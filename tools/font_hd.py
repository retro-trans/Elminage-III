"""Build the 2x/4x half-width font sheet for the HD build: work/font/FONT10_16_<n>x.GIM.

Source: the left-aligned 1x sheet (work/font/FONT10_16.GIM from tools/font_build.py, else the original).
Upscaling: Scale2x (EPX) on the palette indices — keeps every original pixel shape, rounds diagonals,
adds no new colours. Glyph cells become 20x32; the HD patch (vwf.apply_hd) doubles texture
coordinates when the game draws from this sheet, so on-screen size is unchanged.
    python tools/font_hd.py      # also writes work/font/FONT10_16_2x_preview.png
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gim
import vwf

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
SCALE = 4                      # 2 or 4
OUT = os.path.join(ROOT, 'work', 'font', 'FONT10_16_%dx.GIM' % SCALE)
COLS_1X, CELL_W, CELL_H = 25, 10, 16
COLS_4X = 12                   # 4x: 40x64 cells repacked 12 per row -> 480x512 (PSP max texture 512)


def scale2x(a):
    p = np.pad(a, 1, mode='edge')
    E = p[1:-1, 1:-1]
    B, D, F, H = p[:-2, 1:-1], p[1:-1, :-2], p[1:-1, 2:], p[2:, 1:-1]
    e0 = np.where((D == B) & (B != F) & (D != H), D, E)
    e1 = np.where((B == F) & (B != D) & (F != H), F, E)
    e2 = np.where((D == H) & (D != B) & (H != F), D, E)
    e3 = np.where((H == F) & (D != H) & (B != F), F, E)
    out = np.empty((a.shape[0] * 2, a.shape[1] * 2), a.dtype)
    out[0::2, 0::2], out[0::2, 1::2], out[1::2, 0::2], out[1::2, 1::2] = e0, e1, e2, e3
    return out


VECTOR = os.path.join(ROOT, 'work', 'font', 'genei', 'GenEiLateGo_v2.ttc')   # SIL OFL 1.1
V_SIZE, V_BASE, V_XSCALE, V_MAXW = 56, 49, 0.75, 38


def render_vector(scale=4):
    """95 ASCII glyphs from Genei LateGo (源暎ラテゴ, SIL OFL) in (10*scale)x(16*scale) cells,
    left-aligned, as an alpha array laid out like the 1x sheet (25 per row)."""
    from PIL import Image, ImageDraw, ImageFont
    f = ImageFont.truetype(VECTOR, V_SIZE * scale // 4, index=0)
    cw, ch = CELL_W * scale, CELL_H * scale
    sheet = np.zeros((ch * 4, cw * COLS_1X), np.uint8)
    for i in range(1, 96):
        c = chr(0x20 + i)
        big = Image.new('L', (cw * 3, ch), 0)
        ImageDraw.Draw(big).text((cw // 2, V_BASE * scale // 4), c, font=f, fill=255, anchor='ls',
                                 stroke_width=max(1, scale // 4), stroke_fill=255)
        a = np.array(big)
        cols = np.where(a.max(0) > 8)[0]
        if not len(cols):
            continue
        a = a[:, cols.min():cols.max() + 1]
        w = a.shape[1]
        nw = max(1, int(round(w * V_XSCALE)))
        maxw = V_MAXW * scale // 4
        nw = min(nw, maxw)
        a = np.array(Image.fromarray(a).resize((nw, ch), Image.LANCZOS))
        x0, y0 = (i % COLS_1X) * cw, (i // COLS_1X) * ch
        sheet[y0:y0 + ch, x0:x0 + nw] = a
    return sheet


def widths_from_alpha(alpha_sheet, scale, spacing=1, space=5):
    """VWF widths (1x pixels) for each code from a scale-x alpha sheet laid out 25 per row."""
    cw, ch = CELL_W * scale, CELL_H * scale
    w = [10] * 256
    for i in range(1, 96):
        x0, y0 = (i % COLS_1X) * cw, (i // COLS_1X) * ch
        cols = np.where((alpha_sheet[y0:y0 + ch, x0:x0 + cw] > 40).any(0))[0]
        w[0x20 + i] = int(np.ceil((cols.max() + 1) / scale)) + spacing if len(cols) else space
    w[0x20] = space
    return w


def hd_widths():
    return widths_from_alpha(render_vector(SCALE), SCALE) if VECTOR and os.path.exists(VECTOR) else None


def build():
    src = vwf.FONT_NEW if os.path.exists(vwf.FONT_NEW) else vwf.FONT_SRC
    d = open(src, 'rb').read()
    rgba, idx, info = gim.decode(d)
    big = scale2x(idx)
    if VECTOR and os.path.exists(VECTOR):
        # glyphs from the OFL vector font: map coverage to the sheet's own alpha palette entries
        pal_info = gim.parse(d)[1]
        P = gim._colors(d[pal_info['data']:pal_info['data'] + pal_info['w'] * 4], pal_info['fmt'])
        rgb0 = P[idx.max()][:3] if idx.max() else P[1][:3]
        cand = [k for k in range(len(P)) if (P[k][:3] == rgb0).all()]
        lut = np.array([min(cand, key=lambda k: abs(int(P[k][3]) - v)) for v in range(256)], np.uint8)
        big = lut[render_vector(SCALE)]
        if SCALE == 2:
            big4 = None
    if SCALE == 4:
        big4 = big if (VECTOR and os.path.exists(VECTOR)) else scale2x(big)
        cw, ch = CELL_W * 4, CELL_H * 4
        big = np.zeros((512, 512), idx.dtype)
        for i in range(96):
            sx, sy = (i % COLS_1X) * cw, (i // COLS_1X) * ch
            dx, dy = (i % COLS_4X) * cw, (i // COLS_4X) * ch
            if sy + ch <= big4.shape[0]:
                big[dy:dy + ch, dx:dx + cw] = big4[sy:sy + ch, sx:sx + cw]
    out = gim.write_index_resized(d, big)
    open(OUT, 'wb').write(out)
    rgba2, idx2, info2 = gim.decode(out)
    assert (idx2 == big).all()
    from PIL import Image
    im = Image.fromarray(rgba2, 'RGBA')
    bg = Image.new('RGBA', im.size, (0, 0, 80, 255))
    bg.alpha_composite(im)
    bg.save(OUT.replace('.GIM', '_preview.png'))
    return out


if __name__ == '__main__':
    build()
    print('wrote', OUT)
