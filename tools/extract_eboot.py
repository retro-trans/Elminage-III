"""Extract Japanese strings from the EBOOT data area to work/translation/en/eboot.json.

Entry: {id: "eb@<va hex>", jp, en, len (bytes incl. NUL), refs: code xref count, ptrs: data pointer count}
Build (eboot_text.py) writes English in place when it fits (len), else into the cave and
repoints every code xref (lui/addiu pair) and data pointer. Strings with no refs at all are
reached by computed addresses (tables of fixed-size records) -> in place only.
"""
import json
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import textcodec
from mips import Elf

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DST = os.path.join(ROOT, 'work', 'translation', 'en', 'eboot.json')
DATA_START, DATA_END = 0x0894ED64, 0x08BC5500


def scan(e):
    o0, o1 = e.off(DATA_START), e.off(DATA_END - 1) + 1
    d = e.data
    res = []
    for m in re.finditer(rb'(?:[\x81-\x9f\xe0-\xef][\x40-\x7e\x80-\xfc]|[\x20-\x7e]|\x0a)+\x00', d[o0:o1]):
        b = m.group()[:-1]
        if not re.search(rb'[\x81-\x9f\xe0-\xef][\x40-\x7e\x80-\xfc]', b):
            continue
        start = o0 + m.start()
        # align: real strings usually start at a word boundary or right after a NUL
        res.append((e.va(start), b))
    return res


def main():
    e = Elf()
    strs = scan(e)
    # data pointer index
    words = {}
    o0, o1 = e.off(DATA_START), e.off(DATA_END - 1) + 1
    for o in range(o0 - (o0 % 4), o1 - 4, 4):
        v = struct.unpack_from('<I', e.data, o)[0]
        if DATA_START <= v < DATA_END:
            words.setdefault(v, []).append(e.va(o))
    old = {}
    if os.path.exists(DST):
        old = {x['id']: x for x in json.load(open(DST, encoding='utf-8'))}
    out = []
    for va, b in strs:
        txt = textcodec.decode(b.replace(b'\n', b'\x1b\x0d'))
        ent = dict(id='eb@%08x' % va, jp=txt, en='', len=len(b) + 1,
                   refs=len(e.xrefs(va)), ptrs=len(words.get(va, [])))
        o = old.get(ent['id'])
        if o and o.get('jp') == txt:
            ent['en'] = o.get('en', '')
        out.append(ent)
    os.makedirs(os.path.dirname(DST), exist_ok=True)
    json.dump(out, open(DST, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(len(out), 'strings;', sum(1 for x in out if x['refs'] or x['ptrs']), 'referenced')


if __name__ == '__main__':
    main()
