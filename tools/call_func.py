"""Call a game function from the debugger at a safe point and return v0.
    python tools/call_func.py FUNC_HEX [a0 a1 a2 a3]   (values hex)
Halts at the script dispatcher (0x0888F074), saves registers, sets pc=FUNC and ra to a
breakpoint in unused cave memory, runs, reads v0, restores every register."""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ppsspp_dbg import Emu
HALT = 0x0888F074
RET = 0x09035000          # zero-filled cave tail (never executed by the game)
def call(func, args, halt=HALT, timeout=30):
    with Emu() as e:
        e.bp_clear()
        e.bp_add(halt)
        e.resume()
        t = time.time()
        while True:
            try:
                e.wait_event('cpu.stepping', timeout=1.5)
                break
            except TimeoutError:
                if time.time() - t > 60:
                    raise
                e.press('circle')      # VM idles on message windows; advance one
        e.bp_remove(halt)
        saved = e.call('cpu.getAllRegs')['categories'][0]
        names, vals = saved['registerNames'], saved['uintValues']
        for r, v in zip(['a0', 'a1', 'a2', 'a3'], args):
            e.setreg(r, v)
        e.setreg('ra', RET)
        e.setreg('pc', func)
        regs = e.run_to(RET, timeout=timeout)
        v0 = regs['v0']
        for n, v in zip(names, vals):
            if n in ('zero',):
                continue
            e.setreg(n, v)
        e.resume()
        return v0
if __name__ == '__main__':
    f = int(sys.argv[1], 16)
    args = [int(x, 16) for x in sys.argv[2:]]
    print('v0 = %x' % call(f, args))
