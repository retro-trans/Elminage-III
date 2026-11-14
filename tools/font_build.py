"""Build work/font/FONT10_16.GIM: the game's half-width ASCII glyphs, left-aligned in their
10x16 cells so the VWF can crop them (vwf.measure reads widths from the result).

    python tools/font_build.py          # also writes work/font/FONT10_16_preview.png
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gim

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
SRC = os.path.join(ROOT, 'work', 'source', 'arc', 'ANIME', 'FONT10_16.GIM')
OUT = os.path.join(ROOT, 'work', 'font', 'FONT10_16.GIM')


def main():
    d = open(SRC, 'rb').read()
    rgba, idx, img = gim.decode(d)
    idx = idx.copy()
    alpha = rgba[:, :, 3]
    bg = 0
    # background index: most common index in an empty cell (space, code 0x20)
    bg = int(np.bincount(idx[0:16, 0:10].ravel()).argmax())
    for code in range(0x21, 0x7f):
        i = code - 0x20
        x0, y0 = (i % 25) * 10, (i // 25) * 16
        cell = idx[y0:y0 + 16, x0:x0 + 10].copy()
        lit = alpha[y0:y0 + 16, x0:x0 + 10] > 40
        cols = np.where(lit.any(0))[0]
        if not len(cols):
            continue
        left = int(cols.min())
        if left == 0:
            continue
        new = np.full_like(cell, bg)
        new[:, :10 - left] = cell[:, left:]
        idx[y0:y0 + 16, x0:x0 + 10] = new
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    out = gim.encode_index(d, idx)
    open(OUT, 'wb').write(out)
    from PIL import Image
    r2, _, _ = gim.decode(out)
    a = r2[:, :, 3:4].astype(np.uint16)
    Image.fromarray((r2[:, :, :3] * a // 255).astype(np.uint8)).resize((512, 256), Image.NEAREST).save(
        os.path.join(ROOT, 'work', 'font', 'FONT10_16_preview.png'))
    print('wrote', OUT)


if __name__ == '__main__':
    main()
