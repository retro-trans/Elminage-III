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


def _writes(w):
    """Register written by instruction w (MIPS I subset used by the compiler), or None."""
    op = w >> 26
    if op == 0:                                   # R-type: rd
        return (w >> 11) & 31
    if op in (0x08, 0x09, 0x0a, 0x0b, 0x0c, 0x0d, 0x0e, 0x0f, 0x20, 0x21, 0x23, 0x24, 0x25):
        return (w >> 16) & 31                     # I-type ALU / loads: rt
    if op == 0x03:
        return 31                                 # jal: ra
    return None


def _base(w):
    """Base/source register of an I-type ALU op or load/store, else None."""
    op = w >> 26
    if op in (0x08, 0x09, 0x0a, 0x0b, 0x0c, 0x0d, 0x0e) or 0x20 <= op <= 0x2e or op in (0x31, 0x39):
        return (w >> 21) & 31
    return None


def repoint_code(eb, elf, old, new, report=None):
    """Patch every lui + addiu|ori pair that builds `old` so it builds `new`. Returns count.

    Each low-half instruction is paired with the NEAREST preceding lui of its base register (the
    first-lui-found rule paired neighbouring address loads wrongly: the trap report showed a
    fragment of the credits). A lui whose register also feeds another instruction before being
    overwritten is shared with a different address: it is left alone and reported.
    """
    n = 0
    hi_old, lo_old = _hilo(old)
    hi_new, lo_new = _hilo(new)
    a, ws = elf.words()
    for j, w2 in enumerate(ws):
        op = w2 >> 26
        if op not in (0x09, 0x0d) or (w2 & 0xffff) != (old & 0xffff):
            continue
        rs = (w2 >> 21) & 31
        want = hi_old if op == 0x09 else old >> 16
        i = None
        for k in range(j - 1, max(j - 13, -1), -1):
            wk = ws[k]
            if wk >> 26 == 0x0f and (wk >> 16) & 31 == rs:
                i = k
                break
            if _writes(wk) == rs:
                break
        if i is None or (ws[i] & 0xffff) != want:
            continue
        # other readers of the lui's register before it is overwritten
        shared = False
        for k in range(i + 1, min(i + 24, len(ws))):
            if k == j:
                if (ws[k] >> 16) & 31 == rs:      # addiu rs, rs, lo: register replaced here
                    break
                continue
            wk = ws[k]
            if _base(wk) == rs or (wk >> 26 == 0 and rs in ((wk >> 21) & 31, (wk >> 16) & 31)):
                shared = True
                break
            if _writes(wk) == rs:
                break
        if shared:
            if report is not None:
                report.append('%08x: lui at %08x is shared, not repointed' % (old, a + i * 4))
            continue
        hi_val = hi_new if op == 0x09 else new >> 16
        lo_val = lo_new if op == 0x09 else new & 0xffff
        eb.w32(a + i * 4, (ws[i] & 0xffff0000) | hi_val)
        eb.w32(a + j * 4, (w2 & 0xffff0000) | lo_val)
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
    0x089731BC: 'Access.',       # equip compare 'Typ' column (type table 0x089731A0, two accessory slots):
    0x089731C0: 'Access.',       # 'Accessory' ran into the 'Rng' label
    0x08973C94: 'Access.',       # shop category list (0x08973C7C): 'Accessory' ran into the window border
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
    moves, coded = {}, {}
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
        moves[va] = new
        if e.get('refs', 0):
            coded[va] = e['id']
        for p in ptrs.get(va, []):
            eb.w32(p, new)
        moved += 1
    # code references: one global pass over every lui/addiu pair (tools/repoint.py)
    import repoint
    base, words = elf.words()
    patches, conflicts, fixed = repoint.plan(base, words, moves)
    for i, w in patches.items():
        eb.w32(base + 4 * i, w)
    report.extend('repoint: ' + c for c in conflicts)
    report.extend('%s: code references not repointed' % coded[a] for a in sorted(set(coded) - fixed))
    for p, en in sorted(PTR_OVERRIDE.items()):
        eb.w32(p, eb.alloc(encode(en) + b'\0', align=4))
    print('  eboot strings: %d in place, %d moved to cave, %d kept (too long, unreferenced)'
          % (inplace, moved, skipped))
    return report
