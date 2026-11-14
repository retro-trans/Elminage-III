"""Apply work/glossary/term_replacements.json to every translation output file.

    python tools/apply_terms.py            # dry run: counts + sample diffs
    python tools/apply_terms.py --write

Rules: {"from", "to", "regex": bool}. Applied in file order (longest first, as written by the
terminology pass) to the `en` field of pilot/pilot_all.json and every */slice_*.out.json.
Run AFTER agent edits (agents work from stale copies and may reintroduce old spellings).
"""
import glob
import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
T = os.path.join(ROOT, 'work', 'translation', 'en')


def load_rules():
    rules = []
    for f in sorted(glob.glob(os.path.join(ROOT, 'work', 'glossary', 'term_replacements*.json'))):
        rules += json.load(open(f, encoding='utf-8'))
    out = []
    for r in rules:
        pat = r['from'] if r.get('regex') else re.escape(r['from'])
        out.append((re.compile(pat), r['to']))
    return out


def main():
    write = '--write' in sys.argv
    rules = load_rules()
    files = [os.path.join(T, 'pilot', 'pilot_all.json')] + sorted(glob.glob(os.path.join(T, '*', 'slice_*.out.json'))) + sorted(f for f in glob.glob(os.path.join(T, '*', 'review_g*.json')) if not f.endswith('.en.json'))
    changed = 0
    samples = []
    for f in files:
        rows = json.load(open(f, encoding='utf-8'))
        dirty = False
        for r in rows:
            en = r.get('en') or ''
            new = en
            for rx, to in rules:
                new = rx.sub(to, new)
            if new != en:
                changed += 1
                dirty = True
                if len(samples) < 12:
                    samples.append((os.path.relpath(f, T), r.get('row'), en[:90], new[:90]))
                r['en'] = new
        if dirty and write:
            json.dump(rows, open(f, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    for s in samples:
        print('%s row %s\n  - %s\n  + %s' % s)
    print('%d rows %s' % (changed, 'changed' if write else 'would change (dry run)'))


if __name__ == '__main__':
    main()
