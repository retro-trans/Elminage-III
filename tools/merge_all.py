"""Merge every reviewed translation into the build inputs (run after tools/apply_terms.py --write).

    python tools/merge_all.py [--dry]

1. World map: wmap/review_g*.json -> scp/SCDWMAP.json (merge_dedup).
2. Chapters: chap/review_g*.json; rows whose Japanese also exists in the world map take the
   world-map English (one rendering per line across the game) -> scp/SCD*.json.
3. EBOOT UI: merge_ebt (reviewed ebt groups + EXTRA/OVERRIDE/NEVER rules) -> eboot.json.
4. CSV: merge_csv (reviewed csvt groups + overrides.json + key-column protection) -> csv/*.json.
"""
import glob
import json
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
T = os.path.join(ROOT, 'work', 'translation', 'en')
PY = sys.executable


def combined(d):
    rows = []
    for f in sorted(f for f in glob.glob(os.path.join(T, d, 'review_g*.json')) if not f.endswith('.en.json')):
        rows += json.load(open(f, encoding='utf-8'))
    return rows


def run(*args):
    print('>', ' '.join(args))
    r = subprocess.run([PY, os.path.join(ROOT, 'tools', args[0])] + list(args[1:]), cwd=ROOT)
    if r.returncode:
        raise SystemExit('failed: %s' % args[0])


def fill_by_jp(rows):
    """Script entries the dedup index missed (same Japanese under another id, or short strings
    the index filter dropped: speaker names, quest items) get the English of the same Japanese.
    wmap/supplement.json holds the dropped ones (translated by the lead)."""
    import re
    jp = re.compile('[぀-ヿ一-鿿]')
    m = {r['jp']: r['en'] for r in rows if (r.get('en') or '').strip()}
    for sp in sorted(f for f in glob.glob(os.path.join(T, 'wmap', 'supplement*.json')) if not f.endswith('.en.json')):   # + supplement_test.json
        m.update(json.load(open(sp, encoding='utf-8')))
    total = 0
    for f in sorted(glob.glob(os.path.join(T, 'scp', 'SCD*.json'))):
        if f.endswith('.en.json'):
            continue
        ents = json.load(open(f, encoding='utf-8'))
        n = 0
        for e in ents:
            if not (e.get('en') or '').strip() and jp.search(e.get('jp') or '') and e['jp'] in m:
                e['en'] = m[e['jp']]
                n += 1
        if n:
            json.dump(ents, open(f, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
            total += n
    print('filled %d script entries by matching Japanese' % total)


def main():
    dry = '--dry' in sys.argv
    build = os.path.join(ROOT, 'work', 'build')
    os.makedirs(build, exist_ok=True)

    wmap = combined('wmap')
    by_jp = {r['jp']: r['en'] for r in wmap}
    kind_jp = {r['jp']: r.get('kind') for r in wmap}
    p_w = os.path.join(build, 'wmap_reviewed.json')
    json.dump(wmap, open(p_w, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    chap = {r['row']: r for r in combined('chap')}
    index = json.load(open(os.path.join(T, 'chap', 'rows_index.json'), encoding='utf-8'))
    synced = added = 0
    out = []
    for ref in index:
        r = chap.get(ref['row'])
        if ref['jp'] in by_jp:
            if r is None:
                r = {'row': ref['row'], 'jp': ref['jp'], 'en': by_jp[ref['jp']], 'kind': ref.get('kind') or kind_jp[ref['jp']]}
                added += 1
            elif r['en'] != by_jp[ref['jp']]:
                r = dict(r, en=by_jp[ref['jp']])
                synced += 1
        if r is not None:
            out.append(r)
    print('chapters: %d rows, %d taken from the world map, %d synced to it' % (len(out), added, synced))
    p_c = os.path.join(build, 'chap_reviewed.json')
    json.dump(out, open(p_c, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    if dry:
        return
    run('merge_dedup.py', os.path.join(T, 'wmap'), 'SCDWMAP', '--file', p_w)
    run('merge_dedup.py', os.path.join(T, 'chap'), 'ALL', '--file', p_c)
    run('scp_extra.py')                 # strings reached only by offset (choices, shared lines)
    run('scp_extra_dead.py')            # strings after a jump the first sweep read as code
    fill_by_jp(wmap + out)
    run('merge_ebt.py')
    run('merge_csv.py')


if __name__ == '__main__':
    main()
