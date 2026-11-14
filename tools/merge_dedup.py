"""Merge translated deduplicated slices back into a per-SCD translation file.

    python tools/merge_dedup.py work/translation/en/wmap SCDWMAP [--file reviewed.json]
    python tools/merge_dedup.py work/translation/en/chap ALL   (ids carry their own SCD file)

Reads <dir>/rows_index.json (row -> all ids sharing the same Japanese) and the translated
rows (default: every slice_*.out.json; or one combined reviewed file), checks each row with
check_tr.check, and writes 'en' into work/translation/en/scp/<SCD>.json for every id.
Rows with check issues are reported and NOT merged.
"""
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_tr

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


def main():
    d, scd = sys.argv[1], sys.argv[2]
    index = json.load(open(os.path.join(d, 'rows_index.json'), encoding='utf-8'))
    if '--file' in sys.argv:
        rows = json.load(open(sys.argv[sys.argv.index('--file') + 1], encoding='utf-8'))
    else:
        rows = []
        for f in sorted(glob.glob(os.path.join(d, 'slice_*.out.json'))):
            rows += json.load(open(f, encoding='utf-8'))
    en_by_id, bad = {}, 0
    for r in rows:
        ref = index[r['row']]
        if ref['jp'] != r['jp']:
            print('row %d: source text mismatch, skipped' % r['row'])
            bad += 1
            continue
        r = dict(r, id='row%d' % r['row'])
        iss = check_tr.check(r)
        if iss:
            print('row %d [%s]: %s' % (r['row'], r['kind'], '; '.join(iss)))
            bad += 1
            continue
        for i in ref['ids']:
            f, i = (i if isinstance(i, list) else (scd, i))
            en_by_id.setdefault(f, {})[i] = r['en']
    n = 0
    for f, m in en_by_id.items():
        p = os.path.join(ROOT, 'work', 'translation', 'en', 'scp', f + '.json')
        data = json.load(open(p, encoding='utf-8'))
        for e in data:
            if e['id'] in m:
                e['en'] = m[e['id']]
                n += 1
        json.dump(data, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('%d rows read, %d with issues (not merged), %d script entries filled in %d files'
          % (len(rows), bad, n, len(en_by_id)))


if __name__ == '__main__':
    main()
