"""Register script strings that the first extraction missed because the sweep stopped early.

    python tools/scp_extra_dead.py         # adds entries to work/translation/en/scp/SCD*.json

The original sweep (tools/extract_scp.py) read every byte after an unconditional jump as code. After a
choice menu the game keeps its prompt and some unreferenced text there, so the sweep failed and every
later line of the sub-script was never extracted (casino card game, Rafa temple, GIAF scene, ...).
scp.parse_file(d, skip_dead=True) reads those gaps as strings and continues at the next known code
target. Strings found that way which no existing entry covers are added with the usual id
'<sub>@<file offset>' and kind msg / name / opXXX / data, speaker tracked for msg.
English is filled by translating the new entries (they have en == '').
"""
import glob
import json
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scp
import textcodec
from extract_scp import strip_term

ROOT = scp.ROOT
SRC = os.path.join(ROOT, 'work', 'source', 'arc', 'SCP')
TR = os.path.join(ROOT, 'work', 'translation', 'en', 'scp')
JP = re.compile('[ぁ-ヿ一-鿿]')


def strings_of(d):
    for s in scp.parse_file(d, skip_dead=True):
        items = []
        for p, op, parts in s['ops']:
            for k, a, b in parts:
                if k == 'STR':
                    items.append((a, b, {0x8a: 'name', 0x8b: 'msg'}.get(op, 'op%03x' % op)))
        for a, b in s['strs']:
            if d[a] == 0x8b and a + 1 < b:     # op 8B (message) read as data inside a skipped gap
                items.append((a + 1, b, 'msg'))
            else:
                items.append((a, b, 'data'))
        for a, b, kind in sorted(items):
            yield s, a, b, kind


def main():
    total = 0
    for path in sorted(glob.glob(os.path.join(TR, 'SCD*.json'))):
        if path.endswith('.en.json'):
            continue
        name = os.path.basename(path).replace('.json', '.BIN')
        d = open(os.path.join(SRC, name), 'rb').read()
        ents = json.load(open(path, encoding='utf-8'))
        cov = bytearray(len(d) + 2)
        for e in ents:
            a = int(e['id'].rsplit('@', 1)[1], 16)
            cov[a:a + e['len']] = b'\x01' * e['len']
        new, speaker = [], ''
        for s, a, b, kind in strings_of(d):
            raw = strip_term(d[a:b])
            try:
                txt = textcodec.decode(raw)
            except (struct.error, IndexError):
                continue                       # truncated escape: not a real string
            if kind == 'name':
                speaker = txt
            if not raw or any(cov[a:b]) or not JP.search(txt) or textcodec.encode(txt) != raw:
                continue
            e = dict(id='%s@%x' % (s['name'], a), kind=kind, jp=txt, en='', len=b - a)
            if kind == 'msg':
                e['speaker'] = speaker
            new.append(e)
            cov[a:b] = b'\x01' * (b - a)
        if new:
            ents += new
            json.dump(ents, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
            total += len(new)
            print('  %s: %d strings added' % (name, len(new)))
    print('%d strings registered' % total)


if __name__ == '__main__':
    main()
