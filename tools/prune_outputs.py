"""Keep only the latest ISO in work/output; older builds become xdelta patches (AGENTS.md rule).

    python tools/prune_outputs.py [keep_iso_name]      # also run at the end of tools/build.py

For every ISO in work/output other than the newest build (and current.iso, a hard link to it):
  1. xdelta3 -e against the original Japanese ISO -> work/output/patches/<name>.xdelta
  2. decode it again and compare SHA-256 with the ISO; only on a match is the ISO deleted
     (the hash is appended to work/output/patches/SHA256SUMS.txt).
At most MAX_PATCHES patches are kept; the oldest (by version) are removed.
Rebuild an old version:  xdelta3 -d -s "<original JP ISO>" patches/<name>.xdelta "<name>.iso"
xdelta3 3.1.0 (jmacd/xdelta-gpl release, Windows x86_64) lives in work/xdelta/.
"""
import glob
import hashlib
import os
import re
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
OUT = os.path.join(ROOT, 'work', 'output')
PATCHES = os.path.join(OUT, 'patches')
XDELTA = os.path.join(ROOT, 'work', 'xdelta', 'xdelta3-3.1.0-x86_64.exe')
ORIG_ISO = os.path.join(ROOT, 'Elminage III - Ankoku no Shito to Taiyou no Kyuuden (Japan).iso')
MAX_PATCHES = 10
WINDOW = str(1 << 30)


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 24), b''):
            h.update(chunk)
    return h.hexdigest()


def version_key(name):
    m = re.search(r'v(\d+)\.(\d+)\.(\d+)', name)
    return tuple(int(x) for x in m.groups()) if m else (0, 0, 0)


def main(keep=None):
    if not os.path.exists(XDELTA):
        print('  prune: xdelta3 not found, old ISOs kept')
        return
    isos = [p for p in glob.glob(os.path.join(OUT, '*.iso')) if os.path.basename(p) != 'current.iso']
    if not isos:
        return
    keep = keep or max(isos, key=lambda p: (version_key(p), os.path.getmtime(p)))
    os.makedirs(PATCHES, exist_ok=True)
    check = os.path.join(ROOT, 'work', 'xdelta', 'check.iso')
    for iso in sorted(isos):
        if os.path.abspath(iso) == os.path.abspath(keep):
            continue
        name = os.path.splitext(os.path.basename(iso))[0]
        patch = os.path.join(PATCHES, name + '.xdelta')
        subprocess.run([XDELTA, '-e', '-f', '-9', '-B', WINDOW, '-s', ORIG_ISO, iso, patch], check=True)
        subprocess.run([XDELTA, '-d', '-f', '-B', WINDOW, '-s', ORIG_ISO, patch, check], check=True)
        a, b = sha256(iso), sha256(check)
        os.remove(check)
        if a != b:
            print('  prune: %s patch does not rebuild the ISO, ISO kept' % name)
            continue
        with open(os.path.join(PATCHES, 'SHA256SUMS.txt'), 'a') as f:
            f.write('%s  %s.iso\n' % (a, name))
        os.remove(iso)
        print('  prune: %s -> patches/%s.xdelta (%.1f MB, verified)' % (name, name, os.path.getsize(patch) / 1e6))
    patches = sorted(glob.glob(os.path.join(PATCHES, '*.xdelta')), key=version_key)
    for p in patches[:-MAX_PATCHES]:
        os.remove(p)
        print('  prune: removed old patch', os.path.basename(p))


if __name__ == '__main__':
    main(os.path.join(OUT, sys.argv[1]) if len(sys.argv) > 1 else None)
