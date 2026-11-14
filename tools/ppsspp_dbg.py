"""PPSSPP WebSocket debugger client for the Elminage III translation project.

Controls only the portable emulator in work/emulator/ppsspp (matched by full path).
Port comes from env ELM3_PPSSPP_PORT (default 45123, set in the portable ppsspp.ini).

Usage as a library:
    from ppsspp_dbg import Emu, start_emulator, stop_emulator
    start_emulator(iso)            # launches project PPSSPP with the ISO
    with Emu() as e:
        e.read(0x08804000, 0x100)
        e.press('cross')
        e.screenshot('shot.png')

CLI:
    python tools/ppsspp_dbg.py start [iso] [--state=file]
    python tools/ppsspp_dbg.py stop
    python tools/ppsspp_dbg.py status
    python tools/ppsspp_dbg.py reset       # clear breakpoints, resume CPU
    python tools/ppsspp_dbg.py shot out.png
    python tools/ppsspp_dbg.py press cross [frames]
    python tools/ppsspp_dbg.py dumpram out.bin   # 0x08800000..0x0A000000
"""
import base64
import json
import os
import subprocess
import sys
import time

from websockets.sync.client import connect

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
EMU_DIR = os.path.join(ROOT, 'work', 'emulator', 'ppsspp')
EMU_EXE = os.path.join(EMU_DIR, 'PPSSPPWindows64.exe')
DEFAULT_ISO = os.path.join(ROOT, 'work', 'output', 'current.iso')
ORIG_ISO = os.path.join(ROOT, 'Elminage III - Ankoku no Shito to Taiyou no Kyuuden (Japan).iso')
PORT = int(os.environ.get('ELM3_PPSSPP_PORT', '0'))  # 0 = discover from emulator PID

FB_OFFSETS = (0x0, 0x88000)   # display framebuffers inside VRAM (double buffered)

# PSP button names accepted by input.buttons.send / press
BUTTONS = ['cross', 'circle', 'triangle', 'square', 'up', 'down', 'left', 'right',
           'start', 'select', 'ltrigger', 'rtrigger', 'home']


# ---------------------------------------------------------------- process control
def _ps_lines():
    out = subprocess.run(
        ['powershell', '-NoProfile', '-Command',
         "Get-CimInstance Win32_Process -Filter \"Name='PPSSPPWindows64.exe'\" | "
         "ForEach-Object { \"$($_.ProcessId)`t$($_.ExecutablePath)\" }"],
        capture_output=True, text=True).stdout
    res = []
    for line in out.splitlines():
        if '\t' in line:
            pid, path = line.split('\t', 1)
            res.append((int(pid), path.strip()))
    return res


def emulator_pids():
    """PIDs of the project emulator only (full path match)."""
    want = os.path.normcase(os.path.abspath(EMU_EXE))
    return [pid for pid, path in _ps_lines() if path and os.path.normcase(path) == want]


def stop_emulator(timeout=15):
    for pid in emulator_pids():
        subprocess.run(['taskkill', '/PID', str(pid), '/F'], capture_output=True)
    t = time.time()
    while emulator_pids() and time.time() - t < timeout:
        time.sleep(0.3)
    return not emulator_pids()


def start_emulator(iso=None, state=None, wait=True):
    """Start the project PPSSPP (one instance only) and wait for the debugger port."""
    stop_emulator()
    iso = iso or (DEFAULT_ISO if os.path.exists(DEFAULT_ISO) else ORIG_ISO)
    args = [EMU_EXE, '--windowed']
    if state:
        args.append('--state=' + os.path.abspath(state))
    args.append(os.path.abspath(iso))
    subprocess.Popen(args, cwd=EMU_DIR)
    if wait:
        t = time.time()
        while time.time() - t < 60:
            try:
                with Emu(timeout=2) as e:
                    st = e.call('game.status')
                    if st.get('game'):
                        return True
            except Exception:
                pass
            time.sleep(0.5)
        raise RuntimeError('debugger did not come up')
    return True


def discover_port():
    """Debugger port: env ELM3_PPSSPP_PORT, else the TCP port the project emulator listens on."""
    if PORT:
        return PORT
    pids = emulator_pids()
    if not pids:
        raise RuntimeError('project emulator not running')
    out = subprocess.run(['netstat', '-ano', '-p', 'TCP'], capture_output=True, text=True).stdout
    for line in out.splitlines():
        f = line.split()
        if len(f) >= 5 and f[3] == 'LISTENING' and int(f[4]) in pids and f[1].startswith('0.0.0.0:'):
            return int(f[1].rsplit(':', 1)[1])
    raise RuntimeError('emulator has no listening port yet')


# ---------------------------------------------------------------- debugger link
class Emu:
    def __init__(self, port=None, timeout=10):
        self.port = port or discover_port()
        self.timeout = timeout
        self.ws = None
        self.ticket = 0
        self.events = []      # unsolicited events (cpu.stepping etc.)

    def __enter__(self):
        self.ws = connect('ws://127.0.0.1:%d/debugger' % self.port,
                          subprotocols=['debugger.ppsspp.org'],
                          open_timeout=self.timeout, max_size=None)
        return self

    def __exit__(self, *a):
        self.close()

    def close(self):
        if self.ws:
            self.ws.close()
            self.ws = None

    def call(self, event, timeout=None, **kw):
        self.ticket += 1
        tk = str(self.ticket)
        msg = dict(kw, event=event, ticket=tk)
        self.ws.send(json.dumps(msg))
        end = time.time() + (timeout or self.timeout)
        while True:
            left = end - time.time()
            if left <= 0:
                raise TimeoutError(event)
            r = json.loads(self.ws.recv(timeout=left))
            # cpu.stepping / cpu.resume answer with an untagged broadcast of the same name
            if event in ('cpu.stepping', 'cpu.resume') and r.get('event') == event:
                return r
            if r.get('ticket') == tk:
                if r.get('event') == 'error':
                    raise RuntimeError('%s: %s' % (event, r.get('message')))
                return r
            if r.get('event') == 'error' and r.get('ticket') is None:
                raise RuntimeError('%s: %s' % (event, r.get('message')))
            self.events.append(r)

    def wait_event(self, name, timeout=10):
        for i, ev in enumerate(self.events):
            if ev.get('event') == name:
                return self.events.pop(i)
        end = time.time() + timeout
        while True:
            left = end - time.time()
            if left <= 0:
                raise TimeoutError(name)
            r = json.loads(self.ws.recv(timeout=left))
            if r.get('event') == name:
                return r
            self.events.append(r)

    # memory ---------------------------------------------------------------
    def read(self, addr, size):
        out = bytearray()
        while size > 0:
            n = min(size, 0x100000)
            r = self.call('memory.read', address=addr, size=n, replacements=False)
            out += base64.b64decode(r['base64'])
            addr += n
            size -= n
        return bytes(out)

    def write(self, addr, data):
        for i in range(0, len(data), 0x100000):
            self.call('memory.write', address=addr + i,
                      base64=base64.b64encode(data[i:i + 0x100000]).decode())

    def u32(self, addr):
        return int.from_bytes(self.read(addr, 4), 'little')

    def w32(self, addr, v):
        self.write(addr, (v & 0xffffffff).to_bytes(4, 'little'))

    # cpu ------------------------------------------------------------------
    def status(self):
        return self.call('cpu.status')

    def stepping(self):
        return bool(self.status().get('stepping'))

    def pause(self):
        if not self.stepping():
            self.call('cpu.stepping')

    def resume(self):
        if self.stepping():
            self.call('cpu.resume')

    def regs(self):
        r = self.call('cpu.getAllRegs')
        gpr = r['categories'][0]
        return dict(zip(gpr['registerNames'], gpr['uintValues']))

    REG_NAMES = ['zero', 'at', 'v0', 'v1', 'a0', 'a1', 'a2', 'a3', 't0', 't1', 't2', 't3', 't4', 't5',
                 't6', 't7', 's0', 's1', 's2', 's3', 's4', 's5', 's6', 's7', 't8', 't9', 'k0', 'k1',
                 'gp', 'sp', 'fp', 'ra', 'pc', 'hi', 'lo']

    def setreg(self, name, value):
        """cpu.setReg wants the register index (names are rejected)."""
        idx = name if isinstance(name, int) else self.REG_NAMES.index(name)
        self.call('cpu.setReg', category=0, register=idx, value=value & 0xffffffff)

    def bp_add(self, addr, cond=None):
        kw = dict(address=addr, enabled=True, log=False)
        if cond:
            kw['condition'] = cond
        self.call('cpu.breakpoint.add', **kw)

    def bp_remove(self, addr):
        try:
            self.call('cpu.breakpoint.remove', address=addr)
        except RuntimeError:
            pass

    def bp_clear(self):
        for bp in self.call('cpu.breakpoint.list').get('breakpoints', []):
            self.bp_remove(bp['address'])

    def run_to(self, addr, timeout=10, cond=None):
        """Set a temporary breakpoint, resume, wait for the hit, return regs."""
        self.bp_add(addr, cond)
        self.events = [e for e in self.events if e.get('event') != 'cpu.stepping']
        self.resume()
        try:
            self.wait_event('cpu.stepping', timeout)
        finally:
            self.bp_remove(addr)
        return self.regs()

    def disasm(self, addr, count=32):
        r = self.call('memory.disasm', address=addr, count=count)
        return [(l['address'], l['name'] + ' ' + l['params']) for l in r['lines']]

    # input / video -------------------------------------------------------
    def press(self, button, frames=4):
        """Hold a button ~frames/60 s then release (send down/up; safe while breakpoints stop the CPU)."""
        self.call('input.buttons.send', buttons={button: True})
        time.sleep(max(frames, 4) / 60.0 + 0.03)
        self.call('input.buttons.send', buttons={button: False})

    def hold(self, buttons):
        self.call('input.buttons.send', buttons={b: True for b in buttons})

    def release_all(self):
        self.call('input.buttons.send', buttons={b: False for b in BUTTONS})

    def screenshot(self, path, single=0):
        """Capture both framebuffers from emulated VRAM (software renderer), side by side.

        The API screenshot call fails with the software renderer, so read VRAM:
        the game double-buffers 480x272 RGBA8888, stride 512, at VRAM+0 and VRAM+0x88000.
        """
        import numpy as np
        from PIL import Image
        was_running = not self.stepping()
        if was_running:
            self.call('cpu.stepping')
        try:
            v = self.read(0x04000000, 0x110000)
        finally:
            if was_running:
                self.call('cpu.resume')
        a = np.frombuffer(v, dtype=np.uint8)
        frames = [a[o:o + 512 * 272 * 4].reshape(272, 512, 4)[:, :480, :3] for o in FB_OFFSETS]
        img = np.concatenate(frames, axis=1) if not single else frames[single - 1]
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        Image.fromarray(img).save(path)
        return path


def reset_debugger():
    """Clear breakpoints and resume: recovery after an interrupted script."""
    with Emu() as e:
        e.bp_clear()
        e.release_all()
        e.resume()


if __name__ == '__main__':
    a = sys.argv[1:]
    cmd = a[0] if a else 'status'
    if cmd == 'start':
        iso = next((x for x in a[1:] if not x.startswith('--')), None)
        st = next((x.split('=', 1)[1] for x in a[1:] if x.startswith('--state=')), None)
        start_emulator(iso, st)
        print('started')
    elif cmd == 'stop':
        print('stopped' if stop_emulator() else 'still running')
    elif cmd == 'status':
        print('pids', emulator_pids())
        with Emu() as e:
            print(e.call('game.status'), e.status())
    elif cmd == 'reset':
        reset_debugger()
        print('ok')
    elif cmd == 'shot':
        with Emu() as e:
            print(e.screenshot(a[1]))
    elif cmd == 'press':
        with Emu() as e:
            e.press(a[1], int(a[2]) if len(a) > 2 else 4)
    elif cmd == 'dumpram':
        with Emu() as e:
            e.pause()
            d = e.read(0x08800000, 0x01800000)
            e.resume()
        open(a[1], 'wb').write(d)
        print(len(d))


# ---------------------------------------------------------------- savestates (menu commands, no focus needed)
STATE_DIR = os.path.join(ROOT, 'work', 'emulator', 'states')
SLOT_DIR = os.path.join(EMU_DIR, 'memstick', 'PSP', 'PPSSPP_STATE')
CMD_SAVE_STATE, CMD_LOAD_STATE = 40034, 40035


def _main_window():
    import ctypes
    import ctypes.wintypes as wt
    user32 = ctypes.windll.user32
    pids = emulator_pids()
    found = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def cb(h, l):
        pid = wt.DWORD()
        user32.GetWindowThreadProcessId(h, ctypes.byref(pid))
        if pid.value in pids and user32.IsWindowVisible(h) and user32.GetMenu(h):
            found.append(h)
        return True
    user32.EnumWindows(cb, 0)
    if not found:
        raise RuntimeError('emulator window not found')
    return found[0], user32


def _slot_file():
    fs = [os.path.join(SLOT_DIR, f) for f in os.listdir(SLOT_DIR) if f.endswith('.ppst')] if os.path.isdir(SLOT_DIR) else []
    return max(fs, key=os.path.getmtime) if fs else None


def save_state(name, timeout=15):
    """Save to the current slot via the menu, then copy to work/emulator/states/<name>.ppst."""
    import shutil
    h, user32 = _main_window()
    old = _slot_file()
    old_t = os.path.getmtime(old) if old else 0
    user32.PostMessageW(h, 0x0111, CMD_SAVE_STATE, 0)
    t = time.time()
    while time.time() - t < timeout:
        f = _slot_file()
        if f and os.path.getmtime(f) > old_t:
            time.sleep(1.0)
            os.makedirs(STATE_DIR, exist_ok=True)
            dst = os.path.join(STATE_DIR, name + '.ppst')
            shutil.copyfile(f, dst)
            return dst
        time.sleep(0.3)
    raise TimeoutError('savestate not written')


def load_state(name):
    """Copy work/emulator/states/<name>.ppst into the current slot and load it via the menu."""
    import shutil
    src = name if os.path.exists(name) else os.path.join(STATE_DIR, name + '.ppst')
    f = _slot_file()
    if not f:
        raise RuntimeError('no slot file yet: save a state once first')
    shutil.copyfile(src, f)
    h, user32 = _main_window()
    user32.PostMessageW(h, 0x0111, CMD_LOAD_STATE, 0)
    time.sleep(2.0)
