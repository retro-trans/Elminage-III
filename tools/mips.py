"""MIPS (Allegrex) helpers for the decrypted EBOOT (work/source/EBOOT.elf).

    from mips import Elf
    elf = Elf()                       # loads work/source/EBOOT.elf
    elf.xrefs(0x0896A0F8)             # code addresses that build this address (lui+addiu/ori/lw...)
    elf.dis(0x08804000, 40)           # print disassembly
    elf.func_start(addr)              # walk back to the 'addiu sp,sp,-N' prologue
"""
import os
import struct

import capstone

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
ELF_PATH = os.path.join(ROOT, 'work', 'source', 'EBOOT.elf')


class Elf:
    def __init__(self, path=ELF_PATH):
        self.data = open(path, 'rb').read()
        d = self.data
        phoff, = struct.unpack_from('<I', d, 0x1c)
        phnum, = struct.unpack_from('<H', d, 0x2c)
        shoff, = struct.unpack_from('<I', d, 0x20)
        shnum, = struct.unpack_from('<H', d, 0x30)
        shstrndx, = struct.unpack_from('<H', d, 0x32)
        self.segs = []
        for i in range(phnum):
            t, off, va, pa, fsz, msz, fl, al = struct.unpack_from('<8I', d, phoff + i * 32)
            if t == 1:
                self.segs.append((va, off, fsz, msz))
        self.sections = {}
        if shnum:
            stro = struct.unpack_from('<10I', d, shoff + shstrndx * 40)[4]
            for i in range(shnum):
                nm, typ, fl, addr, off, sz = struct.unpack_from('<6I', d, shoff + i * 40)
                name = d[stro + nm:d.index(b'\0', stro + nm)].decode()
                self.sections[name] = (addr, off, sz)
        self.base = self.segs[0][0]
        self.md = capstone.Cs(capstone.CS_ARCH_MIPS, capstone.CS_MODE_MIPS32 | capstone.CS_MODE_LITTLE_ENDIAN)
        self.md.detail = False

    # address mapping ---------------------------------------------------
    def off(self, va):
        for sva, off, fsz, msz in self.segs:
            if sva <= va < sva + fsz:
                return off + va - sva
        return None

    def va(self, off):
        for sva, soff, fsz, msz in self.segs:
            if soff <= off < soff + fsz:
                return sva + off - soff
        return None

    def read(self, va, n):
        o = self.off(va)
        return self.data[o:o + n]

    def u32(self, va):
        return struct.unpack_from('<I', self.data, self.off(va))[0]

    def cstr(self, va, enc='cp932'):
        o = self.off(va)
        e = self.data.index(b'\0', o)
        return self.data[o:e].decode(enc, 'replace')

    def text_range(self):
        if '.text' in self.sections:
            a, o, s = self.sections['.text']
            return a, a + s
        va, off, fsz, msz = self.segs[0]
        return va, va + fsz

    # disassembly -------------------------------------------------------
    def insns(self, va, count):
        code = self.read(va, count * 4)
        return list(self.md.disasm(code, va))

    def dis(self, va, count=40, out=None):
        lines = ['%08x: %08x  %s %s' % (i.address, struct.unpack('<I', i.bytes)[0], i.mnemonic, i.op_str)
                 for i in self.insns(va, count)]
        s = '\n'.join(lines)
        if out is None:
            print(s)
        return s

    def words(self):
        a, b = self.text_range()
        o = self.off(a)
        n = (b - a) // 4
        return a, struct.unpack_from('<%dI' % n, self.data, o)

    def xrefs(self, target, window=12):
        """Find code that materialises `target` as lui hi + (addiu|ori|lw|sw|lb...) lo."""
        a, ws = self.words()
        hi = (target + 0x8000) >> 16 & 0xffff
        hi_ori = target >> 16 & 0xffff
        lo = target & 0xffff
        res = []
        for i, w in enumerate(ws):
            if w >> 26 == 0x0f:  # lui
                imm = w & 0xffff
                rt = (w >> 16) & 31
                if imm not in (hi, hi_ori):
                    continue
                for j in range(i + 1, min(i + window, len(ws))):
                    w2 = ws[j]
                    op = w2 >> 26
                    rs = (w2 >> 21) & 31
                    if rs != rt:
                        continue
                    imm2 = w2 & 0xffff
                    if op == 0x0d and imm == hi_ori and imm2 == lo:      # ori
                        res.append(a + j * 4)
                    elif op != 0x0d and imm == hi and imm2 == lo and op in (
                            0x09, 0x20, 0x21, 0x23, 0x24, 0x25, 0x28, 0x29, 0x2b, 0x31, 0x39):
                        res.append(a + j * 4)
        return res

    def calls_to(self, func):
        a, ws = self.words()
        want = 0x0c000000 | ((func >> 2) & 0x03ffffff)
        return [a + i * 4 for i, w in enumerate(ws) if w == want]

    def func_start(self, va, limit=0x4000):
        """Walk back to the nearest 'addiu sp, sp, -N'."""
        p = va
        while p > va - limit:
            w = self.u32(p)
            if w >> 16 == 0x27bd and (w & 0x8000):
                return p
            p -= 4
        return None

    def find_bytes(self, pat):
        res = []
        i = self.data.find(pat)
        while i >= 0:
            res.append(self.va(i))
            i = self.data.find(pat, i + 1)
        return res
