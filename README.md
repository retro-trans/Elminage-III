# Elminage III — translation project

An open toolchain for translating **Elminage III: Ankoku no Shito to Taiyou no Kyuuden**
(PSP, ULJM05883), plus the English translation built with it.

## Contribute

The script, menus, item and monster data, UI artwork and the opening movie are translated,
but the game has not been played through to the end yet, and no human has proofread the
English against the Japanese. If you want to contribute to this project or the next in any
way — be it bug reports, proofreading or playtesting — please join my Discord:

**[discord.gg/MssepShjmB](https://discord.gg/MssepShjmB)**

## Play it

The latest release is **[v0.8.5](https://github.com/retro-trans/Elminage-III/releases/tag/v0.8.5)**,
a full patch for the Japanese release (**ULJM05883**): the whole script, menus, data
tables, interface artwork, the title logo and the subtitled opening movie are in English, with a variable-width font and an optional HD font chosen
when you start a new game.

### Apply

Use [Retro Trans](https://github.com/retro-trans/retro-trans-tools), or apply the `.xdelta`
with DeltaPatcher or xdelta3. You need your own Japanese disc image.

| Your source image | Patch |
|---|---|
| Japanese release, ULJM05883 | `Elminage3-English-v0.8.5.xdelta` |
| English v0.8.3 image | `Elminage3-English-v0.8.3-to-v0.8.5.xdelta` |
| English v0.8.1 image | `Elminage3-English-v0.8.1-to-v0.8.5.xdelta` |
| English v0.8.0 image | `Elminage3-English-v0.8.0-to-v0.8.5.xdelta` |

Check the source hashes in `README-v0.8.5.txt` if your patcher reports a mismatch; keep
checksum verification enabled.

For example:

```
xdelta3 -d -s "Elminage III - Ankoku no Shito to Taiyou no Kyuuden (Japan).iso" Elminage3-English-v0.8.5.xdelta "Elminage III English v0.8.5.iso"
```

**Boot the new image fresh.** Old emulator save states keep the previous executable and
scripts; in-game saves (Memory Stick) work across versions.

The patched executable is unencrypted: it runs on PPSSPP and on a PSP with custom firmware.
Do not use the game's data-install option (Memory Stick install): it would load the
untranslated archives. The patch turns the install off.

### Text font

At the start of a new game you choose the text font:

- **Original pixel font** — the default; looks right at 1x and on real hardware.
- **HD font** — a 4x rendering of [GenEi LateGo](https://okoneya.jp/font/genei-latin.html),
  sharp on PPSSPP with a hardware renderer (Vulkan, OpenGL or Direct3D) at 2x or higher
  rendering resolution. It has no benefit with the software renderer.

The choice is stored in your save. Saves from before v0.8.0 use the original font.

## Translate it

Fork it to fix the English, or to take the game into another language. The working rules
are in **[BASE_RULES.md](BASE_RULES.md)** and **[docs/translation_brief.md](docs/translation_brief.md)**;
the formats are in **[docs/formats.md](docs/formats.md)**.

```sh
python tools/extract_scp.py          # pull the script out of your own disc's SCP archive
#   ... translate the "en" fields in work/translation/en/scp/*.json ...
python tools/merge_all.py            # merge reviewed rows, EBOOT strings and data tables
python tools/build.py 0.8.5          # build work/output/Elminage III (EN) v0.8.5.iso
```

The script stays byte-for-byte in place: English goes into the freed string slots and a
small hook in the executable follows the links, so no jump offsets ever change.

You need your own copy of the game. This repository contains no disc image, no game data
and no dump of the original Japanese script. The translation files here
(`work/translation/**/*.en.json`) carry only ids, offsets and English; the tools read the
Japanese from the disc you dump yourself.

## What is here

| Path | Contents |
|---|---|
| `tools/` | 43 tools: archive and image codecs, the script VM parser, text insertion, VWF and HD font patches, the movie subtitler, the PPSSPP debugger client |
| `work/translation/en/` | the English: 36,757 script strings, 1,469 executable strings, 45 data tables |
| `work/glossary/glossary.en.json` | 479 names and terms |
| `work/ui/specs/` | 13 interface sheets: where each Japanese label sits and its English |
| `work/movie/captions.json` | the opening movie's English captions and timing |
| `docs/formats.md` | archives, scripts, fonts, the editor and the script variables |
| `docs/debug_tools.md` | the live-debugging tools and the addresses they rely on |
| `BASE_RULES.md` | portable rules for running a project like this |
| `CHANGELOG.md` | every build, what changed, and what broke |

## Using these tools

They expect your own Japanese disc image in the project folder and the files extracted
from it in `work/source/` (`tools/extract_*.py`). Python 3.8+, with numpy, Pillow,
keystone-engine and capstone; ffmpeg for the movie; xdelta3 for patches.

```sh
python tools/build.py 0.8.5                   # full build
python tools/ppsspp_dbg.py start work/output/current.iso
python tools/uv_probe.py ANIME/EL01_000.GIM   # which sprite rects a screen draws
```

## Do not sell this

This patch is free. Do not sell it, and do not sell anything made with it - no
pre-patched discs or images, no loaded memory cards or consoles, no paywalled or ad-gated
downloads.

It is an unofficial fan translation of a game Starfish-SD owns. Selling it takes money for
work that was given away, and it is the surest way to get a project like this shut down.

## Credits

We use the [GenEi LateGo font by okoneya](https://okoneya.jp/font/genei-latin.html)
(SIL Open Font License 1.1, see `docs/fonts/GenEiLatin_OFL.txt`) for the HD text font.
Thank you to its creator.

| Role | |
|---|---|
| Project lead | binhlt0402 |
| Proofreading | *none yet - see [Status](#status)* |
| Playtesting | binhlt0402 |

Translation passes, tooling and reverse engineering were done with Claude (Anthropic),
directed by binhlt0402. The translation is machine-produced and then edited - see the
release notes for what that means in practice.

## Status

The translation is in progress. `CHANGELOG.md` is the honest record, including the builds
that shipped broken and why.

Every line was machine-translated and then put through separate machine review passes
(accuracy, editorial, proofreading) with a shared glossary. **No human has proofread it
against the Japanese yet.** In-game checks so far cover the opening, town, shops, temple,
castle, Training Hall and character creation, the first dungeon and battles, the options,
and save/load; the later chapters have only been checked by scanning the built files.
