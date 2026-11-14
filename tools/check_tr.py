"""Check translated rows and merge them into the per-SCD translation files.

    python tools/check_tr.py work/translation/en/pilot/slice_*.out.json [--merge]

Checks per row: {w}/{p} counts and order equal to the source, runtime inserts preserved,
ASCII only, name <= 16 chars, data <= 30 chars, encoded message <= 2000 bytes, empty en.
--merge writes 'en' into work/translation/en/scp/<file>.json (matching ids) after checks.
"""
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import text_build

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
INS = re.compile(r'\{[0-9A-F]{2}:[0-9A-F]{4}:[0-9A-F]{4}\}')


def check(r):
    jp, en = r['jp'], r.get('en') or ''
    issues = []
    if not en.strip():
        return ['empty']
    seq = lambda s: re.findall(r'\{w\}|\{p\}', s)
    if seq(jp) != seq(en):
        issues.append('wait/page codes differ: jp %s en %s' % (''.join(seq(jp)), ''.join(seq(en))))
    if sorted(INS.findall(jp)) != sorted(INS.findall(en)):
        issues.append('inserts differ')
    if any(ord(c) > 0x7e or (ord(c) < 0x20 and c != '\n') for c in en):
        issues.append('non-ASCII chars: %s' % ''.join(sorted(set(c for c in en if ord(c) > 0x7e)))[:20])
    if r['kind'] == 'name' and len(en) > 16:
        issues.append('name too long (%d)' % len(en))
    if r['kind'] == 'data' and text_build.text_width(en) > text_build.MSG_WIDTH:
        issues.append('data row wider than the box (%d px)' % text_build.text_width(en))
    try:
        b = text_build.prepare_en(en, r['kind'])
        if len(b) + 2 > text_build.MSG_MAX:
            issues.append('too long (%d bytes)' % len(b))
    except Exception as x:
        issues.append('encode error %s' % x)
    return issues


def main():
    files = [f for a in sys.argv[1:] if not a.startswith('--') for f in glob.glob(a)]
    rows = []
    for f in sorted(files):
        rows += json.load(open(f, encoding='utf-8'))
    bad = 0
    for r in rows:
        iss = check(r)
        if iss:
            bad += 1
            print('%s [%s]: %s' % (r['id'], r['kind'], '; '.join(iss)))
    print('%d rows, %d with issues' % (len(rows), bad))
    if '--merge' in sys.argv:
        by_file = {}
        for r in rows:
            if r.get('en', '').strip():
                by_file.setdefault('SCDWMAP' if 'SCD' not in r.get('file', '') else r['file'], {})[r['id']] = r['en']
        for fn, m in by_file.items():
            p = os.path.join(ROOT, 'work', 'translation', 'en', 'scp', fn + '.json')
            data = json.load(open(p, encoding='utf-8'))
            n = 0
            for e in data:
                if e['id'] in m:
                    e['en'] = m[e['id']]
                    n += 1
            json.dump(data, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
            print('merged %d rows into %s' % (n, fn))


if __name__ == '__main__':
    main()
