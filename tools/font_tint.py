"""Colour gradient for the pixel text font (FONT10_16, the "Original pixel font" option).

    python tools/font_tint.py      # writes work/font/FONT10_16_tint.GIM and work/font/FONT10_16_tint_preview.png

Input is the left-aligned sheet from tools/font_build.py (work/font/FONT10_16.GIM, else the original).
That sheet stays as it is: vwf.measure reads the glyph widths from it, tools/font_hd.py scales it and
tools/img_text.py draws labels with it. This module recolours a copy, which vwf.apply puts in ANIME:
letters go from near-white at the cap tops (TOP, rows 0-3) to cream at the baseline (BOTTOM, row 13),
descender rows stay cream. Alpha (the anti-aliasing) is unchanged, so shapes and widths are the same.
The game multiplies the texture by the text colour, so greyed or coloured text is tinted the same way.
Only image data changes. A darkening shade with a black shadow (v0.8.15) did not show on the nearly
black menu panels; a colour change does.
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gim

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
SRC = os.path.join(ROOT, 'work', 'font', 'FONT10_16.GIM')
ORIG = os.path.join(ROOT, 'work', 'source', 'arc', 'ANIME', 'FONT10_16.GIM')
OUT = os.path.join(ROOT, 'work', 'font', 'FONT10_16_tint.GIM')
CELL_H = 16
TOP, BOTTOM = (255, 252, 245), (226, 206, 160)   # white -> cream
ROW_TOP, ROW_BOTTOM = 3, 13                      # cap tops / baseline in the 16 px cell


def row_colour(row):
    t = min(max((row - ROW_TOP) / float(ROW_BOTTOM - ROW_TOP), 0.0), 1.0)
    return tuple(int(round(a + (b - a) * t)) for a, b in zip(TOP, BOTTOM))


def build(src=None, out=OUT):
    src = src or (SRC if os.path.exists(SRC) else ORIG)
    d = open(src, 'rb').read()
    rgba, idx, _ = gim.decode(d)
    h, w = idx.shape
    rows = np.arange(h) % CELL_H
    rgb = np.array([row_colour(r) for r in rows], np.int64)[:, None, :].repeat(w, 1)
    alpha = rgba[:, :, 3].astype(np.int64)
    px = np.dstack([rgb, alpha])
    px[alpha == 0] = 0
    keys = px[:, :, 0] << 24 | px[:, :, 1] << 16 | px[:, :, 2] << 8 | px[:, :, 3]
    uniq, inv = np.unique(keys, return_inverse=True)
    pi = gim.parse(d)[1]
    assert pi['fmt'] == 3, pi
    assert uniq[0] == 0 and len(uniq) <= pi['w'], (len(uniq), pi['w'])   # index 0: transparent
    new = bytearray(gim.encode_index(d, inv.reshape(h, w).astype(idx.dtype)))
    pal = bytearray(4 * pi['w'])
    for i, k in enumerate(uniq.tolist()):
        pal[4 * i:4 * i + 4] = bytes(((k >> 24) & 255, (k >> 16) & 255, (k >> 8) & 255, k & 255))
    new[pi['data']:pi['data'] + len(pal)] = pal
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, 'wb').write(bytes(new))
    return out, len(uniq)


def preview(path, png, bg=(30, 24, 23), scale=3):
    from PIL import Image
    rgba, _, _ = gim.decode(open(path, 'rb').read())
    a = rgba[:, :, 3:4].astype(np.float64) / 255
    im = rgba[:, :, :3] * a + np.array(bg) * (1 - a)
    Image.fromarray(im.astype(np.uint8)).resize((rgba.shape[1] * scale, rgba.shape[0] * scale),
                                                Image.NEAREST).save(png)


if __name__ == '__main__':
    path, n = build()
    preview(path, os.path.join(ROOT, 'work', 'font', 'FONT10_16_tint_preview.png'))
    print('wrote', path, '(%d palette entries)' % n)
