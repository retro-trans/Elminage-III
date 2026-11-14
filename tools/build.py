"""Build the patched ISO.

    python tools/build.py 0.1.0 [--notext] [--nohd] [--nomovie]
      (default: original + HD font, chosen at New Game; --nohd: original font only, no choice)

Output: work/output/Elminage III (EN) v<ver>.iso  (+ work/output/current.iso copy for the emulator)
Older versions are kept only as xdelta patches (see tools/release_keep.py) — max 10.
"""
import os
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import iso_patch
import mps2
from eboot import Eboot

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
ORIG_ISO = os.path.join(ROOT, 'Elminage III - Ankoku no Shito to Taiyou no Kyuuden (Japan).iso')
USR = os.path.join(ROOT, 'work', 'source', 'iso', 'PSP_GAME', 'USRDIR')
OUT = os.path.join(ROOT, 'work', 'output')
BUILD = os.path.join(ROOT, 'work', 'build')


def build(ver, opts):
    t0 = time.time()
    os.makedirs(BUILD, exist_ok=True)
    os.makedirs(OUT, exist_ok=True)
    repl = {}

    # ---- EBOOT
    eb = Eboot()
    import patches
    info = patches.apply_all(eb, opts)
    eb_path = os.path.join(BUILD, 'EBOOT.BIN')
    eb.save(eb_path)
    repl['PSP_GAME/SYSDIR/EBOOT.BIN'] = eb_path

    # ---- archives with replaced files
    for arc, files in info.get('archives', {}).items():
        d = os.path.join(BUILD, 'arc_' + arc)
        if os.path.isdir(d):
            shutil.rmtree(d)
        os.makedirs(d)
        for name, data in files.items():
            open(os.path.join(d, name), 'wb').write(data)
        out = os.path.join(BUILD, arc + '.BIN')
        mps2.build(os.path.join(USR, arc + '.BIN'), d, out)
        repl['PSP_GAME/USRDIR/%s.BIN' % arc] = out

    # opening movie with English captions (tools/movie_sub.py); same size as the original, so it is
    # written in place
    movie = os.path.join(ROOT, 'work', 'movie', 'OP_01_en.pmf')
    orig_movie = os.path.join(USR, 'MOVIE', 'OP_01.pmf')
    if 'nomovie' not in opts and os.path.exists(movie) and os.path.getsize(movie) == os.path.getsize(orig_movie):
        repl['PSP_GAME/USRDIR/MOVIE/OP_01.pmf'] = movie
        print('  movie: OP_01.pmf with English captions')
    iso = os.path.join(OUT, 'Elminage III (EN) v%s%s.iso' % (ver, ' nohd' if 'nohd' in opts else ''))
    import ppsspp_dbg
    ppsspp_dbg.stop_emulator()          # it keeps current.iso (a hard link to the ISO) open
    iso_patch.patch(ORIG_ISO, iso, repl)
    cur = os.path.join(OUT, 'current.iso')
    if os.path.exists(cur):
        os.remove(cur)
    try:
        os.link(iso, cur)
    except OSError:
        shutil.copyfile(iso, cur)
    print('built', iso, 'in %.1fs' % (time.time() - t0))
    import prune_outputs                # older ISOs -> verified xdelta patches (AGENTS.md)
    prune_outputs.main(iso)
    return iso


if __name__ == '__main__':
    ver = sys.argv[1] if len(sys.argv) > 1 else '0.0.0'
    build(ver, set(a.lstrip('-') for a in sys.argv[2:]))
