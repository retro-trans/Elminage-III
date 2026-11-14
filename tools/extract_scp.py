"""Extract script strings to translation working files.

    python tools/extract_scp.py            # writes work/translation/en/scp/SCDxx.json (keeps existing 'en')

Entry: {id: "<sub>@<file offset hex>", kind: name|msg|op0XX|data, speaker, jp, en, len}
'len' = original byte length of the string including terminator.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scp
import textcodec

ROOT = scp.ROOT
SRC = os.path.join(ROOT, 'work', 'source', 'arc', 'SCP')
DST = os.path.join(ROOT, 'work', 'translation', 'en', 'scp')


def strip_term(b):
    if b.endswith(b'\x1b\x00'):
        return b[:-2]
    if b.endswith(b'\x00'):
        return b[:-1]
    return b


def strings_of(d):
    """Yield (sub, pos, end, kind) for every string slot, in file order."""
    for s in scp.parse_file(d):
        items = []
        for p, op, parts in s['ops']:
            for k, a, b in parts:
                if k == 'STR':
                    kind = {0x8a: 'name', 0x8b: 'msg'}.get(op, 'op%03x' % op)
                    items.append((a, b, kind))
        for a, b in s['strs']:
            items.append((a, b, 'data'))
        for a, b, kind in sorted(items):
            yield s, a, b, kind


def extract_file(fname):
    d = open(os.path.join(SRC, fname), 'rb').read()
    out = []
    speaker = ''
    bad = 0
    for s, a, b, kind in strings_of(d):
        raw = strip_term(d[a:b])
        txt = textcodec.decode(raw)
        if textcodec.encode(txt) != raw:
            bad += 1
        if kind == 'name':
            speaker = txt
            if not raw:
                speaker = ''
        if not raw:
            continue          # empty strings stay as they are
        e = dict(id='%s@%x' % (s['name'], a), kind=kind, jp=txt, en='', len=b - a)
        if kind == 'msg':
            e['speaker'] = speaker
        out.append(e)
    return out, bad


def main():
    os.makedirs(DST, exist_ok=True)
    total = 0
    for f in sorted(os.listdir(SRC)):
        ents, bad = extract_file(f)
        path = os.path.join(DST, f.replace('.BIN', '.json'))
        old = {}
        if os.path.exists(path):
            for e in json.load(open(path, encoding='utf-8')):
                old[e['id']] = e
        for e in ents:
            o = old.get(e['id'])
            if o and o.get('jp') == e['jp']:
                for k in ('en', 'note', 'status'):
                    if k in o:
                        e[k] = o[k]
        json.dump(ents, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        total += len(ents)
        print('%-12s %6d strings  roundtrip-mismatch %d' % (f, len(ents), bad))
    print('total', total)


if __name__ == '__main__':
    main()
