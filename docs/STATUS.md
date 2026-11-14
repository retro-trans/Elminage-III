# Translation status (2026-11-14)

Last build: **v0.2.0** — work/output/Elminage III (EN) v0.2.0.iso (not a release).

## Done
- All script text (world map + chapters), EBOOT UI/battle strings and CSV data tables translated and
  reviewed in three stages (accuracy, editorial, proofreading). Reports next to each group:
  work/translation/en/{wmap,chap,ebt,csvt}/review_g*_{accuracy,editorial,proof}.md.
- Term rules (work/glossary/term_replacements*.json) applied; `python tools/apply_terms.py` (dry run)
  reports 0 pending changes.
- Merge pipeline: `python tools/merge_all.py` (story, EBOOT, CSV) -> `python tools/build.py <ver>`.

## In progress
- UI textures: Japanese baked into GIM sheets (menu buttons, skill plates, labels).
  Guide: docs/agent_prompts/ui_texture.md. Specs: work/ui/specs/<SHEET>.json (built by tools/img_text.py,
  wired into the build). Survey of all images: work/ui/japanese_images.md.
- Play-test v0.2.0 in the emulator (savestate work/emulator/states/v020_tavern.ppst when present).

## Open questions / to check in game
- 12px-font VWF (party bar names), item-description wrapping, battle-message assembly (%s %s fragments),
  help-window ": " prefixes (csvt 461/466), "50 percent" spacing (ebt 221/222), Yes/None (ebt 165/166),
  SP_TEXT sentence form (slices 49/50), alchemy recipe window width (RENKIN_TXT).
- Lead decisions still open: 領主 gender, Zaalhaut / Wattner / Zonette / Toner genders (glossary),
  Hobbit vs Hotlet in SP_TEXT 4071, "Alchemy Spells" vs "Alchemist Spells", Summer (monster) vs Summa (rank).
- Old builds should be kept as xdelta patches (AGENTS.md); xdelta is not installed (download needs approval).
