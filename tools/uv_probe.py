"""Find which texels of a UI sheet the current screen shows (exact sprite rects).

    python tools/uv_probe.py ANIME/EL01_000.GIM [--ylo 0 --yhi 511] [--xmin 0 --xmax 480]
The emulator must show the screen. The sheet (resident in RAM) is overwritten with coordinate-coded
indices and a unique palette (4 passes: x low, x high bit, y low, y high bit); screenshots are decoded
back to source (x, y) and grouped into sprites. Reload a savestate afterwards (the sheet is destroyed).
Prints: screen rect -> source rect for every sprite drawn from the sheet.
"""
import os
import sys
import time
from collections import defaultdict

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gim
from ppsspp_dbg import Emu

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
SHOT = os.path.join(ROOT, 'work', 'emulator', 'shots')


def find_in_ram(e, probe):
    for base in range(0x08800000, 0x0A000000, 0x100000):
        try:
            chunk = e.read(base, 0x100000 + len(probe))
        except RuntimeError:
            chunk = e.read(base, 0x100000)
        i = chunk.find(probe)
        if i >= 0:
            return base + i
    return None


def arg(name, default):
    return int(sys.argv[sys.argv.index(name) + 1]) if name in sys.argv else default


def main():
    rel = sys.argv[1]
    name = os.path.basename(rel)
    built = os.path.join(ROOT, 'work', 'build', 'img', name)
    d = open(built if os.path.exists(built) else os.path.join(ROOT, 'work', 'source', 'arc', rel), 'rb').read()
    img, pal = gim.parse(d)
    w, h = img['w'], img['h']
    with Emu() as e:
        e.pause()
        pix = find_in_ram(e, d[img['data'] + 4096:img['data'] + 4096 + 64])
        if pix is None:
            raise SystemExit('sheet not resident (built GIM differs from RAM?)')
        pix -= 4096
        ppos = find_in_ram(e, d[pal['data']:pal['data'] + 256])
        pal_new = bytearray()
        for i in range(256):
            pal_new += bytes([i, 255 - i, 77, 255])
        e.write(ppos, bytes(pal_new))
        ys, xs = np.mgrid[0:h, 0:w]
        shots = {}
        for key, arr in (('x', xs & 0xFF), ('xh', (xs >> 8) & 1), ('y', ys & 0xFF), ('yh', (ys >> 8) & 1)):
            e.pause()
            e.write(pix, arr.astype(np.uint8).tobytes())
            e.resume()
            time.sleep(0.8)
            p = os.path.join(SHOT, 'uv_%s.png' % key)
            e.screenshot(p, single=1)
            shots[key] = np.array(Image.open(p).convert('RGB')).astype(int)

    def dec(a):
        r, g, b = a[..., 0], a[..., 1], a[..., 2]
        return np.where((abs(r + g - 255) <= 6) & (abs(b - 77) <= 8), r, -1)
    dx, dxh, dy, dyh = (dec(shots[k]) for k in ('x', 'xh', 'y', 'yh'))
    ok = (dx >= 0) & (dxh >= 0) & (dy >= 0) & (dyh >= 0)
    sx, sy = dx + 256 * dxh, dy + 256 * dyh
    ylo, yhi = arg('--ylo', 0), arg('--yhi', h - 1)
    x0, x1 = arg('--xmin', 0), arg('--xmax', 480)
    groups = defaultdict(list)
    for y in range(272):
        for x in range(x0, x1):
            if ok[y, x] and ylo <= sy[y, x] <= yhi:
                groups[(int(sy[y, x]) - y, int(sx[y, x]) - x)].append((x, y))
    rows = []
    for (oy, ox), pts in groups.items():
        if len(pts) < 6:
            continue
        xs_, ys_ = [p[0] for p in pts], [p[1] for p in pts]
        rows.append((min(ys_), min(xs_), max(xs_), max(ys_), ox, oy, len(pts)))
    for y0, xa, xb, yb, ox, oy, n in sorted(rows):
        print('screen x%3d-%3d y%3d-%3d -> src x%3d-%3d y%3d-%3d  (%d px)' % (xa, xb, y0, yb, xa + ox, xb + ox, y0 + oy, yb + oy, n))


if __name__ == '__main__':
    main()
