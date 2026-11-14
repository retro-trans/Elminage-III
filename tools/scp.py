"""Elminage III script container (SCD*.BIN inside SCP.BIN) parser.

SCD file:
  u32 dir_size, then entries: byte t (t&0xC0: 0x80 file, 0x40 dir; t&0x3F = entry length)
  file entry: t, u32 offset, u32 size, name (NUL-padded). Name 'NNNNN...' -> script id.
Sub-script at offset: u16 0, u16 (size-6), then code; base = offset+4.
VM (EBOOT 0x0888F074): opcode u8, 0xFF xx -> 0x100+xx. Operands per scp_sigs.json:
  ARGS n: u16 type mask (2 bits/arg: 0 u8, 1 s16, 2 u32, 3 var s16) + values
  STR   : inline Shift-JIS with ESC (0x1B xx) codes, terminated by 1B 00 (or bare 00)
  RAW n : n bytes
Op 0x0D: ARGS(1) + s16 pairs (case, offset) until case 0xFFFF, then one s16.

    python tools/scp.py check            # parse every sub-script, report coverage
"""
import json
import os
import struct
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
SIGS = json.load(open(os.path.join(ROOT, 'work', 'source', 'scp_sigs.json')))
SIGS = {int(k, 16): v for k, v in SIGS.items()}
ARG_SIZE = {0: 1, 1: 2, 2: 4, 3: 2}
# ESC codes followed by 4 operand bytes (u16 type, u16 value): runtime inserts (EBOOT 0x08897804)
ESC4 = {0x0a, 0x0b, 0x0c, 0x10, 0x11, 0x12, 0x13}  # 1B 0E/0F take no operands (emit 5/6)


def parse_dir(d):
    end = struct.unpack_from('<I', d, 0)[0]
    p = 4
    out = []
    while p < end and d[p]:
        t = d[p]
        ln = t & 0x3f
        if t & 0xc0 == 0x80:
            off, size = struct.unpack_from('<II', d, p + 1)
            name = d[p + 9:p + ln].split(b'\0')[0].decode('ascii', 'replace')
            out.append((name, off, size, p))
        p += ln
    return out


def read_str(d, p):
    """Return end position (after terminator) of an inline string starting at p."""
    while True:
        b = d[p]
        if b == 0:
            return p + 1
        if b == 0x1b:
            c = d[p + 1]
            if c == 0:
                return p + 2
            p += 2 + (4 if c in ESC4 else 0)
            continue
        if 0x81 <= b <= 0x9f or 0xe0 <= b <= 0xfc:
            p += 2
        else:
            p += 1


class ParseError(Exception):
    pass


# operand index (into decoded ARGS values) that is a script-relative offset
STR_OFF_ARGS = {0x08f: [1], 0x092: [1], 0x0a2: [2], 0x10a: [1], 0x12a: [1], 0x12b: [1], 0x12d: [1], 0x12f: [0]}
CODE_OFF_ARGS = {0x008: [0], 0x00a: [0]}


def decode_args(d, p, n):
    mask = d[p] | d[p + 1] << 8
    q = p + 2
    vals = []
    for i in range(n):
        t = (mask >> (2 * i)) & 3
        if t == 0:
            v = d[q]
        elif t == 2:
            v = struct.unpack_from('<I', d, q)[0]
        else:
            v = struct.unpack_from('<H', d, q)[0]
        vals.append((t, v))
        q += ARG_SIZE[t]
    return vals, q


def parse_op(d, p):
    """Parse one op at p. Returns (op, end, parts, str_offs, code_offs)."""
    op = d[p]
    q = p + 1
    if op == 0xff:
        op = 0x100 + d[q]
        q += 1
    if op == 0:
        return op, q, [], [], []
    sig = SIGS.get(op)
    if not sig and sig != []:
        raise ParseError('unknown op %03x at %x' % (op, p))
    parts, soffs, coffs = [], [], []
    vals = []
    for step in sig:
        k = step[0]
        if k == 'ARGS':
            if step[1] is None:
                raise ParseError('op %03x ARGS(None) at %x' % (op, p))
            vals, r = decode_args(d, q, step[1])
            parts.append(('ARGS', q, r))
            q = r
        elif k == 'STR':
            r = read_str(d, q)
            parts.append(('STR', q, r))
            q = r
        elif k == 'RAW' and op != 0x092:
            parts.append(('RAW', q, q + step[1]))
            q += step[1]
        elif k == 'U8':
            parts.append(('RAW', q, q + 1))
            q += 1
    for i in STR_OFF_ARGS.get(op, []):
        if i < len(vals) and vals[i][0] == 1:
            soffs.append(vals[i][1])
    for i in CODE_OFF_ARGS.get(op, []):
        if i < len(vals) and vals[i][0] == 1:
            coffs.append(vals[i][1])
    if op == 0x092:            # choice menu: arg0 = count; each: u8, s16 text offset, s16 value
        n = vals[0][1] if vals and vals[0][0] != 3 else 0
        r = q + 5 * n
        for i in range(n):
            soffs.append(struct.unpack_from('<H', d, q + 5 * i + 1)[0])
            coffs.append(struct.unpack_from('<H', d, q + 5 * i + 3)[0])   # branch code
        parts.append(('RAW', q, r))
        q = r
    if op == 0x0d:             # switch: (case, offset) pairs until case 0xFFFF, then default offset
        r = q
        while True:
            case, off = struct.unpack_from('<HH', d, r)
            r += 4
            if case == 0xffff:
                if off != 0xffff:
                    coffs.append(off)
                break
            coffs.append(off)
        parts.append(('TAB', q, r))
        q = r
    return op, q, parts, soffs, coffs


JUMPS = (0x00a,)     # unconditional jump: the next byte need not be code


def parse_sub(d, off, size, skip_dead=False):
    """Sweep a sub-script. Returns dict(ops=[(pos, op, parts)], strs=[(pos,end)], err).

    skip_dead: after an unconditional jump/return, bytes up to the next known code target that is
    not reached otherwise are read as strings (choice prompts and unreferenced text sit there)."""
    base = off + 4
    end = off + size
    str_at, code_at = set(), {0}
    ops, strs = [], []
    p = base
    err = None
    while p < end:
        rel = p - base
        if rel in str_at and rel not in code_at:
            q = read_str(d, p)
            strs.append((p, q))
            p = q
            continue
        try:
            op, q, parts, so, co = parse_op(d, p)
        except (ParseError, IndexError, struct.error) as x:
            err = str(x)
            break
        ops.append((p, op, parts))
        str_at.update(so)
        code_at.update(co)
        p = q
        if skip_dead and op in JUMPS and (p - base) not in code_at:
            nxt = [c for c in code_at if c > p - base and base + c <= end]
            if nxt:
                t = base + min(nxt)
                while p < t:
                    r = read_str(d, p)
                    if r <= p or r > t:
                        break
                    strs.append((p, r))
                    p = r
                p = t                    # leftover non-string bytes: skip to the code target
    if not err and p != end:
        err = 'overrun %x > %x' % (p, end)
    return dict(ops=ops, strs=strs, err=err, base=base, end=end, str_at=str_at, code_at=code_at)


def parse_file(d, skip_dead=False):
    """skip_dead: re-sweep only the sub-scripts whose normal sweep fails, with dead-data skipping."""
    subs = []
    for name, off, size, dpos in parse_dir(d):
        r = parse_sub(d, off, size)
        if skip_dead and r['err']:
            r2 = parse_sub(d, off, size, True)
            if not r2['err'] or r2['ops'][-1][0] > r['ops'][-1][0]:
                r = r2
        r.update(name=name, off=off, size=size)
        subs.append(r)
    return subs


if __name__ == '__main__':
    sd = os.path.join(ROOT, 'work', 'source', 'arc', 'SCP')
    tot = bad = 0
    nstr = 0
    for f in sorted(os.listdir(sd)):
        d = open(os.path.join(sd, f), 'rb').read()
        subs = parse_file(d)
        errs = [s for s in subs if s['err']]
        tot += len(subs)
        bad += len(errs)
        nstr += sum(1 for s in subs for o in s['ops'] for pt in o[2] if pt[0] == 'STR') + sum(len(s['strs']) for s in subs)
        print(f, len(subs), 'subs', len(errs), 'errors', (errs[0]['name'] + ': ' + errs[0]['err']) if errs else '')
    print('total', tot, 'bad', bad, 'strings', nstr)
