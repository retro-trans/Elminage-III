"""Global repointing of lui/addiu (lui/ori) address pairs after strings move (tools/eboot_text.py).

For every lui whose immediate can form a moved address, follow the code forward along every path
(branch targets, fall-through, delay slots, branch-likely annulment, calls) until the register is
overwritten, and collect the instructions that read it. Each reader needs a high half:
  - addiu/ori building an address that moved: the new address's high half (and its low half);
  - any other reader (unmoved address, load/store, register arithmetic): the original high half.
A lui is rewritten only when all its readers agree. Readers reached from several luis (the compiler
often hoists a lui into a branch delay slot) are covered because every lui is checked against every
reader it reaches. Disagreements are reported, not patched.
"""

LIKELY = {0x14, 0x15, 0x16, 0x17}                     # beql bnel blezl bgtzl
COND = {0x04, 0x05, 0x06, 0x07} | LIKELY
CALLEE_SAVED = set(range(16, 24)) | {28, 29, 30}


def _sx(v):
    return v - 0x10000 if v & 0x8000 else v


def writes(w):
    op = w >> 26
    if op == 0:
        f = w & 0x3f
        if f == 0x08 or f in (0x18, 0x19, 0x1a, 0x1b):     # jr, mult/div
            return None
        return (w >> 11) & 31
    if op in (0x08, 0x09, 0x0a, 0x0b, 0x0c, 0x0d, 0x0e, 0x0f) or 0x20 <= op <= 0x27:
        return (w >> 16) & 31
    if op == 0x03:
        return 31
    if op == 0x1f:                                       # SPECIAL3: seb/seh (rd), ext/ins (rt)
        return (w >> 11) & 31 if (w & 0x3f) == 0x20 else (w >> 16) & 31
    return None


def reads(w, r):
    if r == 0:
        return False
    op = w >> 26
    rs, rt = (w >> 21) & 31, (w >> 16) & 31
    if op == 0:
        return r in (rs, rt)
    if op in (0x01, 0x06, 0x07, 0x16, 0x17):
        return rs == r
    if op in (0x04, 0x05, 0x14, 0x15):
        return r in (rs, rt)
    if op in (0x08, 0x09, 0x0a, 0x0b, 0x0c, 0x0d, 0x0e) or 0x20 <= op <= 0x27:
        return rs == r
    if 0x28 <= op <= 0x2e:
        return r in (rs, rt)
    if op in (0x31, 0x35, 0x39, 0x3d):
        return rs == r
    if op == 0x1f:
        return r in (rs, rt)
    return False


def branch_target(w, i):
    op = w >> 26
    if op in COND or op == 0x01:
        return i + 1 + _sx(w & 0xffff)
    return None


BASE = [0]


def jtarget(w):
    return ((((w & 0x3ffffff) << 2) | 0x08000000) - BASE[0]) // 4


def readers(ws, start, r, limit=64):
    """Readers of register r reachable after the lui at `start`; None if the walk runs too far."""
    out, seen = set(), set()
    stack = [(start + 1, limit)]
    if start > 0:                                         # lui in a delay slot: control goes on
        p = ws[start - 1]                                 # from the branch's successors
        pop = p >> 26
        t = branch_target(p, start - 1)
        if pop == 0x02:                                   # j: continue at its target
            stack = [(jtarget(p), limit)]
        elif pop == 0x03 or (pop == 0 and (p & 0x3f) == 0x09):
            stack = [(start + 1, limit)] if r in CALLEE_SAVED else []
        elif pop == 0 and (p & 0x3f) == 0x08:
            stack = []                                    # jr
        elif t is not None:
            uncond = pop == 0x04 and ((p >> 21) & 31) == ((p >> 16) & 31)
            stack = [(t, limit)] + ([] if uncond or pop in LIKELY else [(start + 1, limit)])
    while stack:
        i, budget = stack.pop()
        if i >= len(ws) or i in seen:
            continue
        if budget <= 0:
            return None
        seen.add(i)
        w = ws[i]
        if reads(w, r):
            out.add(i)
        if writes(w) == r:
            continue
        op = w >> 26
        jump = op == 0x02 or (op == 0 and (w & 0x3f) == 0x08)
        call = op == 0x03 or (op == 0 and (w & 0x3f) == 0x09)
        t = branch_target(w, i)
        if not (jump or call or t is not None):
            stack.append((i + 1, budget - 1))
            continue
        slot = i + 1                                      # delay slot
        wsl = ws[slot]
        if reads(wsl, r):
            out.add(slot)
        slot_kills = writes(wsl) == r
        if jump:
            if op == 0x02 and not slot_kills:             # j: follow; jr: value leaves
                stack.append((jtarget(w), budget - 2))
            continue
        if call:
            if not slot_kills and r in CALLEE_SAVED:
                stack.append((slot + 1, budget - 2))
            continue
        uncond = op == 0x04 and ((w >> 21) & 31) == ((w >> 16) & 31)
        if not slot_kills:
            stack.append((t, budget - 2))
            if not uncond and op not in LIKELY:
                stack.append((slot + 1, budget - 2))
        if op in LIKELY:                                  # not taken: slot annulled
            stack.append((slot + 1, budget - 2))
    return out


def plan(base, ws, moves):
    """moves {old: new}. Returns (patches {index: word}, conflicts [str], fixed set(old))."""
    BASE[0] = base
    his = {((a + 0x8000) >> 16) & 0xffff for a in moves} | {a >> 16 for a in moves}
    patches, conflicts, fixed = {}, [], set()
    for i, w in enumerate(ws):
        if w >> 26 != 0x0f or (w & 0xffff) not in his:
            continue
        r = (w >> 16) & 31
        hi = w & 0xffff
        rd = readers(ws, i, r)
        if not rd:
            continue
        need, lows, hits = set(), {}, []
        for j in rd:
            wj = ws[j]
            op = wj >> 26
            if op in (0x09, 0x0d) and (wj >> 21) & 31 == r:
                a = ((hi << 16) + _sx(wj & 0xffff)) & 0xffffffff if op == 0x09 else (hi << 16) | (wj & 0xffff)
                if a in moves:
                    n = moves[a]
                    need.add(((n + 0x8000) >> 16) & 0xffff if op == 0x09 else n >> 16)
                    lows[j] = (wj & 0xffff0000) | (n & 0xffff)
                    hits.append(a)
                    continue
            need.add(hi)
        if not hits:
            continue
        if len(need) != 1:
            conflicts.append('lui %08x: readers need high halves %s (moved %s)' % (
                base + 4 * i, ','.join('%04x' % x for x in sorted(need)), ','.join('%08x' % a for a in hits)))
            continue
        nh = need.pop()
        neww = (w & 0xffff0000) | nh
        if patches.get(i, neww) != neww:
            conflicts.append('lui %08x patched two ways' % (base + 4 * i))
            continue
        patches[i] = neww
        for j, v in lows.items():
            if patches.get(j, v) != v:
                conflicts.append('reader %08x patched two ways' % (base + 4 * j))
            patches[j] = v
        fixed.update(hits)
    return patches, conflicts, fixed
