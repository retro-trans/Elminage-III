"""EBOOT (plain ELF) patcher with a code cave appended after .bss.

The single PT_LOAD segment (va 0x08804000, filesz 0x3C1500, memsz 0x7F1580) is extended:
filesz = memsz = CAVE_END - 0x08804000. Bytes between the old filesz and CAVE are zero
(the old .bss, which the loader zeroes anyway). Section headers are moved to the end.
REAL-HARDWARE NOTE: the module grows by the cave size; the game's heap starts after the
module, so keep the cave small (see CAVE_SIZE) and test free memory.

    from eboot import Eboot
    eb = Eboot()                         # loads work/source/EBOOT.elf
    a = eb.alloc(code_bytes, 'name')     # place bytes in the cave, returns va
    eb.asm(va, 'addiu $v0, $zero, 1')    # assemble at va (in text or cave)
    eb.save('out/EBOOT.BIN')
"""
import os
import struct

import keystone

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
SRC = os.path.join(ROOT, 'work', 'source', 'EBOOT.elf')
BASE = 0x08804000
CAVE = 0x08FF5600          # just after memsz end (0x08FF5580), 0x80 aligned
CAVE_SIZE = 0x40000        # 256 KB: code, tables, buffers, relocated EBOOT strings
BSS = CAVE + CAVE_SIZE     # zero-filled buffers after the cave: in memsz only, not in the file


class Eboot:
    def __init__(self, path=SRC):
        d = bytearray(open(path, 'rb').read())
        self.hdr = d
        phoff = struct.unpack_from('<I', d, 0x1c)[0]
        self.phoff = phoff
        t, off, va, pa, fsz, msz, fl, al = struct.unpack_from('<8I', d, phoff)
        assert va == BASE and off == 0x54
        self.seg_off, self.fsz, self.msz, self.pa = off, fsz, msz, pa
        self.mem = bytearray(CAVE + CAVE_SIZE - BASE)
        self.mem[:fsz] = d[off:off + fsz]
        shoff = struct.unpack_from('<I', d, 0x20)[0]
        shnum = struct.unpack_from('<H', d, 0x30)[0]
        self.shdrs = bytearray(d[shoff:shoff + shnum * 40])
        self.shtail = bytes(d[off + fsz:shoff])   # .shstrtab/.comment etc. between segment and shdrs
        self.tail_off = off + fsz
        self.cave_ptr = CAVE
        self.bss_ptr = BSS
        self.symbols = {}
        self.ks = keystone.Ks(keystone.KS_ARCH_MIPS, keystone.KS_MODE_MIPS32 + keystone.KS_MODE_LITTLE_ENDIAN)

    # memory -----------------------------------------------------------
    def read(self, va, n):
        return bytes(self.mem[va - BASE:va - BASE + n])

    def write(self, va, data):
        self.mem[va - BASE:va - BASE + len(data)] = data

    def u32(self, va):
        return struct.unpack_from('<I', self.mem, va - BASE)[0]

    def w32(self, va, v):
        struct.pack_into('<I', self.mem, va - BASE, v & 0xffffffff)

    def alloc(self, data, name=None, align=4):
        self.cave_ptr = (self.cave_ptr + align - 1) & ~(align - 1)
        va = self.cave_ptr
        if va + len(data) > CAVE + CAVE_SIZE:
            raise MemoryError('cave full')
        self.write(va, data)
        self.cave_ptr += len(data)
        if name:
            self.symbols[name] = va
        return va

    def bss(self, n, name=None, align=0x40):
        """Reserve zero-initialised memory after the cave (adds to memsz, not to the file)."""
        self.bss_ptr = (self.bss_ptr + align - 1) & ~(align - 1)
        va = self.bss_ptr
        self.bss_ptr += n
        if name:
            self.symbols[name] = va
        return va

    def reserve(self, n, name=None, align=4):
        return self.alloc(b'\0' * n, name, align)

    # assembly ---------------------------------------------------------
    def assemble(self, src, va):
        for k, v in sorted(self.symbols.items(), key=lambda x: -len(x[0])):
            src = src.replace('@' + k, '0x%08x' % v)
        enc, _ = self.ks.asm('.set noreorder; ' + src, va)
        if enc is None:
            raise ValueError('assembly failed at %x' % va)
        return bytes(enc)

    def asm(self, va, src, expect=None):
        code = self.assemble(src, va)
        if expect is not None:
            assert len(code) == expect * 4, (hex(va), len(code))
        self.write(va, code)
        return code

    def asm_alloc(self, src, name):
        """Assemble into the cave (two passes so labels/branches resolve at the final va)."""
        va = (self.cave_ptr + 3) & ~3
        self.symbols[name] = va
        code = self.assemble(src, va)
        return self.alloc(code, name)

    # output -----------------------------------------------------------
    def save(self, path):
        size = self.cave_ptr - BASE
        size = (size + 0xf) & ~0xf
        out = bytearray(self.hdr[:self.seg_off])
        memsz = max(size, self.msz, (self.bss_ptr - BASE + 0xf) & ~0xf if self.bss_ptr > BSS else 0)
        struct.pack_into('<8I', out, self.phoff, 1, self.seg_off, BASE, self.pa, size, memsz, 7, 16)
        out += self.mem[:size]
        tail_new = len(out)
        out += self.shtail
        shoff = len(out)
        sh = bytearray(self.shdrs)
        # shift file offsets of sections that lived after the segment
        for i in range(len(sh) // 40):
            o = struct.unpack_from('<I', sh, i * 40 + 16)[0]
            if o >= self.tail_off:
                struct.pack_into('<I', sh, i * 40 + 16, o - self.tail_off + tail_new)
        out += sh
        struct.pack_into('<I', out, 0x20, shoff)
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        open(path, 'wb').write(out)
        return len(out)


def j(target):
    return 'j 0x%08x' % target


def jal(target):
    return 'jal 0x%08x' % target
