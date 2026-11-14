"""Patch files inside a PSP ISO (ISO9660, 2048-byte sectors) without rebuilding it.

A replacement that fits in the file's current sector span (up to the next file's
first sector) is written in place; a larger one is appended at the end of the
image. The directory record (LBA + size, both byte orders) and the PVD volume
size are updated. Everything else in the image stays byte-identical.

    python tools/iso_patch.py in.iso out.iso PSP_GAME/USRDIR/ETC.BIN=path [...]
"""
import os
import shutil
import struct
import sys

SECTOR = 2048


def _both32(v):
    return struct.pack('<I', v) + struct.pack('>I', v)


class Iso:
    def __init__(self, path):
        self.path = path
        self.f = open(path, 'r+b')
        self.f.seek(16 * SECTOR)
        pvd = self.f.read(SECTOR)
        assert pvd[1:6] == b'CD001'
        self.vol_size = struct.unpack_from('<I', pvd, 80)[0]
        root = pvd[156:156 + 34]
        self.files = {}     # path -> (record_file_offset, lba, size)
        self._walk(struct.unpack_from('<I', root, 2)[0], struct.unpack_from('<I', root, 10)[0], '')

    def _walk(self, lba, size, prefix):
        self.f.seek(lba * SECTOR)
        data = self.f.read(size)
        pos = 0
        while pos < len(data):
            ln = data[pos]
            if ln == 0:
                pos = (pos // SECTOR + 1) * SECTOR
                continue
            rec = data[pos:pos + ln]
            elba = struct.unpack_from('<I', rec, 2)[0]
            esize = struct.unpack_from('<I', rec, 10)[0]
            flags = rec[25]
            nlen = rec[32]
            name = rec[33:33 + nlen]
            if name not in (b'\0', b'\1'):
                nm = name.decode('ascii').split(';')[0]
                full = prefix + nm
                if flags & 2:
                    self._walk(elba, esize, full + '/')
                else:
                    self.files[full.upper()] = (lba * SECTOR + pos, elba, esize)
            pos += ln

    def span(self, path):
        """Sectors available to a file: up to the next file's start (or image end)."""
        _, lba, size = self.files[path.upper()]
        starts = sorted(l for _, l, _ in self.files.values() if l > lba)
        nxt = starts[0] if starts else self.vol_size
        return (nxt - lba) * SECTOR

    def replace(self, path, data):
        key = path.upper()
        rec_off, lba, size = self.files[key]
        if len(data) <= self.span(path):
            new_lba = lba
        else:
            new_lba = self.vol_size
            self.vol_size += (len(data) + SECTOR - 1) // SECTOR
        self.f.seek(new_lba * SECTOR)
        self.f.write(data)
        pad = (-len(data)) % SECTOR
        if pad:
            self.f.write(b'\0' * pad)
        self.f.seek(rec_off + 2)
        self.f.write(_both32(new_lba) + _both32(len(data)))
        self.files[key] = (rec_off, new_lba, len(data))
        return new_lba

    def close(self):
        self.f.seek(16 * SECTOR + 80)
        self.f.write(_both32(self.vol_size))
        self.f.truncate(self.vol_size * SECTOR)
        self.f.close()


def patch(src, dst, repl):
    if os.path.abspath(src) != os.path.abspath(dst):
        shutil.copyfile(src, dst)
    iso = Iso(dst)
    res = {}
    for path, fpath in repl.items():
        data = open(fpath, 'rb').read() if isinstance(fpath, str) else fpath
        res[path] = iso.replace(path, data)
    iso.close()
    return res


if __name__ == '__main__':
    src, dst = sys.argv[1], sys.argv[2]
    rep = dict(a.split('=', 1) for a in sys.argv[3:])
    for k, v in patch(src, dst, rep).items():
        print(k, 'lba', v)
