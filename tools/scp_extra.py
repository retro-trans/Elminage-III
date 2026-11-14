"""Register script strings the extractor missed (reached only by offset: choice options such as
いいえ/戻る/なし, shared lines such as shared lines, some speaker names).

    python tools/scp_extra.py            # adds entries to work/translation/en/scp/SCD*.json

A candidate is a Shift-JIS segment containing Japanese, bounded by 1B 00 on both sides, not inside
any existing entry. A leading 0x8A byte is the name-box opcode, not text (the string starts after it).
Single-character segments that are not known strings are skipped (bytecode look-alikes).
New entries: id 'extra@<offset>', kind 'name' after 0x8A else 'data', len = bytes incl. 1B 00.
English is filled later by tools/merge_all.py (same Japanese elsewhere or wmap/supplement*.json).
"""
import glob
import json
import os
import re

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
TR = os.path.join(ROOT, 'work', 'translation', 'en', 'scp')
SRC = os.path.join(ROOT, 'work', 'source', 'arc', 'SCP')
JP = re.compile('[぀-ヿ一-鿿]')


def main():
    known = set()
    for f in glob.glob(os.path.join(TR, 'SCD*.json')):
        if not f.endswith('.en.json'):
            known.update(e['jp'] for e in json.load(open(f, encoding='utf-8')))
    for sp in [f for f in glob.glob(os.path.join(ROOT, 'work', 'translation', 'en', 'wmap', 'supplement*.json')) if not f.endswith('.en.json')]:
        known.update(json.load(open(sp, encoding='utf-8')))
    known = {k for k in known if len(k) > 1}   # single kanji: bytecode look-alikes
    total = 0
    for f in sorted(glob.glob(os.path.join(TR, 'SCD*.json'))):
        if f.endswith('.en.json'):
            continue
        name = os.path.basename(f).replace('.json', '.BIN')
        d = open(os.path.join(SRC, name), 'rb').read()
        ents = json.load(open(f, encoding='utf-8'))
        cov = bytearray(len(d) + 2)
        for e in ents:
            a = int(e['id'].rsplit('@', 1)[1], 16)
            cov[a:a + e['len']] = b'\x01' * e['len']
        new = []
        for m in re.finditer(rb'\x1b\x00', d):
            s = m.end()
            n = d.find(b'\x1b\x00', s)
            if n < 0 or n == s or n - s > 80 or any(cov[s:n + 2]):
                continue
            kind = 'data'
            if d[s] == 0x8A:
                s += 1
                kind = 'name'
            try:
                t = d[s:n].decode('cp932')
            except UnicodeDecodeError:
                continue
            if not JP.search(t) or any(ord(c) < 0x20 for c in t):
                continue
            if len(t) == 1 and t not in known:
                continue
            new.append({'id': 'extra@%x' % s, 'kind': kind, 'jp': t, 'en': '', 'len': n + 2 - s})
            cov[s:n + 2] = b'\x01' * (n + 2 - s)
        # pass 2: strings preceded by an operand byte instead of 1B 00 (e.g. はい after '5F 49'):
        # walk back from each uncovered terminator over Shift-JIS pairs and register only the
        # longest ending that is a known string (a bytecode pair can look like a kanji).
        def lead(b): return 0x81 <= b <= 0x9F or 0xE0 <= b <= 0xFC
        def trail(b): return 0x40 <= b <= 0xFC and b != 0x7F
        for m in re.finditer(rb'\x1b\x00', d):
            n = m.start()
            if cov[n]:
                continue
            s = n
            while s >= 2 and lead(d[s - 2]) and trail(d[s - 1]) and not cov[s - 1]:
                s -= 2
            for st in range(s, n, 2):
                try:
                    t = d[st:n].decode('cp932')
                except UnicodeDecodeError:
                    continue
                if t in known and JP.search(t):
                    kind = 'name' if st > 0 and d[st - 1] == 0x8A else 'data'
                    new.append({'id': 'extra@%x' % st, 'kind': kind, 'jp': t, 'en': '', 'len': n + 2 - st})
                    cov[st:n + 2] = b'\x01' * (n + 2 - st)
                    break
        if new:
            ents += new
            json.dump(ents, open(f, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
            total += len(new)
            print('  %s: %d strings added' % (name, len(new)))
    print('%d strings registered' % total)


if __name__ == '__main__':
    main()
