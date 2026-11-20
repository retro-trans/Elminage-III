"""Redraw text baked into GIM images with the game's own 16px font (FONT10_16, VWF widths).

    python tools/img_text.py                     # every entry in work/ui/images.json + work/ui/specs/*.json
    python tools/img_text.py work/ui/specs/EL01_001.json   # one spec file (preview while working)

images.json: [{"gim": "ANIME/GR01_301.GIM",
               "erase": [[x0, y0, x1, y1, "black" | "copy:x" ], ...],
               "text":  [{"x": 26, "y": 50, "w": 430, "align": "left|center", "lines": [...]
                          or "wrap": "paragraph text", "indent": 20, "lh": 17, "color": [r,g,b]}]}]
Output: work/build/img/<name>.GIM (picked up by tools/build.py via images.archive_files())
        work/ui/preview/<name>.png
The result is quantised to the image's own palette (index formats) so the GIM layout is unchanged.
"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gim
import vwf

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
ARC = os.path.join(ROOT, 'work', 'source', 'arc')
OUT = os.path.join(ROOT, 'work', 'build', 'img')
PREV = os.path.join(ROOT, 'work', 'ui', 'preview')


class Font:
    """16px game font (FONT10_16, left-aligned 10x16 cells, VWF widths)."""
    height = 16

    def __init__(self, spacing=1):
        path = vwf.FONT_NEW if os.path.exists(vwf.FONT_NEW) else vwf.FONT_SRC
        rgba, _, _ = gim.decode(open(path, 'rb').read())
        self.alpha = rgba[:, :, 3].astype(np.float32) / 255.0
        self.w = [w - 1 + spacing if w > 0 else w for w in vwf.measure(path)]
        self.w[0x20] = vwf.SPACE_W
        self.left = [0] * 256

    def glyph(self, c):
        i = ord(c) - 0x20
        x0, y0 = (i % 25) * 10, (i // 25) * 16
        return self.alpha[y0:y0 + 16, x0:x0 + 10]

    def width(self, s):
        return sum(self.w[ord(c)] for c in s)

    def _blend(self, img, x, y, g, color):
        h, w = g.shape
        x0, y0 = max(x, 0), max(y, 0)
        x1, y1 = min(x + w, img.shape[1]), min(y + h, img.shape[0])
        if x1 <= x0 or y1 <= y0:
            return
        a = g[y0 - y:y1 - y, x0 - x:x1 - x, None]
        region = img[y0:y1, x0:x1, :3].astype(np.float32)
        img[y0:y1, x0:x1, :3] = (region * (1 - a) + np.array(color, np.float32) * a).astype(np.uint8)
        al = img[y0:y1, x0:x1, 3:4].astype(np.float32)
        img[y0:y1, x0:x1, 3:4] = np.maximum(al, a * 255).astype(np.uint8)

    def draw(self, img, x, y, s, color, outline=None, rows=None):
        """rows: optional letter colour per glyph row (MENU_GRADIENT); the outline stays one colour."""
        if outline is not None:
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, -1), (-1, 1), (1, 1)):
                self.draw(img, x + dx, y + dy, s, outline)
        for c in s:
            if c != ' ':
                g = self.glyph(c)
                if rows is None:
                    self._blend(img, x - self.left[ord(c)], y, g, color)
                else:
                    for r in range(g.shape[0]):
                        if g[r].any():
                            self._blend(img, x - self.left[ord(c)], y + r, g[r:r + 1], rows[r])
            x += self.w[ord(c)]


    def wrap(self, text, width, indent=0):
        lines, cur, first = [], '', True
        for word in text.split(' '):
            limit = width - (indent if first else 0)
            cand = (cur + ' ' + word) if cur else word
            if self.width(cand) <= limit:
                cur = cand
            else:
                lines.append((indent if first else 0, cur))
                first = False
                cur = word
        lines.append((indent if first else 0, cur))
        return lines


class Font12(Font):
    """12px game font (FONT12_12 full-width Latin cells, ink-measured advance)."""
    height = 12

    def __init__(self, spacing=1):
        import font12
        # letter pixels only (the sheet carries a baked black outline; use `outline` to add one)
        self.g = {c: (g[:, :, 3].astype(np.float32) / 255.0) * (g[:, :, :3].mean(2) / 255.0)
                  for c, g in font12.glyphs(font12.FONT).items()}
        m = font12.metrics(spacing=spacing, space=4, path=font12.FONT)
        self.w = [12] * 256
        self.left = [0] * 256
        for c, (l, adv) in m.items():
            self.w[c], self.left[c] = adv, l

    def glyph(self, c):
        return self.g[ord(c)]

    def wrap(self, text, width, indent=0):
        lines, cur, first = [], '', True
        for word in text.split(' '):
            limit = width - (indent if first else 0)
            cand = (cur + ' ' + word) if cur else word
            if self.width(cand) <= limit:
                cur = cand
            else:
                lines.append((indent if first else 0, cur))
                first = False
                cur = word
        lines.append((indent if first else 0, cur))
        return lines


GR_FONT = os.path.join(ROOT, 'tools', 'fonts', 'gr_latin.txt')
SHADOW = [0, 0, 0]             # default drop shadow colour of the small font (near-black in every sheet)
# brightness of the letter colour by cell row (caps rows 2-8, descenders 9-10): full at the top, ~75 % at
# the bottom, the ramp measured from the PS1 status text ("Lv01 Ex000": 246 -> 191) the user pointed at
GRADIENT = [1.0, 1.0, 1.0, 0.97, 0.94, 0.91, 0.88, 0.85, 0.81, 0.77, 0.74, 0.74]
SHADOW_OFFS = ((1, 0), (0, 1), (1, 1))   # right, down and diagonal: a 1 px diagonal alone vanishes when the
                                         # emulator / PSP scales the dark panels (v0.8.7 check)


class FontGR(Font):
    """Small label font: hand-drawn proportional 12px Latin font with 1 px strokes (tools/fonts/gr_latin.txt,
    taken from the Getter Robo Daikessen project, project original). Caps rows 2-8, x-height rows 4-8,
    descenders rows 9-10, so a drop shadow 1 px right/down stays inside the 12 rows. Advance = ink width + 1: the
    column after each letter holds its shadow, so the shadow costs no width."""
    height = 12

    def __init__(self, spacing=1):
        self.g, self.w, self.left = {}, [0] * 256, [0] * 256
        cur = None
        for ln in open(GR_FONT, encoding='utf-8'):
            ln = ln.rstrip('\n')
            if ln.startswith('@'):
                p = ln.split()
                ch = ' ' if p[1] == 'space' else p[1]
                adv = next((int(x[4:]) for x in p[3:] if x.startswith('adv=')), None)
                cur = [ch, int(p[2]), [], adv]
                self.g[ch] = cur
            elif cur is not None and ln and set(ln) <= set('#.'):
                cur[2].append(ln)
        for ch, (_, top, rows, adv) in list(self.g.items()):
            w = max((len(r) for r in rows), default=0)
            a = np.zeros((12, max(w, 1)), np.float32)
            for r, row in enumerate(rows):
                a[top + r, :len(row)] = [1.0 if c == '#' else 0.0 for c in row]
            self.g[ch] = a
            # adv= in the file counts shadow column + gap (Getter layout); here the gap holds the shadow
            self.w[ord(ch)] = (adv if adv is not None else w + 2) - 1

    def glyph(self, c):
        return self.g[c]

    _grad = None

    def _blend(self, img, x, y, g, color):
        # letter colour fades down the cell (GRADIENT by cell row), like the Getter / PS1 status text
        if self._grad is not None and list(color) == list(self._grad):
            for r in range(g.shape[0]):
                if g[r].any():
                    c = [min(255, int(round(v * GRADIENT[r]))) for v in color]
                    Font._blend(self, img, x, y + r, g[r:r + 1], c)
            return
        Font._blend(self, img, x, y, g, color)

    def draw(self, img, x, y, s, color, outline=None, shadow=None):
        if shadow is not None and outline is None:
            for dx, dy in SHADOW_OFFS:
                Font.draw(self, img, x + dx, y + dy, s, shadow)
        self._grad = color
        try:
            Font.draw(self, img, x, y, s, color, outline)
        finally:
            self._grad = None

    wrap = Font12.wrap


def nearest_palette(rgba, pal):
    flat = rgba.reshape(-1, 4).astype(np.int32)
    p = pal.astype(np.int32)
    out = np.empty(len(flat), np.uint8)
    for s in range(0, len(flat), 65536):
        blk = flat[s:s + 65536]
        d = ((blk[:, None, :] - p[None, :, :]) ** 2).sum(2)
        out[s:s + 65536] = d.argmin(1)
    return out.reshape(rgba.shape[:2])


def fill_free_slots(pal, kept_idx, new_px, min_err=12):
    """Palette entries no unchanged pixel uses are free: give them the redrawn colours the palette
    matches worst (weighted by pixel count), so e.g. the cream menu gradient survives on sheets whose
    palette has no warm whites (EL02_001 / EL02_002). Returns a new palette (RGBA8888 rows)."""
    pal = pal.astype(np.int32).copy()
    free = sorted(set(range(len(pal))) - set(np.unique(kept_idx).tolist()))
    if not free:
        return pal
    cols, counts = np.unique(new_px.reshape(-1, 4).astype(np.int32), axis=0, return_counts=True)
    best = np.sqrt(((cols[:, None, :] - pal[None, :, :]) ** 2).sum(2)).min(1)
    used = set()
    for slot in free:
        score = counts * np.where(best > min_err, best, 0) ** 2
        if used:
            score[list(used)] = 0
        k = int(score.argmax())
        if score[k] <= 0:
            break
        pal[slot] = cols[k]
        used.add(k)
        best = np.minimum(best, np.sqrt(((cols - cols[k]) ** 2).sum(1)))
    return pal


FONTS = {}
# '12' in the specs means the small label font: the hand-drawn FontGR (v0.8.7). The game's own FONT12_12
# (thin, widely spaced letters) stays available as '12game'.
SMALL = {'12': FontGR, '12game': Font12}


def get_font(name='16', spacing=1):
    if name == '12':
        spacing = 1                     # FontGR has one advance (the gap holds the shadow)
    key = (name, spacing)
    if key not in FONTS:
        FONTS[key] = SMALL.get(name, Font)(spacing)
    return FONTS[key]


def erase(img, rect, how):
    x0, y0, x1, y1 = rect
    if how == 'black':
        img[y0:y1, x0:x1, :3] = 0
    elif how.startswith('copy:'):                 # repeat one source column across the rect
        sx = int(how[5:])
        img[y0:y1, x0:x1] = img[y0:y1, sx:sx + 1]
    elif how.startswith('blit:'):                 # copy a same-size rect from (sx, sy)
        sx, sy = map(int, how[5:].split(','))
        img[y0:y1, x0:x1] = img[sy:sy + (y1 - y0), sx:sx + (x1 - x0)].copy()
    elif how == 'inpaint':                        # smooth fill from the rect's border pixels
        top = img[y0 - 1, x0:x1].astype(np.float32)
        bot = img[y1, x0:x1].astype(np.float32)
        lef = img[y0:y1, x0 - 1].astype(np.float32)
        rig = img[y0:y1, x1].astype(np.float32)
        H, W = y1 - y0, x1 - x0
        fy = ((np.arange(H) + 1) / (H + 1))[:, None, None]
        fx = ((np.arange(W) + 1) / (W + 1))[None, :, None]
        v = top[None] * (1 - fy) + bot[None] * fy
        h_ = lef[:, None] * (1 - fx) + rig[:, None] * fx
        wv = np.minimum(fy, 1 - fy)          # distance to top/bottom border
        wh = np.minimum(fx, 1 - fx)
        img[y0:y1, x0:x1] = ((v * wh + h_ * wv) / np.maximum(wv + wh, 1e-6)).astype(np.uint8)
    elif how == 'clear':                          # fully transparent
        img[y0:y1, x0:x1] = 0
    elif how.startswith('vcopy:'):                # repeat one source row down the rect
        sy = int(how[6:])
        img[y0:y1, x0:x1] = img[sy:sy + 1, x0:x1]
    elif how.startswith('fill:'):
        img[y0:y1, x0:x1] = [int(v) for v in how[5:].split(',')]
    else:
        raise SystemExit('unknown erase mode ' + how)


def fit_font(s, w, prefs):
    """First (font, spacing) from prefs whose width fits w."""
    for name, sp in prefs:
        f = get_font(name, sp)
        if f.width(s) <= w:
            return f
    return None


# Menu buttons in their normal state (16px font, light letters with a near-black outline, drawn on the
# nearly black menu panels: town, tavern, temple, shop, battle commands, load menu, map places) get a
# white -> cream gradient so they stand out; highlighted (coloured outline) and greyed states keep their
# colours. Rows as tools/font_tint.py (pixel text font): cap tops rows 0-3, baseline row 13.
MENU_TOP, MENU_BOTTOM = (255, 252, 245), (226, 206, 160)


def menu_gradient(height=16):
    rows = []
    for r in range(height):
        t = min(max((r - 3) / 10.0, 0.0), 1.0)
        rows.append([int(round(a + (b - a) * t)) for a, b in zip(MENU_TOP, MENU_BOTTOM)])
    return rows


def is_menu_normal(f, color, outline, st):
    """Spec key "gradient": true / false overrides the rule."""
    if 'gradient' in st:
        return bool(st['gradient'])
    return (type(f) is Font and outline is not None and max(outline) <= 30
            and min(color) >= 200)


def _draw(f, img, x, y, s, color, outline, st):
    """Draw with the small font's drop shadow (spec key "shadow": [r, g, b], or null for none), or the
    menu gradient (is_menu_normal)."""
    if isinstance(f, FontGR):
        f.draw(img, x, y, s, color, outline, st.get('shadow', SHADOW))
    elif is_menu_normal(f, color, outline, st):
        f.draw(img, x, y, s, color, outline, rows=menu_gradient(f.height))
    else:
        f.draw(img, x, y, s, color, outline)


def build_entry(ent, font=None):
    src = os.path.join(ARC, ent['gim'].replace('/', os.sep))
    d = open(src, 'rb').read()
    rgba, idx, info = gim.decode(d)
    img = rgba.copy()
    for e in ent.get('erase', []):
        erase(img, e[:4], e[4])
    style = ent.get('style', {})
    prefs = [tuple(p) for p in style.get('fonts', [['16', 1], ['16', 0], ['12', 1], ['12', 0]])]
    for lab in ent.get('labels', []):
        x, y, w, h = lab['rect']
        st = dict(style, **lab)
        if st.get('bg'):
            erase(img, [x + st.get('pad_l', 0), y, x + w - st.get('pad_r', 0), y + h], st['bg'])
        en = lab['en']
        tw = w - st.get('pad_l', 0) - st.get('pad_r', 0) - st.get('inset', 4)
        lp = [tuple(x) for x in lab['fonts']] if 'fonts' in lab else prefs
        f = fit_font(en, tw, lp)
        if f is None and st.get('squeeze'):
            # condensed: render with the last font at natural width, resample to tw px wide
            from PIL import Image
            f = get_font(*lp[-1])
            nat = f.width(en)
            scratch = np.zeros((f.height + 2, nat + 2, 4), np.uint8)
            f.draw(scratch, 1, 1, en, st.get('color', [255, 255, 255]), st.get('outline'))
            sq = np.array(Image.fromarray(scratch, 'RGBA').resize((tw + 2, f.height + 2), Image.BOX)).astype(np.float32)
            on = sq[:, :, 3] >= 110                       # crisp: solid label colour or nothing
            sq[:, :, :3] = np.array(st.get('color', [255, 255, 255]), np.float32)
            sq[:, :, 3] = np.where(on, 255, 0)
            tx = x + st.get('pad_l', 0) + (w - st.get('pad_l', 0) - st.get('pad_r', 0) - tw) // 2 - 1
            ty = y + (h - f.height) // 2 + st.get('dy', 0) - 1
            reg = img[ty:ty + sq.shape[0], tx:tx + sq.shape[1]].astype(np.float32)
            al = sq[:, :, 3:4] / 255.0
            reg[:, :, :3] = sq[:, :, :3] * al + reg[:, :, :3] * (1 - al)
            reg[:, :, 3:4] = np.maximum(reg[:, :, 3:4], sq[:, :, 3:4])
            img[ty:ty + sq.shape[0], tx:tx + sq.shape[1]] = reg.astype(np.uint8)
            continue
        if f is None:
            raise SystemExit('%s: label too wide: %r (%d px > %d)' % (ent['gim'], en, get_font(*lp[-1]).width(en), tw))
        tx = x + st.get('pad_l', 0) + st.get('inset', 4) // 2
        if st.get('align', 'center') == 'center':
            tx = x + st.get('pad_l', 0) + (w - st.get('pad_l', 0) - st.get('pad_r', 0) - f.width(en)) // 2
        elif st.get('align') == 'right':      # last glyph's trailing spacing column stays blank
            tx = x + w - st.get('pad_r', 0) - st.get('inset', 4) // 2 - f.width(en) + 1
            if isinstance(f, FontGR) and en:   # glyphs with adv= ('1') end in a blank column: align the ink
                tx += f.w[ord(en[-1])] - f.g[en[-1]].shape[1] - 1
        tx += st.get('dx', 0)                 # the game draws a few sprites off its grid (equip 'Acc2')
        ty = y + (h - f.height) // 2 + st.get('dy', 0)
        _draw(f, img, tx, ty, en, st.get('color', [255, 255, 255]), st.get('outline'), st)
    for t in ent.get('text', []):
        f = get_font(t.get('font', '16'), t.get('spacing', 1)) if font is None or 'font' in t else font
        color = t.get('color', [235, 235, 235])
        lh = t.get('lh', 17)
        y = t['y']
        if 'wrap' in t:
            paras = t['wrap'] if isinstance(t['wrap'], list) else [t['wrap']]
            lines = []
            for p in paras:
                lines += f.wrap(p, t['w'], t.get('indent', 0))
        else:
            lines = [(0, s) for s in t['lines']]
        y_start = y
        if t.get('glow'):                         # soft halo behind the text (logo style)
            r_, g_, b_, a_, rad = t['glow']
            mask = np.zeros(img.shape[:2] + (4,), np.uint8)
            yy = y_start
            for ind, s in lines:
                x = t['x'] + ind
                if t.get('align') == 'center':
                    x = t['x'] + (t['w'] - f.width(s)) // 2
                f.draw(mask, x, yy, s, [255, 255, 255], [255, 255, 255])
                yy += lh
            from PIL import Image, ImageFilter
            m = Image.fromarray(mask[:, :, 3]).filter(ImageFilter.MaxFilter(2 * (rad // 2) + 1))
            m = np.array(m.filter(ImageFilter.GaussianBlur(rad))).astype(np.float32) / 255.0
            ha = np.clip(m * 2.0, 0, 1) * a_
            base_a = img[:, :, 3].astype(np.float32)
            out_a = base_a + ha * (1 - base_a / 255.0)          # base over halo
            w_b = np.where(out_a > 0, base_a / np.maximum(out_a, 1), 0)[..., None]
            img[:, :, :3] = (img[:, :, :3] * w_b + np.array([r_, g_, b_]) * (1 - w_b)).astype(np.uint8)
            img[:, :, 3] = np.clip(out_a, 0, 255).astype(np.uint8)
        for ind, s in lines:
            x = t['x'] + ind
            if t.get('align') == 'center':
                x = t['x'] + (t['w'] - f.width(s)) // 2
            _draw(f, img, x, y, s, color, t.get('outline'), t)
            y += lh
        if y - lh + f.height > t.get('ymax', 10 ** 9):
            raise SystemExit('%s: text overflows (%d > %d)' % (ent['gim'], y - lh + f.height, t['ymax']))
    name = os.path.basename(src)
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(PREV, exist_ok=True)
    if idx is None:
        raise SystemExit('direct-colour GIM not supported yet: ' + name)
    img_pal = gim.parse(d)[1]
    pr = d[img_pal['data']:img_pal['data'] + img_pal['w'] * (4 if img_pal['fmt'] == 3 else 2)]
    pal = gim._colors(pr, img_pal['fmt'])
    changed = (img != rgba).any(2)
    new_idx = idx.copy()
    pal_new = None
    if changed.any():
        if img_pal['fmt'] == 3:
            pal_new = fill_free_slots(pal, idx[~changed], img[changed])
            pal = pal_new
        new_idx[changed] = nearest_palette(img[changed][None, :, :], pal)[0]
    out = gim.encode_index(d, new_idx)
    if pal_new is not None:
        out = bytearray(out)
        o = gim.parse(bytes(out))[1]['data']
        out[o:o + 4 * len(pal_new)] = pal_new.astype(np.uint8).tobytes()
        out = bytes(out)
    open(os.path.join(OUT, name), 'wb').write(out)
    from PIL import Image
    Image.fromarray(pal[new_idx], 'RGBA').save(os.path.join(PREV, name.replace('.GIM', '.png')))
    return ent['gim'].split('/')[0], name


SPECS = [os.path.join(ROOT, 'work', 'ui', 'images.json'), os.path.join(ROOT, 'work', 'ui', 'specs')]


def load_specs(paths=SPECS):
    """Entries from images.json and every work/ui/specs/*.json (one GIM per entry)."""
    import glob
    ents = []
    for p in paths:
        files = sorted(glob.glob(os.path.join(p, '*.json'))) if os.path.isdir(p) else ([p] if os.path.exists(p) else [])
        for f in files:
            d = json.load(open(f, encoding='utf-8'))
            ents += d if isinstance(d, list) else [d]
    seen = set()
    for e in ents:
        if e['gim'] in seen:
            raise SystemExit('duplicate spec for ' + e['gim'])
        seen.add(e['gim'])
    return ents


def archive_files(paths=SPECS):
    """{archive: {name: bytes}} for build.py (rebuilds every image)."""
    res = {}
    for ent in load_specs(paths):
        arc, name = build_entry(ent)
        res.setdefault(arc, {})[name] = open(os.path.join(OUT, name), 'rb').read()
    return res


if __name__ == '__main__':
    paths = sys.argv[1:] or SPECS
    for arc, files in archive_files(paths).items():
        for n in files:
            print(arc, n)
