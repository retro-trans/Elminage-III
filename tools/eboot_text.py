"""Insert translated EBOOT strings (work/translation/en/eboot.json).

For each translated string at va (original byte length L incl. NUL):
  - English (+NUL) fits in L        -> written in place, rest NUL-padded.
  - longer and the string has code xrefs / data pointers -> copied into the cave and every
    lui/addiu (or ori) pair and every data word pointing at va is repointed.
  - longer without any reference (inside a fixed-size table) -> reported, left Japanese.
Strings must be ASCII after textcodec.FIX; \\n inside UI strings is a raw 0x0A.
"""
import json
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import textcodec
from mips import Elf

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
TR = os.path.join(ROOT, 'work', 'translation', 'en', 'eboot.json')
DATA_START, DATA_END = 0x0894ED64, 0x08BC5500


def encode(en):
    for k, v in textcodec.FIX.items():
        en = en.replace(k, v)
    return textcodec.encode(en).replace(b'\x1b\x0d', b'\n')


def _hilo(v):
    lo = v & 0xffff
    return ((v + 0x8000) >> 16) & 0xffff, lo


def repoint_code(eb, elf, old, new):
    """Patch every lui/addiu|ori|lw-style pair building `old` to build `new`. Returns count."""
    n = 0
    hi_old, lo_old = _hilo(old)
    hi_new, lo_new = _hilo(new)
    a, ws = elf.words()
    for i, w in enumerate(ws):
        if w >> 26 != 0x0f or (w & 0xffff) not in (hi_old, old >> 16):
            continue
        rt = (w >> 16) & 31
        for j in range(i + 1, min(i + 12, len(ws))):
            w2 = ws[j]
            if (w2 >> 21) & 31 != rt or (w2 & 0xffff) != (old & 0xffff):
                continue
            op = w2 >> 26
            if op == 0x0d and (w & 0xffff) == old >> 16:          # lui/ori
                eb.w32(a + i * 4, (w & 0xffff0000) | (new >> 16))
                eb.w32(a + j * 4, (w2 & 0xffff0000) | (new & 0xffff))
                n += 1
            elif op == 0x09 and (w & 0xffff) == hi_old:           # lui/addiu
                eb.w32(a + i * 4, (w & 0xffff0000) | hi_new)
                eb.w32(a + j * 4, (w2 & 0xffff0000) | lo_new)
                n += 1
    return n


# Pointers whose string is shared with a different meaning elsewhere: give that one pointer its own
# English string (allocated in the cave). Applied after the normal pass.
# Monster-type table @0x089739DC: (full name, abbreviation) pointer pairs, 15 types. Four entries reuse
# strings that mean something else in English: 霊 (stored as race-style abbreviation 'Gh'), 悪魔 (tarot
# 'The Devil'), its abbreviation 悪 (alignment 'E'), 竜 (abbreviation 'Dg'), 魔術師 (tarot 'The Magician').
PTR_OVERRIDE = {
    0x08973A0C: 'Ghost',
    0x08973A14: 'Demon',
    0x08973A18: 'Dm',
    0x08973A1C: 'Dragon',
    0x08973A2C: 'Mage',
    0x089735DC: 'Mage',          # class table (name, ?, abbreviation): 魔術師 is shared with tarot 'The Magician'
}


def apply(eb, report=None):
    report = [] if report is None else report
    if not os.path.exists(TR):
        return report
    ents = [e for e in json.load(open(TR, encoding='utf-8')) if (e.get('en') or '').strip()]
    if not ents:
        return report
    elf = Elf()
    # data pointer index once
    ptrs = {}
    for va in range(DATA_START & ~3, DATA_END - 4, 4):
        v = eb.u32(va)
        if DATA_START <= v < DATA_END:
            ptrs.setdefault(v, []).append(va)
    inplace = moved = skipped = 0
    for e in ents:
        va = int(e['id'].split('@')[1], 16)
        b = encode(e['en'])
        L = e['len']
        if len(b) + 1 <= L:
            eb.write(va, b + b'\0' * (L - len(b)))
            inplace += 1
            continue
        refs = e.get('refs', 0) + e.get('ptrs', 0)
        if not refs:
            report.append('%s: needs %d bytes, slot %d, no references -> kept' % (e['id'], len(b) + 1, L))
            skipped += 1
            continue
        new = eb.alloc(b + b'\0', align=4)
        nc = repoint_code(eb, elf, va, new)
        for p in ptrs.get(va, []):
            eb.w32(p, new)
        if nc + len(ptrs.get(va, [])) == 0:
            report.append('%s: references not found when repointing' % e['id'])
        moved += 1
    for p, en in sorted(PTR_OVERRIDE.items()):
        eb.w32(p, eb.alloc(encode(en) + b'\0', align=4))
    print('  eboot strings: %d in place, %d moved to cave, %d kept (too long, unreferenced)'
          % (inplace, moved, skipped))
    return report
