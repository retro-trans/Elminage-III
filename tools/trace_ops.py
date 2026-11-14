"""Trace script VM: log (op, read pointer) at the dispatcher and script starts.
python tools/trace_ops.py N_EVENTS [--press]"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ppsspp_dbg import Emu
DISPATCH = 0x0888F074   # a0 = ctx, a1 = opcode; ctx+0x528 = read ptr (already past operands? no: past opcode)
START = 0x08893D58      # a0 = ctx, a1 = sub-script ptr, a2 = id
n = int(sys.argv[1]) if len(sys.argv) > 1 else 50
with Emu() as e:
    e.bp_add(DISPATCH); e.bp_add(START)
    e.resume()
    last = time.time()
    try:
        k = 0
        while k < n:
            try:
                e.wait_event('cpu.stepping', timeout=1.5)
            except TimeoutError:
                if '--press' in sys.argv:
                    e.press('circle')
                continue
            r = e.regs()
            if r['pc'] == START:
                print('START id=%d ptr=%08x bytes=%s' % (r['a2'], r['a1'], e.read(r['a1'], 48).hex(' ')), flush=True)
            else:
                rp = e.u32(r['a0'] + 0x528)
                base = e.u32(r['a0'] + 4)
                print('op=%03x rp=%08x off=%05x mode=%d next=%s' % (r['a1'], rp, rp - base, int.from_bytes(e.read(r['a0'] + 0x312, 2), 'little'), e.read(rp, 16).hex(' ')), flush=True)
            k += 1
            e.resume()
    finally:
        e.bp_remove(DISPATCH); e.bp_remove(START); e.resume()
