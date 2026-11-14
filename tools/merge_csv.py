"""Merge translated CSV slices (work/translation/en/csvt) into work/translation/en/csv/<TABLE>.json.

    python tools/merge_csv.py [--dry] [--file reviewed.json ...]

rows_index.json: row -> {jp, ids ["TABLE.CSV:r:c", ...], max_bytes, en_ui (prefill from UI)}.
Translated rows come from csvt/slice_*.out.json (or reviewed group files via --file). Every id of a
row gets the same English; rows with en_ui and no slice translation use en_ui. Checks: ASCII,
bytes <= max_bytes (the column's original maximum), placeholders unchanged.
"""
import glob
import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
D = os.path.join(ROOT, 'work', 'translation', 'en', 'csvt')
C = os.path.join(ROOT, 'work', 'translation', 'en', 'csv')
PH = re.compile(r'%[-+ #0]*\d*[dsxc%]')
# Columns the program compares with Japanese strings kept in the EBOOT (never translate):
#   SPELL c1 school -> strcmp at 0x0890399C.. (eb@0897155c/64/6c/74 stay Japanese)
#   SPELL_TEXT c1 school mirror; TRAP c4 target -> strncmp at 0x089054A4 (eb@08971748)
KEEP_COLS = {('SPELL.CSV', '1'), ('SPELL_TEXT.CSV', '1'), ('TRAP.CSV', '4')}
# Cells matched by prefix: strncmp 0x08908A70 'unused' (BGM_NAME), 0x089047B0 'circle' (EMPLOY).
KEEP_PREFIX = {'BGM_NAME.CSV': '未使用', 'EMPLOY.CSV': '○'}


def main():
    dry = '--dry' in sys.argv
    index = json.load(open(os.path.join(D, 'rows_index.json'), encoding='utf-8'))
    colmax = {}
    for p in glob.glob(os.path.join(C, '*.json')):
        if os.path.basename(p).startswith('column_spec'):
            continue
        for e in json.load(open(p, encoding='utf-8')):
            colmax[e['id']] = e['max']
    files = [a for a in sys.argv[1:] if not a.startswith('--') and sys.argv[sys.argv.index(a) - 1] == '--file']
    if not files:
        files = sorted(f for f in glob.glob(os.path.join(D, 'review_g*.json')) if not f.endswith('.en.json')) or sorted(glob.glob(os.path.join(D, 'slice_*.out.json')))
    en_row = {}
    for f in files:
        for r in json.load(open(f, encoding='utf-8')):
            if (r.get('en') or '').strip():
                en_row[r['row']] = r['en']
    ov = json.load(open(os.path.join(D, 'overrides.json'), encoding='utf-8'))
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import apply_terms
    rules = apply_terms.load_rules()

    def terms(en):                      # en_ui prefill / overrides never went through apply_terms
        for rx, to in rules:
            en = rx.sub(to, en)
        return en
    by_table = {}
    bad = 0
    for ref in index:
        en = ov.get('row:%d' % ref['row']) or en_row.get(ref['row']) or ref.get('en_ui')
        if not en:
            continue
        en = terms(en)
        ref = dict(ref, ids=[i for i in ref['ids'] if tuple(i.split(':')[0::2]) not in KEEP_COLS
                             and not (i.split(':')[0] in KEEP_PREFIX and ref['jp'].startswith(KEEP_PREFIX[i.split(':')[0]]))])
        if not ref['ids']:
            continue
        if any(ord(c) > 0x7e or (ord(c) < 0x20 and c != '\n') for c in en):
            print('row %d: non-ASCII' % ref['row']); bad += 1; continue
        if len(en.encode('ascii')) > min(colmax[i] for i in ref['ids']):
            print('row %d: %d bytes > %d' % (ref['row'], len(en), min(colmax[i] for i in ref['ids']))); bad += 1; continue
        if PH.findall(ref['jp']) != PH.findall(en):
            print('row %d: placeholders differ' % ref['row']); bad += 1; continue
        for i in ref['ids']:
            v = en
            # scrolling help ticker repeats the line with no gap: pad with 3 spaces when it fits
            if i.startswith('HELP_TEXT.CSV:') and i.endswith(':10') and len(en) + 3 <= colmax[i]:
                v = en + '   '
            by_table.setdefault(i.split(':')[0], {})[i] = v
    n = 0
    for tab, m in by_table.items():
        p = os.path.join(C, tab.replace('.CSV', '.json'))
        data = json.load(open(p, encoding='utf-8'))
        for e in data:
            if e['id'] in m:
                e['en'] = m[e['id']]
                e['max'] = max(e['max'], len(m[e['id']]))   # budget already enforced per column above
                n += 1
        if not dry:
            json.dump(data, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('%d cells %s in %d tables, %d rows rejected' % (n, 'would be filled' if dry else 'filled', len(by_table), bad))


if __name__ == '__main__':
    main()
