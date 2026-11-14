"""Write *.en.json copies of translation files without Japanese script text (for git).

    python tools/strip_jp.py

Translation files: keeps id, en, kind, len/max, used, status and note; drops jp/speaker (the source
text and Japanese speaker names). Japanese quoted inside notes is replaced with [JP].
jp -> en maps (wmap/supplement*.json): only ASCII keys survive.
Glossary (work/glossary/glossary.json -> glossary.en.json): term, English, type, gender, source;
the free-text notes (which quote script lines) are dropped. Japanese names and UI terms are allowed
in git (AGENTS.md); whole script lines are not.
"""
import glob
import json
import os
import re

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
KEEP = ('id', 'en', 'kind', 'len', 'max', 'used', 'status', 'note')
JP = re.compile('[　-〿ぁ-ヿ一-鿿！-｠]+')


def scrub(v):
    return JP.sub('[JP]', v) if isinstance(v, str) else v


def main():
    n = 0
    for p in glob.glob(os.path.join(ROOT, 'work', 'translation', '**', '*.json'), recursive=True):
        if p.endswith('.en.json'):
            continue
        data = json.load(open(p, encoding='utf-8'))
        if isinstance(data, dict):          # jp -> en maps (wmap/supplement*.json) or row overrides
            out = {k: v for k, v in data.items() if k.isascii()} or sorted(set(map(str, data.values())))
        else:
            out = [{k: (e[k] if k == 'en' else scrub(e[k])) for k in KEEP if k in e}
                   for e in data if isinstance(e, dict) and e.get('en')]
        json.dump(out, open(p[:-5] + '.en.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        n += 1
    g = os.path.join(ROOT, 'work', 'glossary', 'glossary.json')
    if os.path.exists(g):
        terms = [{k: e.get(k) for k in ('jp', 'en', 'type', 'gender', 'status', 'source')}
                 for e in json.load(open(g, encoding='utf-8'))]
        json.dump(terms, open(g[:-5] + '.en.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        n += 1
    print(n, 'files stripped')


if __name__ == '__main__':
    main()
