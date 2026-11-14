"""Extract Japanese CSV cells (ETC.BIN) to work/translation/en/csv/<FILE>.json.

Entry: {id: "FILE:row:col", jp, en, used, max}
  used = the cell's Shift-JIS bytes were found in a RAM dump taken after boot
         (work/emulator/states/ram_title.bin) -> the game keeps that text; lazily loaded
         tables (ITEM_TEXT, MON_TEXT) count as used.
  max  = longest original byte length in that column (conservative English budget).
Designer notes/headers come out with used=False; translate those last (or never).
"""
import csv
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import textcodec

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
SRC = os.path.join(ROOT, 'work', 'source', 'arc', 'ETC')
DST = os.path.join(ROOT, 'work', 'translation', 'en', 'csv')
RAM = os.path.join(ROOT, 'work', 'emulator', 'states', 'ram_title.bin')
LAZY = {'ITEM_TEXT.CSV', 'MON_TEXT.CSV'}


def read_csv(path):
    t = open(path, 'rb').read().decode('cp932')
    return list(csv.reader(io.StringIO(t, newline='')))


def main():
    ram = open(RAM, 'rb').read() if os.path.exists(RAM) else b''
    os.makedirs(DST, exist_ok=True)
    tot = used_tot = 0
    for f in sorted(os.listdir(SRC)):
        if not f.endswith('.CSV'):
            continue
        rows = read_csv(os.path.join(SRC, f))
        colmax = {}
        cells = []
        for r, row in enumerate(rows):
            for c, cell in enumerate(row):
                if textcodec.has_jp(cell):
                    b = cell.encode('cp932')
                    colmax[c] = max(colmax.get(c, 0), len(b))
                    cells.append((r, c, cell, b))
        out = []
        for r, c, cell, b in cells:
            used = f in LAZY or (len(b) >= 4 and b in ram)
            out.append(dict(id='%s:%d:%d' % (f, r, c), jp=cell, en='', used=bool(used), max=colmax[c]))
        path = os.path.join(DST, f.replace('.CSV', '.json'))
        if os.path.exists(path):
            old = {e['id']: e for e in json.load(open(path, encoding='utf-8'))}
            for e in out:
                o = old.get(e['id'])
                if o and o['jp'] == e['jp'] and o.get('en'):
                    e['en'] = o['en']
        json.dump(out, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        nu = sum(e['used'] for e in out)
        tot += len(out)
        used_tot += nu
        print('%-16s %5d jp cells, %5d used' % (f, len(out), nu))
    print('total', tot, 'used', used_tot)


if __name__ == '__main__':
    main()
