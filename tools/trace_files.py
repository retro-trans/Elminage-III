"""Log every file the game looks up in its Mps2 archives (bp on 0x08918950, a0 = name).

    python tools/trace_files.py SECONDS [--reset] [--press cross,every_n_hits]
"""
import sys, time
import os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ppsspp_dbg import Emu

LOOKUP = 0x08918950   # find file in mounted archives: a0 = char *name

def main():
    secs = float(sys.argv[1]) if len(sys.argv) > 1 else 30
    with Emu() as e:
        if '--reset' in sys.argv:
            e.call('game.reset')
            time.sleep(1)
        e.bp_add(LOOKUP)
        e.resume()
        end = time.time() + secs
        seen = []
        last_press = time.time()
        try:
            while time.time() < end:
                try:
                    e.wait_event('cpu.stepping', timeout=1.0)
                except TimeoutError:
                    if '--press' in sys.argv and time.time() - last_press > 1.5:
                        e.press('circle'); last_press = time.time()
                    continue
                r = e.regs()
                name = e.read(r['a0'], 40).split(b'\0')[0].decode('ascii', 'replace')
                ra = r['ra']
                seen.append((name, ra))
                print('%-24s ra=%08x' % (name, ra), flush=True)
                e.resume()
        finally:
            e.bp_remove(LOOKUP)
            e.resume()

main()
