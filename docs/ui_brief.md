# Translator brief — Elminage III EBOOT UI strings

Read `BASE_RULES.md` and `docs/translation_brief.md` first (game context, glossary rules).
These rows are strings built into the game program: menu labels, battle/status messages,
item-effect labels, prompts, error messages, the alchemy/compass/save screens, and staff credits.

## Fields
- `kind`: `ui` (menus, messages) or `credits` (staff roll; romanize Japanese person names in
  Western order with Hepburn, translate job titles, keep the leading full-width spaces' layout
  as plain ASCII spaces).
- `max_bytes`: when set, the English must fit in this many bytes (ASCII = 1 byte per character).
  The string sits inside a fixed-size table and cannot move. Abbreviate if needed
  ("Atk", "Def", "HP", "MP", "Lv", "Str"). When `null`, there is no hard limit, but keep menu labels
  short: aim for no more than the Japanese width in half-width columns (one Japanese
  character = two columns).
- `dupes`: how many places use the string.

## Format
- Keep printf placeholders exactly and in the same order: `%s`, `%d`, `%2d`, `%05d`, `%x`, `%c`...
  If English grammar needs a different order, rephrase instead of reordering placeholders.
- `{0D}`-style tags: none here. A real line break is `\n` (keep the same number of lines as the
  source unless the line gets too long; message lines hold about 46 half-width characters).
- Single full-width punctuation labels (？ －) stay as ASCII equivalents (? -).
- Brackets 【武】 etc. are category tags in item-effect lists: render as short ASCII tags such as
  `[Wpn]`, `[Arm]`, `[All]` — be consistent across the slice and record your tag set in the report.
- Japanese-only strings used for kana/kanji input tables were excluded already; if a row is clearly
  a character table, leave `en` empty and say so.
- Glossary terms (classes, races, places, items) must match `work/glossary/glossary.json` exactly;
  new terms: list them in the report.

## Output
Write `slice_NN.out.json` (rows with `en` filled, `note` where needed) and `slice_NN.report.md`
next to the input. Do not edit other files. Never print Japanese to the console.
