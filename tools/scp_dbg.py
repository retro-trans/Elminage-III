"""Show the op trail before a parse failure: python tools/scp_dbg.py SCD01.BIN [subname]"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scp
f = sys.argv[1]
d = open(os.path.join(scp.ROOT, 'work', 'source', 'arc', 'SCP', f), 'rb').read()
for name, off, size, _ in scp.parse_dir(d):
    if len(sys.argv) > 2 and name != sys.argv[2]:
        continue
    p = off + 4; end = off + size; log = []
    try:
        while p < end:
            op_pos = p; op = d[p]; p += 1
            if op == 0xff:
                op = 0x100 + d[p]; p += 1
            sig = scp.SIGS.get(op)
            if op and sig is None:
                raise Exception('unknown op %03x' % op)
            for st in (sig or []):
                if st[0] == 'ARGS':
                    mask = d[p] | d[p + 1] << 8; q = p + 2
                    for i in range(st[1]): q += scp.ARG_SIZE[(mask >> (2 * i)) & 3]
                    p = q
                elif st[0] == 'STR': p = scp.read_str(d, p)
                elif st[0] == 'RAW': p += st[1]
            if op == 0x0d:
                while True:
                    c = d[p] | d[p + 1] << 8; p += 2
                    if c == 0xffff: p += 2; break
                    p += 2
            log.append((op_pos, op, d[op_pos:p].hex(' ')))
        continue
    except Exception as x:
        print(name, 'ERR', x, 'at %x' % p)
        for a, o, h in log[-8:]:
            print('  %x %03x %s' % (a, o, h[:90]))
        print('  next:', d[p - 2:p + 40].hex(' '))
        break
