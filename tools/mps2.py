"""Mps2 archive tool (USRDIR/*.BIN) for Elminage III (PSP, ULJM05883).

Format (reversed from EBOOT 0x08918408):
  0x00  'Mps2'
  0x04  u32 entry count N
  0x08  8 bytes 0
  0x10  u32 checksum/unknown, u32 0
  0x18  N entries of 0x18 bytes: u32 offset, u32 size, char name[16]
  Header words from index 6 (byte 0x18) up to (N+1)*0x18 are XORed with
  KEY[255 - (word_index & 0xff)], KEY = 256 u32 at EBOOT 0x08974378.
  File data is 0x800-aligned. The first 0x20 bytes (8 words) of every file are
  XORed with k_i = (~offset + size) - 0x3E5*i  (EBOOT 0x08916204), using the
  file's own TOC offset/size. Then, for each char c of the file name (uppercased),
  byte[0x20 + 7*c] ^= ~c & 0xff  (EBOOT 0x089162a4). extract() removes both,
  build() re-applies both.

    python tools/mps2.py list  ETC.BIN
    python tools/mps2.py x     ETC.BIN outdir
    python tools/mps2.py build orig.BIN replacements_dir out.BIN   # replaces files by name, keeps order
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(__file__))

_KEY = None


def key():
    global _KEY
    if _KEY is None:
        from mips import Elf
        _KEY = struct.unpack('<256I', Elf().read(0x08974378, 1024))
    return _KEY


def _xor_header(b, nwords):
    k = key()
    w = list(struct.unpack_from('<%dI' % nwords, b, 0))
    for i in range(6, nwords):
        w[i] ^= k[255 - (i & 0xff)]
    return struct.pack('<%dI' % nwords, *w)


def file_crypt(data, off, size, name=None):
    """Apply/remove the 0x20-byte head XOR and the name-keyed byte XOR (symmetric)."""
    if name:
        b = bytearray(data)
        for ch in name.upper().encode('ascii'):
            p = 0x20 + 7 * ch
            if p < len(b):
                b[p] ^= (~ch) & 0xff
        data = bytes(b)
    n = min(8, len(data) // 4)
    if n == 0:
        return data
    k = ((~off) + size) & 0xffffffff
    w = list(struct.unpack_from('<%dI' % n, data, 0))
    for i in range(n):
        w[i] ^= (k - 0x3e5 * i) & 0xffffffff
    return struct.pack('<%dI' % n, *w) + data[n * 4:]


def read_toc(path):
    with open(path, 'rb') as f:
        head = f.read(8)
        assert head[:4] == b'Mps2', path
        n = struct.unpack_from('<I', head, 4)[0]
        f.seek(0)
        raw = f.read((n + 1) * 0x18)
    hdr = _xor_header(raw, (n + 1) * 0x18 // 4)
    ents = []
    for i in range(n):
        off, size = struct.unpack_from('<II', hdr, 0x18 + i * 0x18)
        name = hdr[0x20 + i * 0x18:0x30 + i * 0x18].split(b'\0')[0].decode('ascii')
        ents.append((name, off, size))
    return hdr[:0x18], ents


def extract(path, outdir):
    _, ents = read_toc(path)
    os.makedirs(outdir, exist_ok=True)
    with open(path, 'rb') as f:
        for name, off, size in ents:
            f.seek(off)
            with open(os.path.join(outdir, name), 'wb') as o:
                o.write(file_crypt(f.read(size), off, size, name))
    return ents


def build(orig, repl_dir, out):
    """Rebuild archive: same order/names, files from repl_dir override originals.

    Files in repl_dir that the archive does not have are added; the TOC stays sorted by name
    (the original TOCs are sorted) and the entry count in the header is updated."""
    head, ents = read_toc(orig)
    have = {name for name, _, _ in ents}
    added = sorted(n for n in (os.listdir(repl_dir) if repl_dir else []) if n not in have)
    if added:
        ents = sorted(list(ents) + [(n, None, None) for n in added], key=lambda e: e[0])
        head = bytearray(head)
        struct.pack_into('<I', head, 4, len(ents))
        head = bytes(head)
    n = len(ents)
    hsize = (n + 1) * 0x18
    pos = (hsize + 0x7ff) & ~0x7ff
    datas = []
    with open(orig, 'rb') as f:
        for name, off, size in ents:
            rp = os.path.join(repl_dir, name) if repl_dir else None
            if rp and os.path.exists(rp):
                d = open(rp, 'rb').read()
            else:
                f.seek(off)
                d = file_crypt(f.read(size), off, size, name)
            datas.append((name, pos, file_crypt(d, pos, len(d), name)))
            pos = (pos + len(d) + 0x7ff) & ~0x7ff
    hdr = bytearray(head)
    for name, off, d in datas:
        hdr += struct.pack('<II', off, len(d)) + name.encode('ascii').ljust(16, b'\0')
    enc = _xor_header(bytes(hdr), hsize // 4)
    with open(out, 'wb') as o:
        o.write(enc)
        for name, off, d in datas:
            o.seek(off)
            o.write(d)
        o.truncate((pos + 0x7ff) & ~0x7ff)
    return datas


if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'list':
        for name, off, size in read_toc(sys.argv[2])[1]:
            print('%08x %8d %s' % (off, size, name))
    elif cmd == 'x':
        print(len(extract(sys.argv[2], sys.argv[3])), 'files')
    elif cmd == 'build':
        print(len(build(sys.argv[2], sys.argv[3], sys.argv[4])), 'files')
