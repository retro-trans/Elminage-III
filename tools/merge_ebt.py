"""Merge translated EBOOT UI slices into work/translation/en/eboot.json.

    python tools/merge_ebt.py [--dry]

- Reads work/translation/en/ebt/review_g*.json (reviewed; else slice_*.out.json) + rows_index.json (row -> all eb@ ids).
- Never writes ids in NEVER (strings the program compares with strcmp: CSV parser keys).
- OVERRIDE gives a different English for one id (shared Japanese, different meaning).
- A short string (<= 2 Japanese chars) found at several addresses is applied only to ids that
  the program references (code xref or data pointer); the rest are chance byte matches.
- Checks: printf placeholders equal and in order, ASCII, max_bytes for unreferenced ids.
"""
import glob
import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
D = os.path.join(ROOT, 'work', 'translation', 'en', 'ebt')
EB = os.path.join(ROOT, 'work', 'translation', 'en', 'eboot.json')

NEVER = {
    'eb@0897155c', 'eb@08971564', 'eb@08971574',   # SPELL.CSV school keys (strcmp), ebt slice_13 report
    'eb@08971748',   # 当人: strncmp key at 0x089054A4 (compared with parsed text), keep Japanese
    'eb@0897164c',   # ○: EMPLOY.CSV permission mark, strncmp 0x089047B0 (class sex/alignment bits)
    'eb@08971910',   # 未使用: BGM_NAME.CSV 'unused' prefix, strncmp 0x08908A70
}
# Name-entry character grid: 0x80 pointers at 0x089696C0 -> 2-byte glyph strings 0x089694BC..
# 0x089696BC; code 0x08895754 strcmp()s typed characters against them. Never write there.
GLYPH_POOL = (0x089694BC, 0x089696C0)
OVERRIDE = {
    'eb@08973270': 'The Magician',                 # tarot card list entry sharing the class string
    'eb@089668d0': 'Above the clouds',
    # bestiary monster types: the type column is ~66 px wide (shared-string types: eboot_text.PTR_OVERRIDE)
    'eb@089738f8': 'Arcane', 'eb@08973934': 'Mythic', 'eb@08973968': 'Godshade', 'eb@08973950': 'Beastkin',
    'eb@0896cc68': ' hit(s)!',                     # battle: '<n> hits!' is shown for n = 1 too
    'eb@08960120': 'Select save data to load.  ',   # load screen: shown on one line with eb@08960148
    'eb@08960148': 'Triangle: delete data.',      # (the long version ran past the message box)
    'eb@0896ee54': 'Choose a command. Square: All-Out Attack, R: Command Repeat, L: Normal Mode    ',   # help ticker: trailing gap before it repeats
    'eb@0896eeb8': 'Choose a command. Square: All-Out Attack, R: Command Repeat, L: Action Order    ',   # help ticker: trailing gap before it repeats
    'eb@0895ef48': 'Choose the weather you want.    ',   # help ticker: trailing gap before it repeats
    # battle result: the EP / GP labels sit after 16 spaces; the numbers are drawn separately and
    # right-aligned one space before them (vwf.apply_result_numbers)
    'eb@0896ce6c': 'Each surviving member gained\n' + ' ' * 16 + 'GP',
    'eb@0896cea8': 'Each surviving member gained\n' + ' ' * 16 + 'EP\n' + ' ' * 16 + 'GP',
    'eb@08973188': '2-Hand',                      # equip compare 'Typ' column (table 0x089731A0): 'Two-Handed' ran into 'Rng'
    'eb@089733f4': 'Good', 'eb@08973400': 'Neutral', 'eb@08973410': 'Evil',   # item details use letters (patches.alignment_letters)             # strncmp key vs script line (patches.text_checks)
}
# Rows the slice filter dropped (1-kana race abbreviations, ebt slice_17 report; action-order marker
# row 1049 next to 'A'). Written directly; all are 3-byte slots (2 ASCII + NUL).
EXTRA = {
    # alignment table @0x08973424 (name, letter, full-width letter, colour): the class column ("G-Fig")
    # draws the full-width letter; Good/Neutral were left as Ｇ/Ｎ (pixel full-width glyphs)
    'eb@089733fc': 'G', 'eb@0897340c': 'N',
    'eb@0897359c': 'Sam', 'eb@08973550': 'Kan', 'eb@089735b0': 'Nin',   # class abbreviations: original ＳＡＭ/ＫＡＮ in capitals
    'eb@08973850': 'El', 'eb@08973860': 'Dw', 'eb@0897386c': 'Gn', 'eb@08973880': 'Ho',
    'eb@08973890': 'Fa', 'eb@089738a4': 'Wb', 'eb@089738cc': 'Dv', 'eb@089738e4': 'Og',
    'eb@089738f4': 'Gb', 'eb@08973948': 'Pr', 'eb@0897123c': 'M',
    # weapon range (shop RAN column, table 0x08973CBC: full-width, half-width pairs): the shop draws the
    # full-width Ｓ／Ｍ／Ｌ, which only exist in the pixel font; ASCII letters use the VWF font
    'eb@08973c9c': 'S', 'eb@08973ca4': 'M', 'eb@08973cac': 'L',
}
# Referenced names the slice filter dropped (katakana-only 8-char strings); relocated if longer.
EXTRA_REF = {
    # battle / camp prompts the slice filter dropped (exactly 15 full-width characters)
    'eb@0896ed48': 'No usable skills.',
    'eb@0896ef84': 'Choose an item to use',
    'eb@0896efd8': 'Choose a target to Dispel',
    'eb@0896f084': 'Choose a Swallow Slayer target',
    'eb@0896bbb4': 'There is no Summoner in the party.',
    'eb@08971374': '%s disarmed the trap!',        # missed by the slice filter (next to the failure line)
    'eb@0896d864': 'The breath element changed to "%s"',
    'eb@089646e4': 'Royal Suite',
    'eb@08965368': 'Master Therion', 'eb@0896d2e8': 'Master Therion', 'eb@08972f70': 'Master Therion',
    'eb@0896bc2c': 'Green Plakio', 'eb@08973f1c': 'Green Plakio',
    'eb@0896bf98': 'Dungeon Load', 'eb@08972928': 'Dungeon Load',
    'eb@0896cc44': 'Recovery Phase',
    'eb@0897283c': 'Joker Land', 'eb@08972900': 'Seirion-Daera',
    'eb@08972d8c': 'Magic Drain', 'eb@08972dd8': 'Spell Blaster', 'eb@08972dec': 'Priest Blaster',
    'eb@08972e0c': 'Counter Punch', 'eb@08973d64': 'Dark Fuhrer',
    'eb@08976e30': ' ' * 22 + 'Script    Shingo Magota',
}
PH = re.compile(r'%[-+ #0]*\d*(?:\.\d+)?[hlL]?[diouxXcsfeEgG%]')


def main():
    dry = '--dry' in sys.argv
    index = json.load(open(os.path.join(D, 'rows_index.json'), encoding='utf-8'))
    eb = json.load(open(EB, encoding='utf-8'))
    by_id = {e['id']: e for e in eb}
    rows = []
    # reviewed groups (accuracy/editorial/proof) supersede the raw slices
    files = sorted(f for f in glob.glob(os.path.join(D, 'review_g*.json')) if not f.endswith('.en.json')) or sorted(glob.glob(os.path.join(D, 'slice_*.out.json')))
    for f in files:
        rows += json.load(open(f, encoding='utf-8'))
    applied = skipped_ref = bad = 0
    for r in rows:
        en = (r.get('en') or '').strip('\n') if r.get('en') else ''
        if not en:
            continue
        ref = index[r['row']]
        if ref['jp'] != r['jp']:
            print('row %d: source mismatch' % r['row']); bad += 1
            continue
        if PH.findall(ref['jp'].replace('％', '%%')) != PH.findall(en) and PH.findall(ref['jp']) != PH.findall(en):
            print('row %d: placeholders differ' % r['row']); bad += 1
            continue
        if any(ord(c) > 0x7e for c in en):
            print('row %d: non-ASCII' % r['row']); bad += 1
            continue
        ids = ref['ids']
        short = len(ref['jp']) <= 2 and len(ids) > 1
        for i in ids:
            if i in NEVER or GLYPH_POOL[0] <= int(i[3:], 16) < GLYPH_POOL[1]:
                continue
            e = by_id[i]
            if short and not (e['refs'] or e['ptrs']):
                skipped_ref += 1
                continue
            text = OVERRIDE.get(i, en)
            if not (e['refs'] or e['ptrs']) and len(text.encode('ascii')) + 1 > e['len']:
                print('%s: %d bytes > slot %d (row %d)' % (i, len(text) + 1, e['len'], r['row'])); bad += 1
                continue
            e['en'] = text
            applied += 1
    for i, text in EXTRA_REF.items():
        assert by_id[i]['refs'] or by_id[i]['ptrs'], i
        by_id[i]['en'] = text
        applied += 1
    for i, text in EXTRA.items():
        assert len(text) + 1 <= by_id[i]['len'], i
        by_id[i]['en'] = text
        applied += 1
    print('applied to %d ids, %d chance matches skipped, %d problems' % (applied, skipped_ref, bad))
    if not dry:
        json.dump(eb, open(EB, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
