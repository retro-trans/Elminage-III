# Elminage III — debug tools

Emulator: portable PPSSPP 1.20.4 copied from the local install into `work/emulator/ppsspp/`
(no `installed.txt` → memstick lives next to the exe). Config: software renderer, sound off,
remote debugger on startup. The debugger port is random; `tools/ppsspp_dbg.py` finds it from
the project emulator's PID (override with env `ELM3_PPSSPP_PORT`). Only the emulator whose exe
path is inside the project is ever started/stopped.

**Confirm button is Circle** (Japanese release).

| Tool | Purpose |
| --- | --- |
| `tools/ppsspp_dbg.py` | start/stop/status, memory r/w, regs, breakpoints, input, VRAM screenshots, RAM dump, savestates |
| `tools/autoplay.py` | boot + press a button on a schedule, screenshots per N presses |
| `tools/trace_files.py` | log archive file lookups (bp 0x08918950) |
| `tools/trace_ops.py` | log script VM ops (bp 0x0888F074) and script starts (0x08893D58) |
| `tools/membp_pcs.py` | list PCs that read a memory range |
| `tools/call_func.py` | call a game function at a safe point (script dispatcher), restore all registers |
| `tools/mips.py` | ELF loader, disassembly, xrefs, callers |
| `tools/uv_probe.py` | overwrite a UI sheet in RAM with coordinate-coded colours; a screenshot then tells exactly which texels (sprite rects) a screen shows |
| `tools/ui_regions.py`, `tools/img_text.py` | sprite regions of a GIM sheet; redraw baked-in text with the game font (specs in work/ui/specs) |
| `tools/prune_outputs.py` | after a build: older ISOs -> xdelta patches vs the original JP ISO (verified by SHA-256), max 10; rebuild with `work/xdelta/xdelta3-3.1.0-x86_64.exe -d -s "<JP ISO>" patches/<name>.xdelta <name>.iso` |
| `tools/scp_sig.py`, `tools/scp_dbg.py` | derive VM operand signatures / show trail before a parse failure |

```bash
python tools/ppsspp_dbg.py start work/output/current.iso
python tools/ppsspp_dbg.py shot work/emulator/shots/x.png
python tools/ppsspp_dbg.py reset        # clear breakpoints, resume (after an interrupted script)
python -c "import sys; sys.path.insert(0,'tools'); import ppsspp_dbg as p; p.save_state('v010_town_hanoi')"
```

## Addresses (EBOOT v1.03, decrypted ELF)
| Address | Meaning |
| --- | --- |
| 0x08918950 | find file in mounted archives (a0 = name) |
| 0x08915D58 | load file (name, …, &size); 0x089161A0.. de-obfuscation |
| 0x08974378 | Mps2 TOC key table (256 u32) |
| 0x0891BAF8 | draw string (font, x, y, color, t0, t1, str) — VWF hooks at 0x0891BB88, 0x0891BD28, 0x0891BDB4/CC |
| 0x08898808 | message window renderer (per-char); ASCII advance hooked at 0x08898B48/B54 |
| 0x0888F074 | script VM dispatcher; ctx+0x528 read ptr, ctx+4 base, ctx+0x312 text mode |
| 0x08893D58 | start script (ctx, ptr, id) |
| 0x08897804 | script string parse/copy — hooked for relocated text (`1B 7D` slots) |
| 0x08C88064 | script buffer (0x130000 bytes): SCDWMAP only (patched) |
| 0x09035600 | chapter script buffer (0x80000, EBOOT bss, patched) |
| 0x08896650 | load chapter script (a0 = index into name table 0x089670EC) |
| 0x08DB81D4 | message text buffer (0x800 bytes) |
| 0x08DBB8B4 | speaker name buffer |
| 0x08FF5600 | code cave (appended after .bss, 256 KB) |
| 0x0891B260 | archive mount / data-install check (patched: never use the MS install) |

## Screenshots
`gpu.buffer.screenshot` fails with the software renderer, so screenshots read VRAM directly:
480x272 RGBA8888, stride 512, framebuffers at VRAM+0 and VRAM+0x88000 (`single=1` picks the first).

## Savestates
Saved through PPSSPP's menu command (40034 save / 40035 load, posted to the main window; no
focus needed) and copied to `work/emulator/states/<name>.ppst`. A savestate holds the old
EBOOT and loaded scripts: after a rebuild, hot reload is still TODO (see changelog).

| State | Build | Place |
| --- | --- | --- |
| test_slot | 0.0.5 | opening, Hanoi in the plaza |

## Known limits
- Hot reload and scene preview (guide steps 6–7) not built yet.
- 20 of 574 script sub-files (mostly debug/test and 4 door/switch templates) do not parse fully;
  strings before the failure point are extracted.
- Data install (INSDIR copy to Memory Stick) would load untranslated archives — players must not
  use the install feature, or must reinstall from the patched ISO.

## Finding sprite rects of UI labels (tools/uv_probe.py)
The game crops label sprites out of the EL0x sheets with rects that are not in the EBOOT as data.
Open the screen in the emulator, then:
1. `python tools/uv_probe.py ANIME/EL01_000.GIM x work/emulator/shots/uv_x.png` (writes index = x & 0xFF and a
   unique palette into the resident sheet), then the same with y, plus one pass each with the high bit
   (x >> 8, y >> 8) — see the session notes in CHANGELOG 0.2.1 for the exact snippet.
2. Decode each screenshot pixel (r, 255 - r, 77) -> index -> source (x, y); group pixels by constant
   (src - screen) offset to get one rect per drawn sprite.
3. Reload a savestate afterwards (the sheet in RAM is destroyed).
Result for the equipment screen (EL01_000): label cells are 36x12 (24x12 for Type/Range), contiguous in
each 12px row, Japanese right-aligned inside — so a cell spans from the previous piece's right edge + 1 to
this piece's right edge.
