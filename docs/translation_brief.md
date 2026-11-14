# Translator brief — Elminage III (PSP) script text

Read `BASE_RULES.md` (project root) first; it is binding. This file adds the game's text format.

## Game context
Elminage III: Ankoku no Shito to Taiyou no Kyuuden (Starfish SD / Opera House, PSP 2011).
A first-person dungeon-crawler RPG (Wizardry-like). The player's party is a group of
adventurers created by the player; NPCs address the party as 「君たち」/「君ら」 ("you",
"you guys", "you lot"). The hub is the walled city of Algrantz on the Crestard Continent.
There is no official English release: names come from `work/glossary/glossary.json`
(all marked draft; use them exactly). A name not in the glossary: romanize it, keep it
consistent within your slice, and list it in your report under "new names".

## Row fields
- `kind`: `name` = speaker name box (short!), `msg` = dialogue/narration window,
  `data` = menu choice text or a list item (short), `opXXX` = other UI text.
- `speaker` = the Japanese speaker name of the preceding name box (context only).
- `jp` = source. Write your translation in `en`.

## Control codes (keep exactly, same order)
- `{w}`  wait for a button press, then the text continues on a NEW LINE. Never put `\n` after `{w}`.
- `{p}`  new page (always comes right after `{w}`). Keep every `{w}` and `{p}` of the source,
  in the same order, so pauses and page breaks land where the Japanese has them.
- `\n`   plain line break. You do not need to reproduce the Japanese `\n`s: English is
  word-wrapped automatically (376 px, about 50 characters per line, 3 lines per page; an
  over-full page is split automatically). Use `\n` only where a break matters.
- `{0C:0001:0001}`, `{0B:0003:0000}`, `{12:0003:0018}` etc. are runtime inserts (names,
  numbers, items). Keep them verbatim; move them where English grammar needs them.
  A `{0C:...}` insert shows a name/word of roughly 8 characters.
- Japanese quote brackets 「」 → English double quotes "…". 『』 → single quotes or italics-free
  'Title Case' for named things. The full-width space that indents continuation lines inside
  a quote is dropped.
- Plain ASCII only: straight quotes, `...` for ……, `--` for a dash. No accented letters.

## Length
- `name` rows: keep under ~16 characters.
- `data` rows used as menu choices: keep under ~30 characters.
- `msg`: no hard limit; write the full meaning first (see BASE_RULES), the build wraps it.

## Output
Write `work/translation/en/pilot/slice_N.out.json`: the same list of rows, with `en` filled
(add a `note` field on rows where you made a non-obvious call). Then write
`work/translation/en/pilot/slice_N.report.md`: rows examined vs rows in slice, new names,
decisions, uncertainties, rows left untranslated and why.
Do not edit any other file. Never print Japanese text to the console (write files instead).
