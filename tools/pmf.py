"""PSMF (.pmf) movie helper: split the H.264 elementary stream into access units using the
per-GOP 0xBF tables, and write a new ES back into the exact same container layout.

    import pmf; m = pmf.Pmf(path); m.gops -> [(first_frame, [au sizes])]; m.es -> bytes
    m.write(path_out, new_es)   # new_es must have exactly the same length (and AU sizes)
"""
import struct


class Pmf:
    def __init__(self, path):
        self.d = bytearray(open(path, 'rb').read())
        d = self.d
        self.vid = []          # (offset, length) of every video PES payload, in order
        self.gops = []         # [au sizes] per GOP, from private stream 2 (0xBF)
        i = 2048
        while i < len(d):
            assert d[i:i + 4] == b'\x00\x00\x01\xba', hex(i)
            j = i + 14 + (d[i + 13] & 7)
            while j < i + 2048:
                sid = d[j + 3]
                ln = struct.unpack('>H', d[j + 4:j + 6])[0]
                if sid == 0xE0:
                    hl = d[j + 8]
                    self.vid.append((j + 9 + hl, ln - 3 - hl))
                elif sid == 0xBF:
                    p = d[j + 6:j + 6 + ln]
                    n = struct.unpack('>H', p[16:18])[0]
                    sizes = [struct.unpack('>H', p[20 + 4 * k:22 + 4 * k])[0] |
                             ((struct.unpack('>H', p[18 + 4 * k:20 + 4 * k])[0] & 0x7F) << 16)
                             for k in range(n)]
                    self.gops.append(sizes)
                j += 6 + ln
            i += 2048
        self.es = b''.join(bytes(d[o:o + n]) for o, n in self.vid)

    def aus(self):
        out, p = [], 0
        for sizes in self.gops:
            for s in sizes:
                out.append(self.es[p:p + s])
                p += s
        return out, p

    def write(self, path, new_es):
        assert len(new_es) == len(self.es)
        d = bytearray(self.d)
        p = 0
        for o, n in self.vid:
            d[o:o + n] = new_es[p:p + n]
            p += n
        open(path, 'wb').write(bytes(d))
