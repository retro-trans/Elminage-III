"""Boot the current build and press buttons on a schedule, saving screenshots.
python tools/autoplay.py OUTDIR [--boot] [--presses N] [--button circle] [--every K] [--delay S]"""
import os, sys, time, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ppsspp_dbg import Emu, start_emulator
ap = argparse.ArgumentParser()
ap.add_argument('out'); ap.add_argument('--boot', action='store_true')
ap.add_argument('--presses', type=int, default=30); ap.add_argument('--button', default='circle')
ap.add_argument('--every', type=int, default=3); ap.add_argument('--delay', type=float, default=1.2)
ap.add_argument('--wait', type=float, default=15)
a = ap.parse_args()
os.makedirs(a.out, exist_ok=True)
if a.boot:
    start_emulator()
    time.sleep(a.wait)
with Emu() as e:
    e.bp_clear(); e.resume()
    for i in range(a.presses):
        if i % a.every == 0:
            e.screenshot(os.path.join(a.out, 'shot_%03d.png' % i), single=1)
        e.press(a.button)
        time.sleep(a.delay)
    e.screenshot(os.path.join(a.out, 'shot_%03d.png' % a.presses), single=1)
print('done')
