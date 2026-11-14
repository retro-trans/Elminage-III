"""List opaque rectangles (sprites) in a GIM sheet and write a numbered overlay + crops.

    python tools/ui_regions.py ANIME/EL01_000.GIM [--min 8]
Output: work/ui/regions/<NAME>.json  [[id, x, y, w, h], ...]
        work/ui/regions/<NAME>_map.png (2x, numbered boxes)
"""
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw
from collections import deque

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gim

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


def regions(rgba, minsz=8):
    mask = rgba[:, :, 3] > 0
    H, W = mask.shape
    seen = np.zeros_like(mask)
    out = []
    for y0 in range(H):
        for x0 in np.where(mask[y0] & ~seen[y0])[0]:
            if seen[y0, x0]:
                continue
            q = deque([(y0, x0)])
            seen[y0, x0] = True
            ys, xs = [y0, y0], [x0, x0]
            while q:
                y, x = q.popleft()
                ys[0], ys[1] = min(ys[0], y), max(ys[1], y)
                xs[0], xs[1] = min(xs[0], x), max(xs[1], x)
                for ny, nx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                    if 0 <= ny < H and 0 <= nx < W and mask[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        q.append((ny, nx))
            w, h = xs[1] - xs[0] + 1, ys[1] - ys[0] + 1
            if w >= minsz and h >= minsz // 2:
                out.append([int(xs[0]), int(ys[0]), int(w), int(h)])
    out.sort(key=lambda r: (r[1] // 8, r[0]))
    return [[i] + r for i, r in enumerate(out)]


def main():
    rel = sys.argv[1]
    minsz = int(sys.argv[sys.argv.index('--min') + 1]) if '--min' in sys.argv else 8
    rgba, _, _ = gim.decode(open(os.path.join(ROOT, 'work', 'source', 'arc', rel.replace('/', os.sep)), 'rb').read())
    regs = regions(rgba, minsz)
    od = os.path.join(ROOT, 'work', 'ui', 'regions')
    os.makedirs(od, exist_ok=True)
    name = os.path.basename(rel).replace('.GIM', '')
    json.dump(regs, open(os.path.join(od, name + '.json'), 'w'))
    im = Image.fromarray(rgba, 'RGBA')
    bg = Image.new('RGBA', im.size, (255, 0, 255, 255))
    bg.alpha_composite(im)
    bg = bg.convert('RGB').resize((im.size[0] * 2, im.size[1] * 2), Image.NEAREST)
    dr = ImageDraw.Draw(bg)
    for i, x, y, w, h in regs:
        dr.rectangle([x * 2, y * 2, (x + w) * 2 - 1, (y + h) * 2 - 1], outline=(0, 255, 0))
        dr.text((x * 2 + 1, y * 2 + 1), str(i), fill=(255, 255, 0))
    bg.save(os.path.join(od, name + '_map.png'))
    print(len(regs), 'regions')


if __name__ == '__main__':
    main()
