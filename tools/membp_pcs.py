"""Collect distinct PCs that read a memory range: python tools/membp_pcs.py ADDR SIZE [hits] [--press]"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ppsspp_dbg import Emu
addr = int(sys.argv[1], 16); size = int(sys.argv[2], 16); n = int(sys.argv[3]) if len(sys.argv) > 3 else 40
seen = {}
with Emu() as e:
    e.call('memory.breakpoint.add', address=addr, size=size, enabled=True, log=False, read=True, write=False, change=False)
    try:
        e.resume()
        if '--press' in sys.argv: e.press('cross')
        for k in range(n):
            try: e.wait_event('cpu.stepping', timeout=4)
            except TimeoutError: print('timeout'); break
            r = e.regs()
            key = (r['pc'], r['ra'])
            seen[key] = seen.get(key, 0) + 1
            e.resume()
    finally:
        e.call('memory.breakpoint.remove', address=addr, size=size)
        e.resume()
for (pc, ra), c in sorted(seen.items()):
    print('pc=%08x ra=%08x x%d' % (pc, ra, c))
