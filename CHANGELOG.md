# Changelog

## 0.8.23 (2026-11-20)
- Released as `Elminage3-English-v0.8.23.xdelta` against the Japanese ULJM05883 image (source SHA-256
  b68ce890a8fe247c0d5f3fdc5e1682c52fa9d38f71d86bf2d5e8c03841ba454f, target SHA-256
  1ee49d123b2f90c4ff612c8eac828cecb18224fd82359c1d9f976d3042f2938b), built with
  `python -m retro_trans.release build` for Retro Trans Automatic. Upgrade patch
  `Elminage3-English-v0.8.14-to-v0.8.23.xdelta` (183 KB, source_version 0.8.14, from SHA-256
  534e8d758c7c8afab7478be6b7c393bbb00bc00203f31550f3c052b02a2ec1fd) gives the same image. v0.8.23 also
  contains 0.8.15 to 0.8.22 below (0.8.15 was undone by 0.8.16).
- The menu confirm sound (O) plays at 50 % of its original volume. It is EL2PSP_SE_001, one of the 198
  VAG samples inside the executable (found in PPSSPP with a breakpoint on __sceSasSetVoice: O plays
  SE_001, cursor movement SE_003). tools/se_volume.py (new) adds 1 to the ADPCM shift of every frame,
  which halves the decoded sound exactly (decoded check: RMS ratio 0.50000, largest difference from half
  the original 8.5 of 32768); one frame already at the largest shift has its nibbles halved instead.
  Same size and addresses, data only; every place that plays SE_001 is quieter, not only menus.
- Checked: the patched sample is in memory after a fresh boot. Not listened to (emulator volume is zero).

## 0.8.22 (2026-11-20, not released on its own; included in v0.8.23)
The other two "severe" bugs on the wiki bug page (tools/bugfix.py).
- Training Hall: swapping an NPC (unique character) with a player character turned the PC into an NPC
  and the unique character into a PC (wiki: then the NPC's personality comment, extra skill and face /
  style load could be edited). NPC status belongs to the roster slot (0x6C-0x6E), not the record. With
  Square in a character list, the first pick was checked against NPC slots only in the Roster list; Edit
  Profile also lists the NPCs, so picking the NPC first and a PC second swapped the two records. The check
  now runs in every list (one instruction at 0x0884F5A0). Picking an NPC first now shows "An NPC's place
  in the list can't be changed.", the same message as picking one second.
- Checked in PPSSPP on the Training Hall with a test NPC written into slot 0x6C (the test save has no
  unique characters yet). Reproduced on the old build: NPC first, then Hiyora -> the NPC record moved into
  PC slot 9 and Hiyora into NPC slot 0x6C. With the fix: the message, no swap mode. Swapping two PCs in
  Edit Profile still works. Not checked with a real unique character.
- Wind Castle 2F (Delita): the three west-edge cells at x0, y7-9 had no outer wall (wiki: "can walk off
  the map; may freeze or be lost in stone"). They get the outer wall (0xDE, type 6) the edge has just
  north of them (PARTS/01_67.DAT, floor 53; data only). Every other open map edge on all 67 floors has a
  cell event (an exit); these three were the only ones without one.
- Not reproduced: in PPSSPP with floor 53's original map put in place of the current floor, the party
  stopped at x0 when walking west (and at x19 walking east), so this build may already block leaving the
  grid; the walls make the edge the same as every other one either way. Not checked on the real floor.
- Fresh boot of v0.8.22: the NPC check is patched in memory and the map loads with the three walls.
  Real hardware: one instruction and three data bytes; no timing change.

## 0.8.21 (2026-11-20, not released on its own; included in v0.8.23)
- Freeze at the end of a battle when a level drain (e.g. Ulmakuru) leaves a character lost (original-game
  bug, wiki "severe"). Cause: at battle end, phase 14 sub-state 1 shows "<name> has been lost." and removes
  the character with 0x0887FB04; for a member of the current party that rebuilds the battle party
  (0x088CB688), which resets the battle data block 0x08DF8298-0x08DF8A28 (0x088B97DC). The battle phase,
  sub-state and lost list live in that block, so the phase fell to 0 (idle) before the battle could finish,
  and the game sat on the battle background with an EMPTY slot, ignoring input. Fix (tools/bugfix.py,
  new): the removal at 0x088D1380 only queues the character (lost_defer); the queue is run (lost_flush)
  when the battle task finishes, at 0x088499F4 right before the hand-back to the dungeon (0x08876FC8).
  The message, the slot clear and everything else in the loss step are unchanged.
- Checked in PPSSPP on the Konnu Plains Ruins first battle (reached by playing the opening: town tour,
  audience). Reproduced on the old build: Grace with Vitality 2 and one pending drain, battle won ->
  "Grace's level dropped by 1.", then stuck (phase 0, battle flag still 1). With the fix: phases 14/1 ->
  14/4 -> 23 -> 0, battle flag cleared, back in the dungeon with Grace removed and the party closed up;
  walking and the map work. A normal battle ends exactly as before. Not checked: an actual Ulmakuru
  battle, several characters lost at once, a lost unique character (the code path is the same).
- Real hardware: about 0xD0 bytes of code and data in the code cave; no timing change.

## 0.8.20 (2026-11-20, not released on its own; included in v0.8.23)
Fixes for bugs of the original game (list: the Elminage III wiki bug page), first the small ones.
- Event 56 "Crumbling Stone Tablet" was missing from the event list when the tablet (Konnu Plains Ruins
  B1F, script 02002, sets flag 0x20E) was read before the historian at the Santorea Academy faculty
  building gave the request. The historian (29006) checks 0x20E before 0x20D (request taken = the
  event's start flag, EVENT_TEXT flg_214b), so that order finished the event (0x210, flg_214e) without
  a start flag: Fame and the completed count were given, but the list never showed it. The "told the
  historian" branch now also sets 0x20D (text_build.SCRIPT_FIXES: the op at +0x4C1 jumps to a block in
  free text space of SCD08, which sets 0x20D and 0x210 and returns to +0x4C8). Checked in the built
  file; not played through (needs both places).
- Screenshots are named EL3SS_<date>_<time> instead of the Elminage 2 prefix EL2SS_ (format string at
  0x08974280, patches.screenshot_name). Checked in the built executable.
- Fried Rice and Strawberry Shortcake descriptions said "can be sold to shops, but will never be in
  stock" twice, as the Japanese does; the first copy is removed (csvt overrides rows 2134, 2135).
- Checked, nothing to fix: every dungeon "Read it?" sign (8 scripts in SCD01/04/05) branches to the
  text on Yes and away from it on No, and the same choice op drives the New Game font menu, which
  works; the wiki's "the sign is read even after No" was not found in the scripts and needs a test in
  play. The other typos the wiki lists are in the Japanese only (the English has "Heavenly Fiend
  Asunamuchi", one spelling "Mujirod Manuscript", correct Neutral armor and Boots texts).
- Real hardware: script and data changes only.

## 0.8.19 (2026-11-19, not released on its own; included in v0.8.23)
- The 0.8.18 menu gradient only showed on the EL01_000 buttons (World Map, Inspect, Talk): every redrawn
  image is matched to its sheet's own 256-colour palette, and the town / shop / temple / castle /
  training hall sheets (EL02_001, EL02_002) have no warm whites (nearest to the cream 48 levels away),
  so the cream rows fell back to grey-white. img_text.fill_free_slots now gives the palette entries no
  unchanged pixel uses (6-13 per sheet here) to the redrawn colours the palette matches worst, weighted
  by pixel count. Applies to every redrawn sheet; colours elsewhere can only get closer to the intended
  ones. Sheets without free entries (EL02_003 battle, EL02_004 load: 1 each) already had close creams.
- Checked in play: town menu (Zeppo's Inn ... Training Hall) and Kembeck's shop menu show the gradient.
  Temple, castle, training hall, battle and load menus were not opened in this build.

## 0.8.18 (2026-11-19, not released on its own; included in v0.8.23)
- Menu buttons in their normal state get the same white -> cream gradient (img_text.MENU_TOP /
  MENU_BOTTOM, rows 3-13). These are pre-drawn images, not run-time text, which is why the 0.8.15
  shadow never reached them. Rule (img_text.is_menu_normal): 16px font, light letters (every channel
  >= 200) with a near-black outline (every channel <= 30); spec key "gradient" true/false overrides.
  It catches 160 buttons in EL01_000 (tavern / camp menus), EL02_001 (town), EL02_002 (temple, shops,
  castle), EL02_003 (battle commands), EL02_004 (load menu), EL03_003 / EL03_004 (map places). The
  outline, the highlighted state (white, coloured outline, on the light bar) and the greyed state are
  unchanged. The town / shop buttons were pale cyan (220, 240, 241) and are now white -> cream too.
- Checked in play: tavern menu and town menu (cream at the bottom of the letters, e.g. (239, 235, 216)
  -> (187, 177, 136) on the town buttons). Battle, temple, load and map buttons were not opened.

## 0.8.17 (2026-11-19, not released on its own; included in v0.8.23)
- Pixel text font ("Original pixel font"): white -> cream gradient, near-white (255, 252, 245) at the
  cap tops to cream (226, 206, 160) at the baseline, chosen from a mock-up of five colour ramps (a
  colour change shows on the nearly black panels where the 0.8.15 shade did not). tools/font_tint.py
  recolours a copy of the left-aligned sheet (work/font/FONT10_16_tint.GIM, put into ANIME by
  vwf.apply); alpha is unchanged, so widths and shapes are the same; 180 of 256 palette entries. The HD
  font is unchanged. The game multiplies the texture by the text colour, so greyed and coloured text
  is tinted the same way (not checked in play).
- Checked in play with the pixel font (switched in memory; the test save uses the HD font): the help
  line reads (240, 237, 230) at the top to (212, 193, 150) at the bottom.

## 0.8.16 (2026-11-19, not released on its own; included in v0.8.23)
- Pixel text font shadow and shade (0.8.15) removed: the menu panels are nearly black (about RGB 30,24,23),
  so the black shadow did not show and the shade was hard to see. tools/font_fx.py is gone; vwf.apply
  puts the plain left-aligned sheet back. The ISO is byte-identical to the v0.8.14 release (same SHA-256).

## 0.8.15 (2026-11-19, not released on its own; included in v0.8.23)
- Pixel text font ("Original pixel font" at New Game; FONT10_16): black drop shadow 1 px right, below
  and diagonal, and a top-to-bottom shade (full colour at the cap tops, 74 % at the baseline), the same
  look as the small label font. Baked into a copy of the sheet (tools/font_fx.py ->
  work/font/FONT10_16_fx.GIM, put into ANIME by vwf.apply); the VWF widths, the HD sheet and img_text
  still read the plain sheet, so no width or layout changes. The right shadow uses the 1 px spacing
  column each glyph already draws; shadow below row 15 (descenders) is cut by the cell. The text colour
  multiplies the texture, so greyed text keeps its grey (checked) and the shadow stays black; coloured
  text should keep its colour the same way (not checked).
  Palette: 123 of 256 entries. The HD font is unchanged.
- Checked in play with the pixel font (test save uses the HD font; switched in memory): tavern menu,
  status screen values and the help line show the shadow and shade. Image data only.

## 0.8.14 (2026-11-18)
- Released as `Elminage3-English-v0.8.14.xdelta` against the Japanese ULJM05883 image (source SHA-256
  b68ce890a8fe247c0d5f3fdc5e1682c52fa9d38f71d86bf2d5e8c03841ba454f, target SHA-256
  534e8d758c7c8afab7478be6b7c393bbb00bc00203f31550f3c052b02a2ec1fd), built with
  `python -m retro_trans.release build` for Retro Trans Automatic. Upgrade patch
  `Elminage3-English-v0.8.5-to-v0.8.14.xdelta` (48 KB, source_version 0.8.5, from SHA-256
  8ff28aad2c1e7a9a0adac7aa280cfd4142fcea2aa59fcd4b0a4ce4792ddf5445) gives the same image. v0.8.14 also
  contains 0.8.6 to 0.8.13 below (0.8.11 to 0.8.13 were tried and undone; their net change is none).
- Equip screen slot labels (Main ... Acc2) share one right edge. Acc1 ended 1 px short: the "1" glyph
  advances by one blank column more than its ink, and right alignment now uses the ink of the last letter
  (img_text, small font). Acc2 ended 2 px further right because the game draws that sprite off the grid of
  the others; its label is moved 2 px left (new spec key "dx", EL01_000).
- Checked in play: equip screen. Image data only.

## 0.8.13 (2026-11-18, not released on its own; included in v0.8.14)
- Back to the 0.8.10 small font: 1 px strokes, black inside the letters of the party bar names. The bold
  font (0.8.12) and the clear letter holes (0.8.11) were tried and dropped; their code is removed. The
  ISO is byte-identical to 0.8.10 (same SHA-256).

## 0.8.12 (2026-11-18, not released on its own; included in v0.8.14)
- Small font is bold, like the PS1 status text: each stroke is 1 px wider to the right, so letters and
  advances grow by 1 px (img_text.BOLD, bolden()). Where widening would close a 1 px gap (the bar of G, K,
  N, R, ...) that pixel is left out; m, w, M and W have hand-drawn bold forms (img_text.BOLD_GLYPHS, 7 px
  wide). Applies to the UI labels and the party bar names (FONT12_12).
- Five status screen labels are 1-2 px too wide in bold and stay at the regular weight (font '12r' in
  the spec): Title, Align, Class, Name, Type.
- Party bar names: the holes inside o, e, a, ... are black again (0.8.11 reverted); with the portrait
  showing through, the 2 px holes made the letters look thin and broken.
- Checked in play: status screen labels and party bar names. Image data only.

## 0.8.11 (2026-11-18, not released on its own; included in v0.8.14)
- Party bar names (FONT12_12): the black outline is drawn only around the outside of each letter. The
  holes inside o, e, a, g, 8, B and similar letters are 2 px wide, so the 4-neighbour outline filled them
  completely and they showed as solid black; they are now left transparent (font12._outside, a flood fill
  from the cell border) and show the portrait behind. UI labels (drop shadow, no outline) are unchanged.
- Checked in play: party bar names on the status screen. Image data only.

## 0.8.10 (2026-11-18, not released on its own; included in v0.8.14)
- Small font gets a top-to-bottom shade, like PS1 status text: full colour on the top rows, about 75 % at
  the bottom (img_text.GRADIENT by cell row). UI labels: each row's colour is matched to the sheet's own
  palette, so the middle rows lean slightly beige on the pink labels. Party bar names (FONT12_12): palette
  entries 3-14, unused in the original sheet, hold a white -> grey ramp (255 -> 189) and each letter row
  uses its own entry (font12.GRAD_BASE); the black outline is unchanged. The glyph routine passes a colour
  to the quad draw (0x0891DF40), which should multiply over the ramp; tinted names were not checked.
- Checked in play: status screen labels and party bar names show the shade. Image data only.

## 0.8.9 (2026-11-18, not released on its own; included in v0.8.14)
- The original English art labels LV, EP, HP, AC, GP (status screen, sheet EL01_000) and the two AC / HP
  pairs on the item info sheet (EL02_000) are redrawn in the small label font with its shadow, so every
  label on those screens uses one font. The art (9-15 px letters) is erased to transparent; the new labels
  sit in the same 12px strips (EL01_000 rows 279 / 291, EL02_000 row 116), centred in the gap between
  the neighbouring pieces.
- Party bar names (and any other English drawn with FONT12_12): the cells the ASCII table 0x089749C8
  points at are redrawn with the small label font in the sheet's own style (white letter, black
  4-neighbour outline; font12.build_sheet -> work/font/FONT12_12.GIM, added to ANIME by vwf.apply12).
  The 12px VWF widths are measured from the new sheet, 0 px extra spacing (the outlines keep 2 px between
  strokes). Kana and kanji cells are unchanged. img_text's '12game' font still reads the original sheet.
- Checked in play: status screen (Inspect at the tavern) shows LV/HP/AC/EP/GP in the small font, and the
  party bar names (Grace, Kanosuke, Aruna, Meme, Green, Froila) in the new font, centred, nothing
  clipped. The item info screen was not opened. Only image data and the VWF width table change.
- Build: v0.8.7 and v0.8.8 kept as xdelta patches; the oldest three patches were dropped (10 kept).

## 0.8.8 (2026-11-18, not released on its own; included in v0.8.14)
- Small-label drop shadow was not visible in play (reported on v0.8.7): it was one pixel at (+1,+1) in
  dark brown, which the sheet palette turned into (19,18,19), only about 20 levels below the dark status
  panel (40,36,26), and the emulator's screen scaling blurred it away. Now black and three pixels (right,
  below and diagonal: img_text.SHADOW_OFFS), still inside the letter's gap column and the 12px strip.
  Checked in play on the status screen: the shadow reads (2,2,2) against the panel's (40,36,26).

## 0.8.7 (2026-11-18, not released on its own; included in v0.8.14)
- Small UI labels (the 12px labels redrawn into the EL01/EL02/EL03 and GR01 sheets: status screen, item
  and monster info, equip compare, options, map legend, save/load panel) no longer use the game's
  FONT12_12, whose Latin letters are thin and widely spaced. They use the hand-drawn proportional 12px
  font from the Getter Robo Daikessen project (tools/fonts/gr_latin.txt, project original; caps rows 2-8,
  descenders to row 10) with a drop shadow in the gap column after each letter
  (tools/img_text.py FontGR; spec "font"/"fonts" '12' now means this font, the old one is '12game';
  spec key "shadow": [r, g, b] or null). All 353 small labels fit with a 1 px gap (109 had none), and
  "Title" and "Name" are no longer squeezed.
- Full words where they now fit: status screen Race, Align, Class, Luck; equip compare Type; item info
  Race, Align, Breath, Draw. Rows where some words still do not fit stay abbreviated (Mag/Pri/Alc/Sum,
  Slp/Psn/...; Sts, Str, Rng).
- Only image data changes (no code). Checked in play: save/load panel, status screen (Inspect at the
  tavern) and equip screen show the new labels with the shadow, nothing clipped. The item and monster
  info screens were not opened.

## 0.8.6 (2026-11-17, not released on its own; included in v0.8.14)
- Equip compare panel ("Now / After", 'Typ' column, type table 0x089731A0): 'Two-Handed' (85 px) and
  'Accessory' (73 px) ran into the 'Rng' label, which leaves about 64 px. Now '2-Hand' (50 px;
  merge_ebt.OVERRIDE eb@08973188, used only by this table) and 'Access.' (53 px; own pointers for the
  table's two accessory entries, eboot_text.PTR_OVERRIDE 0x089731BC / 0x089731C0, as the shop list).
  The item details screen (0x088EBB38) reads the same table and had the same overlap. Checked in play:
  shop item details of the Mop (two-handed) show 'Typ 2-Hand' clear of 'Rng M'. The equip compare
  panel was not opened.

## 0.8.5 (2026-11-16)
- Released as `Elminage3-English-v0.8.5.xdelta` against the Japanese ULJM05883 image (source SHA-256
  b68ce890a8fe247c0d5f3fdc5e1682c52fa9d38f71d86bf2d5e8c03841ba454f, target SHA-256
  8ff28aad2c1e7a9a0adac7aa280cfd4142fcea2aa59fcd4b0a4ce4792ddf5445), built with
  `python -m retro_trans.release build` for Retro Trans Automatic. Upgrade patches
  `Elminage3-English-v0.8.3-to-v0.8.5.xdelta` (7 KB, source_version 0.8.3, from SHA-256
  9922d0f26e59aabaa125e0dd9ca95e87c7a1b49574fafba826a8a98261efb8e0),
  `Elminage3-English-v0.8.1-to-v0.8.5.xdelta` (11 KB, source_version 0.8.1, from SHA-256
  ee393e1ea012cb8c0eb0c6343f9483a8858867418f116347495e4bc5d98ea581) and
  `Elminage3-English-v0.8.0-to-v0.8.5.xdelta` (31 KB, source_version 0.8.0, from SHA-256
  0d79a40eea82a005852dcccefd15beeca7e60e601e15559a61e81abbab7b10f3) give the same v0.8.5 image. v0.8.5
  also contains the 0.8.4 change below.
- Book of the Next Age passwords never worked (since v0.8.0): the name-entry confirm hook
  (name_entry ne_commit, 0x08850BEC) converted the typed full-width cells to ASCII in every editor mode,
  the password screen (mode 0x15C) included. Letters, digits and symbols became 1-byte characters, the
  6-character groups shifted, and the comparison with the stored full-width passwords (0x08856AE4,
  strcmp against the table at 0x0896401C) always failed ("Nothing happened."). The hook now leaves the
  password screen's input unchanged. Checked in the emulator: the Lucky Bag password (table entry 8),
  written into the password screen's input buffer and confirmed with the end key, is accepted ("The Book of the Next Age
  was bathed in light."). Medal passwords use the same input and confirm path (decoder 0x08896054,
  unchanged); not tested with a real medal password.

## 0.8.4 (2026-11-16, not released on its own; included in v0.8.5)
- Bestiary, Karussa (MON_TEXT 139): the Japanese entry fills the column's whole 312 bytes and breaks off
  mid-phrase in mock-archaic kana; the English copied that as "...this be ye thing called loue, i",
  which read like a clipping bug. It now ends "...called loue..." (310 bytes; "loue, is it..." would be
  317) so the trail-off reads as intended (csvt overrides row 3460). Checked in the built MON_TEXT.CSV;
  not seen in play.

## 0.8.3 (2026-11-16)
- Released as `Elminage3-English-v0.8.3.xdelta` against the Japanese ULJM05883 image (source SHA-256
  b68ce890a8fe247c0d5f3fdc5e1682c52fa9d38f71d86bf2d5e8c03841ba454f, target SHA-256
  9922d0f26e59aabaa125e0dd9ca95e87c7a1b49574fafba826a8a98261efb8e0), built with
  `python -m retro_trans.release build` for Retro Trans Automatic. Upgrade patches
  `Elminage3-English-v0.8.1-to-v0.8.3.xdelta` (10 KB, source_version 0.8.1, from SHA-256
  ee393e1ea012cb8c0eb0c6343f9483a8858867418f116347495e4bc5d98ea581) and
  `Elminage3-English-v0.8.0-to-v0.8.3.xdelta` (31 KB, source_version 0.8.0, from SHA-256
  0d79a40eea82a005852dcccefd15beeca7e60e601e15559a61e81abbab7b10f3) give the same v0.8.3 image. v0.8.3
  also contains the 0.8.2 changes below.
- Battle result ('Each surviving member gained ... EP / GP'): the numbers are drawn on their own over the
  label template, padded to 10 characters with spaces ('%10llu'). With VWF a space (5 px) is narrower
  than a digit (7-9 px), so the number's right edge moved with its digit count and ran into the EP / GP
  labels. New vwf.apply_result_numbers: the three number draws (0x088BB004, 0x088BB0A0, 0x088BB0EC) go
  through a stub that measures the line and shifts x so it ends at 15 space widths; the labels now sit
  after 16 spaces (merge_ebt.OVERRIDE eb@0896ce6c, eb@0896cea8). Space and digit widths come from the
  selected font (HD aware). Checked in the emulator by running the stub on sample numbers (1 to 8
  digits, both fonts): every number ends at x 131, label at x 136. Not seen on a real battle result
  screen (no encounter reached with the test save).
  Real hardware: one stub in the code cave, called in place of the draw routine with the same arguments.

## 0.8.2 (2026-11-16, not released on its own; included in v0.8.3)
- Description boxes (events, Molder and hint text, alchemy items, bestiary, item index): the game cuts
  these texts into fixed byte rows (28 bytes for events/alchemy, loop 0x08846CC4; 24 bytes for monster
  and item text, loops 0x08860A84 / 0x08860FD8), so English words were split ("sight / ed"). The Japanese
  laid its lines out by padding with spaces, because the CSV line reader drops line breaks inside cells;
  the English line breaks were dropped the same way and glued words together ("tofind", "itslight").
  New vwf.apply_wrap: each row is taken by wrap_line(dst, src, max_px), whole words while the VWF width
  fits (events 224 px, descriptions 200 px; HD widths when the HD font is on), byte 0x0A forces a new row.
  csv_build writes kept line breaks (blank lines, breaks after sentence-ending punctuation or a recipe
  line) as 0x1D, which the cell copy (patches.csv_text) stores as 0x0A; breaks that only copied the
  Japanese line layout become spaces, and line breaks in all other columns become spaces. Every
  translated cell was simulated with both fonts: at most 13 rows for monster/item text (box: 13) and 10
  for events/alchemy (10). MON_TEXT lore entries put 'Not for loan: ------.---' on one row; entry 319
  shortened slightly (csvt overrides row 3634). Checked in play: event list text and item index text.
  Not seen in play: bestiary text (no monsters in the test save; same code as the item text), alchemy.
- tools/ppsspp_dbg.py: the project emulator uses its own debugger port (56531) and the tool refuses a
  port shared with another process (another project's PPSSPP on the same port received our inputs).

## 0.8.1 (2026-11-15)
- Released as `Elminage3-English-v0.8.1.xdelta` against the Japanese ULJM05883 image (source SHA-256
  b68ce890a8fe247c0d5f3fdc5e1682c52fa9d38f71d86bf2d5e8c03841ba454f, target SHA-256
  ee393e1ea012cb8c0eb0c6343f9483a8858867418f116347495e4bc5d98ea581), built with
  `python -m retro_trans.release build` for Retro Trans Automatic. An upgrade patch
  `Elminage3-English-v0.8.0-to-v0.8.1.xdelta` (28 KB, source_version 0.8.0) turns the v0.8.0 image
  (SHA-256 0d79a40eea82a005852dcccefd15beeca7e60e601e15559a61e81abbab7b10f3) into the same v0.8.1 image.
- Executable text references: tools/eboot_text.py paired each moved string's low half with the FIRST
  matching lui it found, so neighbouring address loads were mixed up (and compiler-hoisted luis in branch
  delay slots were missed). 47 references in v0.8.0 pointed at the wrong text, e.g. the trap report's
  "%s" and "Unidentified" (showed "amane", the tail of a credits name), battle lines ("Reflected!",
  "had it nullified", "Resisted it", "was finished off"), target prompts, save/Memory Stick errors and
  fortune-slip lines. New tools/repoint.py follows every path from each lui (branches, delay slots,
  branch-likely, calls) to the instructions that read it and rewrites a lui only when all its readers
  agree. Checked over every lui/reader pair in the game: all addresses now resolve as intended.
- CSV commas and quotes: the game's CSV reader drops every '"' and splits at every ',' even inside quotes
  (an original designer column relies on that), so English cells with commas were cut and shifted the
  row ("Begone, Faint of Heart" became "Begone" and was hidden as a second-playthrough track, likewise
  "O God, Save Us"; 3,237 rows had changed column counts). English ',' and '"' are now written as 0x1F /
  0x1E and the game's cell copy (0x08909B44) turns them back (patches.csv_text). Checked in RAM.
- Alignment: the names read Good / Neutral / Evil (character sheet value, character creation list)
  instead of G / N / E; the item details screen (1-kanji slots, loop at 0x088EBE20) gets its own copy of
  the alignment records with the letters G / N / E (patches.alignment_letters). The roster "G-Fig" column
  and the letter shown before a personality comment keep their single letters (separate fields). Stat and
  field label abbreviations (Rce, Aln, Cls, Luk, ...) kept by choice.
- Shop: the RAN (range: Short / Medium / Long) column drew the full-width Ｓ／Ｍ／Ｌ, which only exist in
  the pixel font; they are now ASCII letters in the VWF font. The category list reads "Access." (its own
  pointer, eboot_text.PTR_OVERRIDE), so it no longer runs into the window border. Checked in play.
- Sound List / Music Folder: the fit-to-width copy (0x0891B77C) counted 10 px per half-width character,
  cutting English titles at 16 characters of the 160 px column; it now uses the VWF widths
  (vwf.apply_fit): "Let's Play Together..." fits in full.

## 0.8.0 (2026-11-14, first public release)
- First published build: the 0.2.5 work below, rebuilt as v0.8.0. Released as
  `Elminage3-English-v0.8.0.xdelta` against the Japanese ULJM05883 image
  (source SHA-256 b68ce890a8fe247c0d5f3fdc5e1682c52fa9d38f71d86bf2d5e8c03841ba454f, target SHA-256 0d79a40eea82a005852dcccefd15beeca7e60e601e15559a61e81abbab7b10f3); the patch was decoded again from the source image and
  matched the target size and hash.
- Retro Trans Automatic: the release assets were rebuilt with `python -m retro_trans.release build`
  (BUILD-MANIFEST.json schema 1, package ID PSP disc-id ULJM-05883, SHA256SUMS.txt, VALIDATION.json with a
  verified round trip; the patch bytes differ from the first upload, source and target are unchanged), and
  the game is registered in retro-trans-tools' game library (retro-trans/retro-trans-tools#3). The catalog
  refresh lists v0.8.0, and the app's own recognize/plan/apply code turns the Japanese ISO into the exact
  v0.8.0 image.
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
