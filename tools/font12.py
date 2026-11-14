"""FONT12_12 (full-width 12x12 font, 21 cells per row) helpers: ASCII -> cell via the game's
ASCII->SJIS table (0x089749C8), SJIS -> cell index (row 0x81: lo-0x40; row 0x82: 189 + lo-0x4F)."""
import os
import struct
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gim

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
FONT = os.path.join(ROOT, 'work', 'source', 'arc', 'ANIME', 'FONT12_12.GIM')
ELF = os.path.join(ROOT, 'work', 'source', 'EBOOT.elf')
TABLE = 0x089749C8


def ascii_sjis():
    d = open(ELF, 'rb').read()
    off = TABLE - 0x08804000 + 0x54
    return {c: struct.unpack_from('<H', d, off + 2 * (c - 0x20))[0] for c in range(0x20, 0x7f)}


def cell(sj):
    hi, lo = sj >> 8, sj & 0xff
    skip = 1 if lo > 0x7f else 0
    if hi == 0x81:
        return lo - 0x40
    if hi == 0x82:
        return 189 + lo - 0x4f
    return None


def glyphs():
    rgba, _, _ = gim.decode(open(FONT, 'rb').read())
    tab = ascii_sjis()
    out = {}
    for c, sj in tab.items():
        i = cell(sj)
        if i is None:
            continue
        x, y = (i % 21) * 12, (i // 21) * 12
        out[c] = rgba[y:y + 12, x:x + 12]
    return out


def metrics(spacing=1, space=4):
    """{ascii: (left, advance)}: draw at x-left, advance by ink width + spacing."""
    m = {}
    for c, g in glyphs().items():
        cols = np.where((g[:, :, 3] > 40).any(0))[0]
        if c == 0x20 or not len(cols):
            m[c] = (0, space)
        else:
            m[c] = (int(cols.min()), int(cols.max() - cols.min()) + 1 + spacing)
    return m


if __name__ == '__main__':
    from PIL import Image
    g = glyphs()
    m = metrics()
    s = sys.argv[1] if len(sys.argv) > 1 else 'Grace Kanosuke Aruna Meme Green Froile 0123'
    img = Image.new('RGBA', (12 * len(s), 12), (0, 0, 80, 255))
    x = 0
    for ch in s:
        l, adv = m[ord(ch)]
        img.alpha_composite(Image.fromarray(g[ord(ch)], 'RGBA'), (x - l if x - l >= 0 else 0, 0))
        x += adv
    img.crop((0, 0, x, 12)).resize((x * 3, 36), Image.NEAREST).save(os.path.join(ROOT, 'work', 'ui', 'font12_vwf_test.png'))
    print(x)
