# Changelog

## 0.8.0 (2026-11-14, first public release)
- First published build: the 0.2.5 work below, rebuilt as v0.8.0. Released as
  `Elminage3-English-v0.8.0.xdelta` against the Japanese ULJM05883 image
  (source SHA-256 b68ce890a8fe247c0d5f3fdc5e1682c52fa9d38f71d86bf2d5e8c03841ba454f, target SHA-256 0d79a40eea82a005852dcccefd15beeca7e60e601e15559a61e81abbab7b10f3); the patch was decoded again from the source image and
  matched the target size and hash.
- Repository: tools, docs and the English translation files only (`*.en.json` from tools/strip_jp.py,
  which now also scrubs Japanese quoted in notes and writes a terms-only glossary.en.json).

## 0.2.5 (2026-11-14, not a release)
- One ISO for both fonts: at the start of a New Game a popup asks for the text font ("Original pixel font",
  the default, or "HD font"). It appears over the opening's first picture (continent map), right after the
  fade-in and before the first narration line, so the town menu is no longer behind it. The choice is stored
  in script global variable 4990 (1 = original, 2 = HD; 0 = old save / not asked = original). Script:
  SCDWMAP 91101-ARG_TOP_IN.bin, the intro's call at +0x40AB (fade-in sub +0x052B) is redirected to an
  injected block (tools/text_build.py inject_font_choice). A popup shown while the screen is faded out is
  invisible, so the earlier spots (town entry, after the fade-out) were dropped.
- FONT16 now loads a second half-width sheet FONT10HD.GIM (new ANIME entry, TOC kept sorted, count updated by
  tools/mps2.py); the glyph hook switches to it, and the VWF width table has an HD half, when the variable is 2.
  Word wrap uses the per-character max of both width tables (+52 automatic page splits out of 15.5k messages).
- Load screen: the two help strings are shown on one line and ran together and past the box; now
  "Select save data to load.  Triangle: delete data." (merge_ebt OVERRIDE eb@08960120 / eb@08960148).
- Scrolling help tickers (battle command help in both modes, weather choice): the Japanese ended in a
  full-width space that separated the loop; the English now ends in 4 spaces ("...Action Order" no longer
  runs into "Choose a command").
- Battle: "1 hits!" -> "1 hit(s)!" (the count is a runtime number, eb@0896cc68).
- Checked in game on the final 0.2.5 build: battle help ticker now loops with a gap ("...L: Action Order    Choose"),
  action lines read "1 hit(s)!", load screen line fits.
- Bestiary monster types: four entries showed strings shared with other meanings ("Gh", "The Devil" with
  abbreviation "E", "Dg", "The Magician"); tools/eboot_text.py PTR_OVERRIDE now gives single pointers their own
  string: Ghost, Demon (Dm), Dragon, Mage. Long names shortened to fit the ~66 px type column: Arcane
  (魔法生物), Mythic (幻獣), Godshade (神影), Beastkin (獣人). Checked in game.
- Untranslated script text found by a static scan of the built files and fixed (about 13,000 Japanese
  characters that were never extracted): the first sweep read the bytes after an unconditional jump (op 0A)
  as code, so the rest of six sub-scripts was never extracted -- the Lumisthenes Central Council scene and
  Natori's sleep-talk (91331 / 91335 / a copy in 91442), the MILL.GP. casino dealer's blackjack lines and
  rules (91442), Mucha's Makana cake scene that unlocks mixed good/evil parties (91112), Menolist's lines in
  the Giaf scene (SCD07 92023), and the Strange Bookmark line (91143). tools/scp.py parse_file(skip_dead=True)
  re-sweeps only failing sub-scripts and reads such gaps as strings (choice-menu branch targets now count as
  code); tools/scp_extra_dead.py registers what it finds (also run by merge_all). 352 entries, 161 unique
  lines; translated, then reviewed (accuracy + editorial, 16 rows changed: titles Chief Barjeff / Council
  Chair Wattner as in the rest of the script, tone fixes), then proofread by script.
- In-engine check of the recovered text: the script VM's next message op in a tavern conversation was
  redirected (debugger) to the casino rules speech (SCDWMAP @e27de): it displays page by page with its
  waits and word wrap, all English.
- Five older fallback entries had captured only the tail of a longer string (the casino rules speech, the
  stake / change-your-mind / paid-stake lines, a Fame line): replaced by the full strings.
- Two missed EBOOT messages: "%s disarmed the trap!" and the breath-element change line (merge_ebt EXTRA_REF).
- Scan result after the fix: no Japanese left in player-visible CSV cells (5,104 English cells); every
  registered script string has English; leftovers are the developer test scripts 00101-00108, dead data after
  the last op of some battle-scene scripts ("君たちは..."), and in the EBOOT the comparison keys (spell
  schools, 当人), the name-entry keyboard tables and debug menus.
- Old outputs: xdelta3 3.1.0 (jmacd/xdelta-gpl release, work/xdelta/) turned v0.1.3-v0.2.4 (9 ISOs, ~6.6 GB)
  into patches against the original Japanese ISO in work/output/patches/ (2.5-8.5 MB each); each patch was
  decoded again and matched the ISO's SHA-256 (SHA256SUMS.txt) before the ISO was deleted. tools/build.py now
  runs tools/prune_outputs.py after every build: older ISOs -> verified patches, at most 10 patches kept.
- Class column ("G-Fig"): the alignment table @0x08973424 holds name, letter and a full-width letter; the
  column draws the full-width one, and Good/Neutral were still Ｇ/Ｎ (pixel full-width glyphs, no HD). Now ASCII
  G/N. Class abbreviations SAM/KAN -> Sam/Kan like the others. Checked in game (tavern Call Companions).
- Scrolling help text: the ticker (0x08847A38) stepped through 2-byte full-width characters 16 px at a time,
  so English jumped two letters per step and the 32-byte window stopped well short of the bar. New
  pixel-based window (vwf.apply_ticker): measures the string with the VWF widths (HD half when the HD font is
  on), starts at the character under the current pixel offset and fills the 240 px bar. Checked in game:
  smooth scroll, gap between loops, text reaches the right edge.
- Screen tour (emulator): Kembeck's shop menus, buy list and Gia's talk; Rust Temple menu, Rite of Flux
  dialogue and Yes/No; character sheets, Items, Spells, Equip; Training Hall menu and character creation --
  all English. Fixed from the tour:
  - Class list in character creation (and wherever the class table is used) said "The Magician": the class
    table's 魔術師 pointer (0x089735DC) now gets its own "Mage" (eboot_text.PTR_OVERRIDE); the tarot card
    keeps "The Magician". Ninja abbreviation NIN -> Nin.
  - Character creation labels "Epithet" and "Name" were cut off: the game crops 23/24-px cells from EL01_000
    (found with uv_probe: x384-406 and x468-491), narrower than the redrawn text. Now "Title" and "Name",
    drawn into the exact cells with a new img_text 'squeeze' option (render, resample, threshold).
  - The name-entry keyboard pages stay as in the original (fixed tables the game compares against).
- Name entry is now Latin-only with the VWF font (tools/name_entry.py): one keyboard page with A-Z,
  a-z, 0-9 and punctuation (blank cells type a space), end key "OK"; the grid and the typed text are drawn
  as ASCII through the VWF/HD font, the cursor box follows the real text width, and names are stored as
  plain ASCII (trailing spaces trimmed) so they match the rest of the English roster. Editing an existing
  English name converts it back for the editor and puts the cursor at its end. Square (random Japanese
  name) is disabled. The Book of the Next Age password screen keeps the original kana keyboard (its
  passwords are kana); that screen was not reached in testing. Tested in the emulator: register a
  character (title "Bold", name "K J" saved as ASCII in the record), backspace across fields, Edit Profile
  on Grace (cursor at end, delete and append).
- Class list in character creation was all grey: the EMPLOY.CSV parser (0x089047B0) strncmp()s each
  permission cell with the EBOOT string '○' (eb@0897164C), which had been translated to 'O', so no class
  got its sex/alignment bits (table 0x08EBCABC byte 0 all zero). '○' is now in merge_ebt NEVER; the bits
  match the original ISO again (checked in RAM). Same audit of every strncmp/strcmp with a literal key:
  '未使用' (BGM_NAME 'unused' filter, 0x08908A70) also restored; the reserved-record check at 0x0884030C
  (strncmp(name, '（', 2)) now compares 1 byte against ASCII '(' to match the English '(Reserve)' names.
- Personality comment screen: drawn through the VWF/HD font too (0x08854C20), and the single-line editor
  limits are doubled for 1-byte ASCII (title 16, name 20, nickname 12, comment 12 letters = the record
  fields and the original pixel width): editing Grace's comment no longer cuts "Naked King" to "Naked".
  The draw wrapper converts a scratch copy (converting the live buffer in place broke typing).
- Five referenced EBOOT prompts were still Japanese (the slice filter had dropped every 15-character string
  as a possible keyboard row): "No usable skills.", "Choose an item to use", "Choose a target to Dispel",
  "Choose a Swallow Slayer target", "There is no Summoner in the party." (merge_ebt EXTRA_REF). The rest of
  the referenced untranslated strings are debug/script-error messages and parser keys.
- Ticker: a line that ends with fewer than 4 spaces gets padding up to 4 when it loops, so no help line runs
  into its own start (lines under 30 bytes are shown static by the game).
- Known original-game quirk, kept: the castle's Item Index header art says "RACE" over the item category column.
  It is its own sprite (EL02_000 378,0 48x10; the bestiary uses 426,0 64x10, found with tools/uv_probe.py), but
  the original Japanese release shows the same English art, and sprite rects are not stored as data, so other
  screens using it cannot be ruled out; left as in the original.
- `--hd` builds removed; `--nohd` builds the original font only. build.py stops the emulator before writing the ISO.
- Tested in PPSSPP: popup position, both choices (variable 1 / 2), HD glyphs through the opening, save on the
  World Map > Party > Save, reboot, load: variable still 2 and no popup. Also seen in English: options screen,
  World Map tabs, Rust Temple, castle audience scene, the first dungeon (Konnu Plains Ruins) and a
  battle (commands, action lines, results screen).
- HD at 4x checked on PPSSPP Vulkan (rendering resolution 4x, window capture via PrintWindow because the
  debugger cannot read back hardware frames): 16px text uses the smooth glyphs; the 12px party-bar names stay
  pixel (only FONT16 has an HD sheet).
- Not verified: real PSP. Real hardware: +256 KB RAM for the HD sheet,
  which is always loaded.

## 0.2.4 — 2026-11-14 (not a release)
- HD build font: the 4x half-width sheet is now rendered from 源暎ラテゴ (Genei LateGo v2.1, okoneya.jp,
  SIL Open Font License 1.1 — license in docs/fonts/GenEiLatin_OFL.txt; font file in
  work/font/genei/). Size 56 at 4x, baseline row 49, horizontal scale 0.75 (widest glyphs capped at
  38 texels), 1-texel stroke so strokes survive 1/4 sampling at 1x. The HD build uses the new glyph
  widths for the EBOOT width table and the script word-wrap (vwf.TEXT_WIDTHS); UI images keep the
  pixel font. Page splits drop from 278 to 83. Normal build unchanged (original pixel font).
- Opening movie (MOVIE/OP_01.pmf) subtitled: 8 caption cards and 4 name plates
  (work/movie/captions.json) drawn over a blurred, darkened band; tools/movie_sub.py decodes each
  affected GOP (they start with IDR), re-encodes it with libx264 (Main, level 2.1, no B-frames, AUD,
  same GOP length), keeps every access unit within the original size and pads it with filler NAL
  units, then writes the ES back into the original container (tools/pmf.py) — PES layout, PTS/DTS and
  the per-GOP AU tables (0xBF) are untouched, file size identical (written in place in the ISO).
  Font for the captions: Georgia (rendered into the video, not distributed). Some GOPs with very small
  original frames needed a coarse QP (36-51) for ~1 s stretches.
- Fixed tooling: strip_jp-generated *.en.json files were picked up by merge globs.

## 0.2.3 — 2026-11-14 (not a release)
- Fixed: Hanoi's Yes/No (and 428 other はい options) still Japanese — strings preceded by an operand
  byte instead of 1B 00. tools/scp_extra.py pass 2 walks back from every uncovered 1B 00 terminator and
  registers the longest ending that is a known string (767 more: はい, speaker names such as Rianna,
  Balgert, Wattner, card-game lines, ...). All script strings are now English (3 code-only slots left).
- HD build (`python tools/build.py <ver> --hd` -> "... vX.Y.Z HD.iso"): 4x half-width font made from the
  game's own glyphs (Scale2x twice), 95 glyphs of 40x64 repacked 12 per row into 512x512 (PSP texture
  limit). Hooks: glyph routine 0x0891BE50 sets a flag for FONT16's half-width sheet, sprite routine
  0x0891DF40 remaps glyph i to (i%12*40, i/12*64) and scales the texel size by 4; screen size unchanged.
  Main RAM +224 KB, VRAM unchanged (fonts are sampled from main RAM). To keep ANIME.BIN from growing (the
  ISO patcher would append the 234 MB archive), two unused 'dummy' monster placeholders (GR08_099/100,
  512x512, 100 identical copies exist) are stored at 128x128.
- strip_jp.py handles dict files; merge tools ignore the *.en.json copies.

## 0.2.2 — 2026-11-14 (not a release)
- Fixed: choice options and other strings the script reaches only by offset were never extracted and
  stayed Japanese (e.g. はい/いいえ under Hanoi's question, 戻る/なし, (a shared "no one is here now" line), some speaker
  names). New tools/scp_extra.py registers every uncovered 1B 00-bounded Japanese string (2,845 in all
  scripts); English comes from the same Japanese elsewhere or wmap/supplement*.json. Every script
  string is now English except 3 control-code-only slots.
- Developer test scripts translated (wmap/supplement_test.json, 165 strings).
- New 4-byte slot form `1B 79 r r` (14-bit offset in 2-byte units, text placed within +-16 KB) for
  one-kanji speaker names: Voice, Samurai, Dragon, Man.
- Title logo (GR01_10301): subtitle redrawn as "Dark Apostle and the Palace of the Sun" with a glow
  like the original; reading エルミナージュ3 -> "ELMINAGE 3". img_text: erase modes clear/vcopy/inpaint,
  text glow.
- Monster-type block on EL02_000 translated (stacked two-letter codes, as EL01_000).
- Item detail screen: alignment G / N / E (Good/Neutral/Evil overlapped in kanji-width slots).

## 0.2.1 — 2026-11-14 (UI images, not a release)
- UI image sheets redrawn in English with the game's own fonts (tools/img_text.py, specs and per-sheet
  reports in work/ui/specs/): EL01_000-002 (menu buttons, skill plates, labels), EL02_000-004 (status
  labels, town/facility buttons, battle commands, chest actions, data features, sound-load tags),
  EL03_000/003/004 (options screen, map legend, place/topic buttons). EL03_002 has no Japanese.
  Not done: monster-type kanji block on EL02_000 (12px columns), title logo subtitle (GR01_10301),
  minor props listed in work/ui/japanese_images.md.
- Verified in game: tavern menu, status screen, equipment screen. Equipment slot / weapon labels moved
  into the exact cells the game crops (measured with the new tools/uv_probe.py: coordinate-coded sheet
  in RAM -> screenshot -> source texels).
- VWF space 4 -> 5 px ("Select an item." read as "anitem").
- Help ticker: HELP_TEXT lines get 3 trailing spaces when the column has room (the ticker repeats the
  line with no gap).
- CSV merge applies the term rules to UI-prefilled cells too (e.g. "Strafe Pursuit"); 追撃 = Pursuit.
- 12px font in images draws letter pixels only (the sheet's baked outline made "blob" letters).
- Gap audit (strings shown in game but still Japanese):
  - World map: 3,458 script strings filled by matching Japanese (same line under another id, plus 28
    short strings the index filter dropped — speaker names, quest items, 4 messages; translated in
    work/translation/en/wmap/supplement.json). Only the developer test scripts (TEST-OP/SF) remain.
  - CSV: help lines starting with ○ were wrongly protected as EMPLOY parser keys (3 cells, e.g. the
    shop's "Circle: Buy. Triangle: View item details.").
  - EBOOT: 17 referenced names the slice filter dropped (Royal Suite, Recovery Phase, trap names,
    Master Therion, Dungeon Load, Seirion-Daera, a credits line, ...).
- Script relocation offsets now count 2-byte units from the even-aligned slot (range +-2 MB): the
  world-map file passed 1 MB. Relocated text starts at even addresses. Hook updated accordingly.

## 0.2.0 — 2026-11-14 (full text translation, not a release)
Translation (all three review stages: accuracy, editorial, proofreading)
- Story: world map (SCDWMAP, 1,573 unique lines -> 5,418 script strings) and all chapters
  (SCD01-18/SCDDL, 1,810 unique lines -> 23,536 script strings). Chapter lines that repeat a
  world-map line use the world-map English.
- EBOOT UI/battle text: 1,452 strings (657 in place, 788 moved to the code cave).
- Data tables (ETC CSVs): 8,699 cells in 32 tables (items, monsters, bestiary, spells, skills,
  help text, events, tarot, ...), byte-exact per column budget; 36 over-long names shortened
  (work/translation/en/csvt/overrides.json).
- Terminology: glossary 408 -> 479 entries; term rules applied corpus-wide (term_replacements*.json):
  class 狩人 = Ranger, Dungeon Load, Sanctum of Genesis, Sun's Light Rank, Beastfolk, Ruu,
  Bolt Magic Seal series, appraise for 鑑定, official series spell names (73 spells,
  sources in work/glossary/spells_report.md).
Engine
- Script text: new 6-byte relocation form `1B 7A r r r L` for 6-byte slots (speaker names such
  as Guard/Underling, weather words); 4 tiny slots still Japanese (3 code-only, 1 "Man").
- Packer fix: a short string no longer fails on a small free extent ("out of text space").
- Parser keys protected: SPELL c1 / SPELL_TEXT c1 / TRAP c4 and cells starting with 未使用 / ○
  stay Japanese (compared with strcmp/strncmp at 0x0890399C, 0x089054A4, 0x08908A70,
  0x089047B0); EBOOT name-entry glyph pool 0x089694BC-0x089696C0 never written.
- Script check 0x08890C2C (strncmp of the message with 'Above the clouds'): length raised to 16,
  EBOOT key overridden to the English line. Real hardware: one immediate changed.
- 12px font (FONT12_12) VWF: converted ASCII advances by ink width (hook 0x0891BDEC / space
  0x0891BB94); party-bar names no longer use 12px per letter. Not yet verified in game.
- Race abbreviations (El, Dw, Gn, Ho, Fa, Wb, Dv, Og, Gb, Pr) and action-order marker "M" restored.
Images
- tools/img_text.py redraws text baked into GIMs with the game font; specs in work/ui/specs/.
  Done: boot disclaimer (GR01_301), first tavern/camp menu button group (EL01_000).
Known
- Most UI sheets (EL01-EL03: menu buttons, skill plates, status labels) are still Japanese;
  in progress.
- Item descriptions rely on the game's own wrapping; not yet checked in game.

## 0.1.3 — 2026-11-13 (not a release)
- Script memory: chapter scripts (SCD01-18, SCDDL) now load into their own 512 KB buffer
  (EBOOT bss after the code cave, 0x09035600); SCDWMAP keeps the whole original 1.24 MB
  buffer. Loader patched at 0x08896488. Build checks both limits: currently SCDWMAP
  985,920 / 1,245,184 and largest chapter (SCD16) 241,920 / 524,288 bytes.
- Verified by forcing a chapter load through the debugger (tools/call_func.py): SCD01 lands
  byte-exact in the new buffer, the shared counters are untouched, the game keeps running.
- Real hardware note: the module's memory size grows by 256 KB (cave) + 512 KB (buffer);
  untested on a PSP.
- Debugger: cpu.setReg needs register indices (fixed in ppsspp_dbg.setreg).

## 0.1.2 — 2026-11-13 (pilot translation, not a release)
- Pilot: the town's opening script (SCDWMAP 91101-ARG_TOP_IN, 375 strings) translated in 5
  slices, then accuracy, editorial and proofreading passes (2 + 13 + 2 rows edited).
- Fixed: script escape table — 1B 0A/0B/0C/10/11/12/13 carry 4 operand bytes, 1B 0E/0F
  carry none (highlight on/off). Script parse failures down from 20 to 9 sub-files.
- New EBOOT patch: never use / create the Memory Stick data install (ULJM05883_02_INST);
  the installed PGD archives are unpatched copies and overrode the patched font/CSV data.
- VWF: full 10px cells are drawn, only the advance comes from the width table.
- Glossary: Miria, Soara, Costo, Mucha, Toner, Santorea, Ildraha added (draft).
- Known: the world-map script grew 6.7 KB for one sub-file; script buffer has 17 KB left,
  so it must be enlarged before more of SCDWMAP is translated.

## 0.1.0 — 2026-11-13 (first framework build, not a release)
Reverse engineering
- Mps2 archives: TOC XOR key (EBOOT 0x08974378), per-file head XOR and name-keyed byte XOR
  decoded; archives rebuild byte-identical (except padding).
- Script container + VM: opcode/operand signatures derived from the EBOOT dispatcher;
  554/574 sub-scripts parse completely; 32,911 script strings extracted, all round-trip.
- CSV text tables (22,867 Japanese cells, 16,621 confirmed used at runtime) and EBOOT strings
  (12,867, 1,894 referenced) extracted.
Engine patches
- EBOOT is shipped as a plain ELF with a 256 KB code cave after .bss
  (real hardware: needs CFW; module grows by the cave size).
- Script text relocation: translated strings keep their slot size (`1B 7D` pointer + length),
  English is packed into free slot space with `1B 7E` links; hook at 0x08897804 rebuilds it.
  No script offsets change.
- VWF for half-width text in the 16px font (draw-string + message window); FONT10_16 glyphs
  left-aligned.
- Auto-wrap of English messages at 376 px, 3 lines per page (extra lines split with {w}{p}).
Tools
- PPSSPP debugger client, VRAM screenshots, savestates via menu commands, file/VM tracers,
  ISO in-place patcher, build script.
Translation
- 17 test lines of the opening (Hanoi/Fena). Draft glossary of 58 names (no official English source).
