"""FONT12_12 (full-width 12x12 font, 21 cells per row) helpers: ASCII -> cell via the game's
ASCII->SJIS table (0x089749C8), SJIS -> cell index (row 0x81: lo-0x40; row 0x82: 189 + lo-0x4F).

v0.8.9: the cells the ASCII table points at are redrawn with the small label font (tools/fonts/gr_latin.txt,
img_text.FontGR) in the sheet's own style (white letter, black 4-neighbour outline), written to
work/font/FONT12_12.GIM (build_sheet; vwf.apply12 puts it into ANIME). English names in the party bar then
match the redrawn UI labels. glyphs()/metrics() read that sheet; pass path=FONT for the original."""
import os
import struct
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gim

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
FONT = os.path.join(ROOT, 'work', 'source', 'arc', 'ANIME', 'FONT12_12.GIM')
ELF = os.path.join(ROOT, 'work', 'source', 'EBOOT.elf')
NEW = os.path.join(ROOT, 'work', 'font', 'FONT12_12.GIM')
TABLE = 0x089749C8
SPACING = 0             # with the outline, letters still have 2 px between strokes
GRAD_BASE = 3           # palette entries 3..14: letter colour by cell row (unused in the original sheet)


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


def build_sheet():
    """Write NEW: FONT12_12 with the ASCII-mapped cells holding the small label font (idx 2 white letter,
    idx 1 black outline, idx 0 transparent, as the original cells)."""
    import img_text
    f = img_text.get_font('12')
    d = open(FONT, 'rb').read()
    _, idx, _ = gim.decode(d)
    idx = idx.copy()
    done = set()
    for c, sj in ascii_sjis().items():
        i = cell(sj)
        if i is None or c == 0x20 or i in done:
            continue
        done.add(i)
        x, y = (i % 21) * 12, (i // 21) * 12
        g = f.glyph(chr(c)) > 0.5
        h, w = g.shape
        ink = np.zeros((12, 12), bool)
        ink[:h, 1:1 + min(w, 10)] = g[:12, :10]
        out = np.zeros_like(ink)
        out[1:] |= ink[:-1]; out[:-1] |= ink[1:]; out[:, 1:] |= ink[:, :-1]; out[:, :-1] |= ink[:, 1:]
        out &= ~ink
        cellv = np.zeros((12, 12), idx.dtype)
        cellv[out] = 1
        # letter pixels: palette entry GRAD_BASE + cell row, a white -> grey ramp (img_text.GRADIENT)
        rows = np.repeat(np.arange(12)[:, None], 12, 1)
        cellv[ink] = (GRAD_BASE + rows[ink]).astype(idx.dtype)
        idx[y:y + 12, x:x + 12] = cellv
    out_d = bytearray(gim.encode_index(d, idx))
    # palette: 16 RGBA8888 entries, only 0 (clear), 1 (black), 2 (white) used by the original sheet
    pi = gim.parse(bytes(out_d))[1]
    assert pi['fmt'] == 3 and pi['w'] >= GRAD_BASE + 12, pi
    for r in range(12):
        v = min(255, int(round(255 * img_text.GRADIENT[r])))
        o = pi['data'] + 4 * (GRAD_BASE + r)
        out_d[o:o + 4] = bytes((v, v, v, 255))
    os.makedirs(os.path.dirname(NEW), exist_ok=True)
    open(NEW, 'wb').write(bytes(out_d))
    return NEW


def glyphs(path=None):
    path = path or (NEW if os.path.exists(NEW) else FONT)
    rgba, _, _ = gim.decode(open(path, 'rb').read())
    tab = ascii_sjis()
    out = {}
    for c, sj in tab.items():
        i = cell(sj)
        if i is None:
            continue
        x, y = (i % 21) * 12, (i // 21) * 12
        out[c] = rgba[y:y + 12, x:x + 12]
    return out


def metrics(spacing=None, space=4, path=None):
    """{ascii: (left, advance)}: draw at x-left, advance by ink width + spacing."""
    if spacing is None:
        spacing = 1 if path == FONT else SPACING
    m = {}
    for c, g in glyphs(path).items():
        cols = np.where((g[:, :, 3] > 40).any(0))[0]
        if c == 0x20 or not len(cols):
            m[c] = (0, space)
        else:
            m[c] = (int(cols.min()), int(cols.max() - cols.min()) + 1 + spacing)
    return m


if __name__ == '__main__':
    from PIL import Image
    build_sheet()
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
