"""Variable-width font for half-width (ASCII) text in the 16px font.

The draw-string routine 0x0891BAF8 advances every half-width glyph by font[0x14] (=10).
We replace the three uses (clip path 0x0891BD28, normal path 0x0891BDB4/0x0891BDCC,
space 0x0891BB88) with a lookup in a 256-byte width table, applied only when
font[0x14] == 10 (the FONT16 object; FONT12 etc. are untouched). The draw width is the
same as the advance, so the 10px cell is cropped to the glyph (glyphs are left-aligned).

Widths are measured from FONT10_16.GIM (work/build/font/FONT10_16.GIM if a redrawn font
exists, else the original): rightmost lit column + 1 + spacing.
"""
import os
import struct
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gim

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
FONT_SRC = os.path.join(ROOT, 'work', 'source', 'arc', 'ANIME', 'FONT10_16.GIM')
FONT_NEW = os.path.join(ROOT, 'work', 'font', 'FONT10_16.GIM')   # optional redrawn font

DRAW = 0x0891BAF8
NEXT_CHAR = 0x0891BE0C
CLIP_JOIN = 0x0891BD38
SPACING = 1
SPACE_W = 5


TEXT_WIDTHS = None      # widths for the script word-wrap: per-char max of the original and HD glyphs
                        # (set by patches.apply_all), so text fits with either font; not used by
                        # tools/img_text.py
HD_WIDTHS = None        # advance widths of the HD glyphs (second half of the EBOOT width table)

# Text font chosen at New Game (tools/text_build.py inject_font_choice): script global variable
# FONT_VAR, 0 = not asked (old saves) / 1 = original pixel font / 2 = HD font. Global variables
# live at *(u32 *)0x08C87860 + 0x20534 + 4 * id (5000 of them, cleared at New Game; the
# scripts use ids up to 396).
FONT_VAR = 4990
FONT_HD = 2
VAR_OFF = 0x534 + 4 * FONT_VAR          # from *(0x08C87860) + 0x20000


def hdchk(reg, lab):
    """asm: reg = 1 if the HD font is selected, else 0 (clobbers $at)."""
    return '''
            lui {r}, 0x08c8
            lw {r}, 0x7860({r})
            beqz {r}, {lab}
            nop
            lui $at, 2
            addu {r}, {r}, $at
            lw {r}, {off}({r})
            addiu {r}, {r}, -{hd}
            sltiu {r}, {r}, 1
        {lab}:
'''.format(r=reg, lab=lab, off=VAR_OFF, hd=FONT_HD)


def text_widths():
    if TEXT_WIDTHS is not None:
        return list(TEXT_WIDTHS)
    return measure(FONT_NEW if os.path.exists(FONT_NEW) else FONT_SRC)


def measure(path):
    rgba, idx, img = gim.decode(open(path, 'rb').read())
    a = rgba[:, :, 3]
    w = [10] * 256
    for code in range(0x21, 0x7f):
        i = code - 0x20
        x0, y0 = (i % 25) * 10, (i // 25) * 16
        cell = a[y0:y0 + 16, x0:x0 + 10] > 40
        cols = np.where(cell.any(0))[0]
        w[code] = int(cols.max()) + 1 + SPACING if len(cols) else SPACE_W
    w[0x20] = SPACE_W
    return w


def apply(eb, info):
    path = FONT_NEW if os.path.exists(FONT_NEW) else FONT_SRC
    widths = measure(path)
    if path == FONT_NEW:
        info['archives'].setdefault('ANIME', {})['FONT10_16.GIM'] = open(path, 'rb').read()
    # [0:256] original font, [256:512] HD font (selected at run time, see hdchk)
    eb.alloc(bytes(widths) + bytes(HD_WIDTHS or widths), 'vwf_widths', align=16)

    # t9 = width of char at fp+s5 if font[0x14]==10, else font[0x14]; result in REG
    def lookup(reg, lab):
        return '''
            lw {r}, 0x14($s3)
            addiu $at, $zero, 10
            bne {r}, $at, {lab}
            addu $t9, $fp, $s5
            lbu $t9, 0($t9)
{hd}            sll $t8, $t8, 8
            addu $t9, $t9, $t8
            lui $t8, %hi(@vwf_widths)
            addiu $t8, $t8, %lo(@vwf_widths)
            addu $t8, $t8, $t9
            lbu {r}, 0($t8)
        {lab}:
        '''.format(r=reg, lab=lab, hd=hdchk('$t8', lab + 'h'))

    def hilo(src):
        v = eb.symbols['vwf_widths']
        hi = ((v + 0x8000) >> 16) & 0xffff
        return src.replace('%hi(@vwf_widths)', '0x%x' % hi).replace('%lo(@vwf_widths)', str(v & 0xffff if v & 0xffff < 0x8000 else (v & 0xffff) - 0x10000))

    # normal half-width path: sets t2 (draw width), t3, a0, a1 and keeps width in s4
    # draw the full cell (narrow sprites under ~4px are not drawn by the GE path);
    # only the advance (s4) comes from the width table
    eb.asm_alloc(hilo(lookup('$s4', 'vwf_l1') + '''
            lw $t2, 0x14($s3)
            lw $t3, 0x18($s3)
            move $a0, $s3
            jr $ra
            move $a1, $s1
        '''), 'vwf_half')
    eb.asm(0x0891BDB4, 'jal 0x%08x; nop; nop; nop' % eb.symbols['vwf_half'], expect=4)
    eb.asm(0x0891BDCC, 'move $v1, $s4', expect=1)

    # clip path (font[0x94] set): s4 = width, t3 = font[0x18], continue at 0x0891BD38
    eb.asm_alloc(hilo(lookup('$s4', 'vwf_l2') + '''
            lw $t3, 0x18($s3)
            j 0x%08x
            nop
        ''' % CLIP_JOIN), 'vwf_clip')
    eb.asm(0x0891BD28, 'j 0x%08x; nop' % eb.symbols['vwf_clip'], expect=2)

    # space (0x20) when half sheets exist: s1 += width(0x20)
    eb.asm_alloc(hilo('''
            lw $v1, 0x14($s3)
            addiu $at, $zero, 10
            bne $v1, $at, vwf_l3
            nop
{hd}            sll $t8, $t8, 8
            lui $t9, %hi(@vwf_widths)
            addiu $t9, $t9, %lo(@vwf_widths)
            addu $t8, $t8, $t9
            lbu $v1, 0x20($t8)
        vwf_l3:  j 0x{nc:08x}
            addu $s1, $s1, $v1
        '''.format(nc=NEXT_CHAR, hd=hdchk('$t8', 'vwf_l3h'))), 'vwf_space')
    eb.asm(0x0891BB88, 'j 0x%08x; nop' % eb.symbols['vwf_space'], expect=2)
    # message window (0x08898808) draws single-byte chars one at a time and advances by the
    # 16px cell (addu s3,s3,s7 @0x08898B54). Wrap the draw call so it returns the VWF width
    # in v0 and advance by v0 instead.
    eb.asm_alloc(hilo('''
            addiu $sp, $sp, -0x10
            sw $ra, 0($sp)
            jal 0x{draw:08x}
            sw $t2, 4($sp)
            lw $t2, 4($sp)
{hd}            sll $t8, $t8, 8
            lbu $t9, 0($t2)
            addu $t9, $t9, $t8
            lui $t8, %hi(@vwf_widths)
            addiu $t8, $t8, %lo(@vwf_widths)
            addu $t8, $t8, $t9
            lbu $v0, 0($t8)
            lw $ra, 0($sp)
            jr $ra
            addiu $sp, $sp, 0x10
        '''.format(draw=DRAW, hd=hdchk('$t8', 'vwf_mch'))), 'vwf_msgchar')
    eb.asm(0x08898B48, 'jal 0x%08x' % eb.symbols['vwf_msgchar'], expect=1)
    eb.asm(0x08898B54, 'addu $s3, $s3, $v0', expect=1)
    info['vwf_widths'] = widths


# ---------------------------------------------------------------------------------------------
# FONT12_12 has no half-width sheet (font[0x2c] == 0): ASCII is converted to full-width SJIS via
# the table at 0x089749C8 and drawn on the full-width path with advance font[4] (12px), so English
# names in the party bar etc. come out widely spaced. For fonts with font[4] == 12 and a byte that
# is a converted ASCII char, draw at x - left[c] and advance by adv[c] (font12.metrics()).
FW_DRAW = 0x0891BDEC      # lw t2,4(s3); lw t3,8(s3); move a0,s3; move a1,s1; jal draw; move a2,s0; lw v1,4(s3)
FW_JOIN = 0x0891BE08      # addu s1,s1,v1
FW_SPACE = 0x0891BB94     # b next; addu s1,s1,v1   (v1 = font[4])
DRAW_CELL = 0x0891BE50


def apply12(eb, info=None):
    import font12
    path = font12.build_sheet()          # Latin cells redrawn with the small label font (v0.8.9)
    if info is not None:
        info['archives'].setdefault('ANIME', {})['FONT12_12.GIM'] = open(path, 'rb').read()
    m = font12.metrics()
    tab = bytearray(256)
    for c in range(0x80):
        left, adv = m.get(c, (0, 12))
        tab[2 * c], tab[2 * c + 1] = left, adv
    eb.alloc(bytes(tab), 'vwf12_tab', align=16)
    v = eb.symbols['vwf12_tab']
    hi, lo = ((v + 0x8000) >> 16) & 0xffff, v & 0xffff
    lo = lo - 0x10000 if lo >= 0x8000 else lo
    eb.asm_alloc('''
            lw $t2, 4($s3)
            lw $t3, 8($s3)
            move $a0, $s3
            move $a1, $s1
            sw $t2, 0x10($sp)
            addiu $at, $zero, 12
            bne $t2, $at, fw_draw
            addu $t9, $fp, $s5
            lbu $t8, 0($t9)
            sltiu $at, $t8, 0x80
            beqz $at, fw_draw
            sltiu $at, $t8, 0x21
            bnez $at, fw_draw
            nop
            beqz $s5, fw_ascii
            nop
            lbu $t7, -1($t9)
            sltiu $at, $t7, 0x81
            beqz $at, fw_draw
            nop
        fw_ascii:
            lui $t9, 0x{hi:x}
            addiu $t9, $t9, {lo}
            sll $t8, $t8, 1
            addu $t9, $t9, $t8
            lbu $t7, 0($t9)
            lbu $t6, 1($t9)
            subu $a1, $s1, $t7
            sw $t6, 0x10($sp)
        fw_draw:
            jal 0x{draw:08x}
            move $a2, $s0
            lw $v1, 0x10($sp)
            j 0x{join:08x}
            nop
        '''.format(hi=hi, lo=lo, draw=DRAW_CELL, join=FW_JOIN), 'vwf12_draw')
    eb.asm(FW_DRAW, 'j 0x%08x; nop; nop; nop; nop; nop; nop' % eb.symbols['vwf12_draw'], expect=7)
    eb.asm_alloc('''
            addiu $at, $zero, 12
            bne $v1, $at, fw_sp
            nop
            lui $t9, 0x{hi:x}
            addiu $t9, $t9, {lo}
            lbu $v1, 0x41($t9)
        fw_sp:
            j 0x{nc:08x}
            addu $s1, $s1, $v1
        '''.format(hi=hi, lo=lo, nc=NEXT_CHAR), 'vwf12_space')
    eb.asm(FW_SPACE, 'j 0x%08x; nop' % eb.symbols['vwf12_space'], expect=2)


# ---------------------------------------------------------------------------------------------
# HD font (one ISO, chosen at New Game): FONT16 gets a second half-width sheet FONT10HD.GIM, a 4x
# (or 2x, tools/font_hd.py SCALE) rendering of the same glyphs. The glyph routine 0x0891BE50 (font a0,
# sheet a3, ...) draws through the generic sprite routine 0x0891DF40 (tex, x, y, w, h, u=t1, v=t2,
# uw=t3, [sp+0]=vh, ...). When the HD font is selected (script variable FONT_VAR == 2), the entry
# hook switches a3 from the 1x sheet to the HD sheet and sets a flag (cleared at the single
# epilogue) that makes 0x0891DF40 scale u, v, uw, vh; the screen size stays the same. Other
# sprites never see the flag. Width tables: vwf_widths[0:256] original, [256:512] HD.
# Real hardware: both sheets stay loaded: +256 KB RAM for the 512x512 index-8 HD sheet (the
# original 1x font path is unchanged when the original font is selected).
GLYPH_FN, GLYPH_RET, SPRITE_FN = 0x0891BE50, 0x0891C0A4, 0x0891DF40
HD_FILE = 'FONT10HD.GIM'



def apply_hd(eb, info):
    import font_hd
    data = font_hd.build()
    # the HD sheet is a NEW file next to the original FONT10_16.GIM (archive TOC is sorted by name)
    info['archives'].setdefault('ANIME', {})[HD_FILE] = data
    # keep ANIME.BIN within its old size (otherwise the 234 MB archive is appended to the ISO): shrink
    # the unused 512x512 'dummy' monster placeholders GR08_100 / GR08_099 (100 identical copies exist)
    shrink = 4 if font_hd.SCALE == 4 else 2
    for name in (('GR08_100.GIM', 'GR08_099.GIM') if font_hd.SCALE == 4 else ('GR08_100.GIM',)):
        dummy = open(os.path.join(ROOT, 'work', 'source', 'arc', 'ANIME', name), 'rb').read()
        _, didx, _ = gim.decode(dummy)
        info['archives']['ANIME'][name] = gim.write_index_resized(dummy, didx[::shrink, ::shrink].copy())
    # FONT16 object (constructor 0x0891B818 called at 0x08876D90): half-width sheet list
    # [FONT10_16.GIM, NULL] @0x0896515C -> [FONT10_16.GIM, FONT10HD.GIM, NULL]; the constructor loads
    # every listed sheet into font[0x30 + 4k], so sheet font[0x2C] + 1 is the HD sheet.
    eb.alloc(HD_FILE.encode('ascii') + bytes(4 - len(HD_FILE) % 4), 'hd_name', align=4)
    eb.alloc(struct.pack('<III', 0x0896514C, eb.symbols['hd_name'], 0), 'hd_list', align=4)
    lst = eb.symbols['hd_list']
    eb.asm(0x08876D74, 'lui $a3, 0x%x' % (((lst + 0x8000) >> 16) & 0xffff), expect=1)
    lo = lst & 0xffff
    eb.asm(0x08876D88, 'addiu $a3, $a3, %d' % (lo - 0x10000 if lo >= 0x8000 else lo), expect=1)
    eb.alloc(bytes(4), 'hd_flag', align=4)
    v = eb.symbols['hd_flag']
    hi, lo = ((v + 0x8000) >> 16) & 0xffff, v & 0xffff
    lo = lo - 0x10000 if lo >= 0x8000 else lo
    # glyph entry: FONT16 half-width sheet (font[0x14] == 10, a3 == font[0x2C]) with a second sheet
    # loaded (a3 + 1 < font[0x24]) and the HD font selected -> draw from sheet a3 + 1, flag the sprite
    eb.asm_alloc(('''
            addiu $sp, $sp, -0x40
            sw $ra, 0x3c($sp)
            lui $t9, 0x{hi:x}
            addiu $t9, $t9, {lo}
            sw $zero, 0($t9)
            lw $at, 0x14($a0)
            addiu $v1, $zero, 10
            bne $at, $v1, hd_e_done
            nop
            lw $at, 0x2c($a0)
            bne $at, $a3, hd_e_done
            nop
            lw $at, 0x24($a0)
            addiu $v1, $a3, 1
            slt $at, $v1, $at
            beqz $at, hd_e_done
            nop
''' + hdchk('$v1', 'hd_e_chk') + '''
            beqz $v1, hd_e_done
            nop
            addiu $a3, $a3, 1
            sw $v1, 0($t9)
        hd_e_done:
            j 0x{back:08x}
            nop
        ''').format(hi=hi, lo=lo, back=GLYPH_FN + 8), 'hd_glyph_entry')
    eb.asm(GLYPH_FN, 'j 0x%08x; nop' % eb.symbols['hd_glyph_entry'], expect=2)
    eb.asm_alloc('''
            lui $t9, 0x{hi:x}
            sw $zero, {lo}($t9)
            jr $ra
            nop
        '''.format(hi=hi, lo=lo), 'hd_glyph_exit')
    eb.asm(GLYPH_RET, 'j 0x%08x; addiu $sp, $sp, 0x40' % eb.symbols['hd_glyph_exit'], expect=2)
    if font_hd.SCALE == 4:
        # 4x sheet is repacked 12 glyphs per row: glyph i = (v/16)*25 + u/10 -> (i%12*40, i/12*64)
        remap = '''
            addiu $at, $zero, 16
            div $zero, $t2, $at
            mflo $v1
            addiu $at, $zero, 25
            mult $v1, $at
            mflo $v1
            addiu $at, $zero, 10
            div $zero, $t1, $at
            mflo $v0
            addu $v1, $v1, $v0
            addiu $at, $zero, 12
            div $zero, $v1, $at
            mflo $v0
            mfhi $v1
            addiu $at, $zero, 40
            mult $v1, $at
            mflo $t1
            addiu $at, $zero, 64
            mult $v0, $at
            mflo $t2
'''
        sh = 2
    else:
        remap = '''
            sll $t1, $t1, 1
            sll $t2, $t2, 1
'''
        sh = 1
    eb.asm_alloc(('''
            addiu $sp, $sp, -0x20
            sw $ra, 0x1c($sp)
            lui $at, 0x{hi:x}
            lw $at, {lo}($at)
            beqz $at, hd_s_done
            nop
''' + remap + '''
            bnez $t3, hd_s1
            nop
            move $t3, $a3
        hd_s1:
            sll $t3, $t3, {sh}
            lw $v0, 0x20($sp)
            bnez $v0, hd_s2
            nop
            move $v0, $t0
        hd_s2:
            sll $v0, $v0, {sh}
            sw $v0, 0x20($sp)
        hd_s_done:
            j 0x{back:08x}
            nop
        ''').format(hi=hi, lo=lo, sh=sh, back=SPRITE_FN + 8), 'hd_sprite_entry')
    eb.asm(SPRITE_FN, 'j 0x%08x; nop' % eb.symbols['hd_sprite_entry'], expect=2)


# ---------------------------------------------------------------------------------------------
# Scrolling help ticker (0x08847A38..): the original builds a 16-character window of 2-byte
# full-width characters starting at char (s1 >> 4) % (len / 2) and draws it at x = s4 - (s1 & 15),
# clipped at x 240 (s1 = elapsed pixels). With 1-byte VWF text that steps two letters per 16 px
# (jittery) and 32 narrow letters stop well short of the bar's end. Replacement (called at
# 0x08847B38, result in s2 = window string, s1 = pixel shift 0..15 for the unchanged x code):
#   W = width of the whole string (VWF table, HD half when the HD font is on; SJIS pair = 16 px),
#   off = s1 % W; start at the character covering pixel 'off', shift = off - its start,
#   copy characters (wrapping at the end) until 256 + shift px are covered (max 120 bytes).
TICKER_HOOK, TICKER_DRAW = 0x08847B38, 0x08847BA0


def apply_ticker(eb):
    eb.alloc(bytes(128), 'ticker_buf', align=4)
    v = eb.symbols['vwf_widths']
    bv = eb.symbols['ticker_buf']
    hl = lambda x: (((x + 0x8000) >> 16) & 0xffff, (x & 0xffff) - (0x10000 if x & 0x8000 else 0))
    whi, wlo = hl(v)
    bhi, blo = hl(bv)
    # t2 = byte, sets t3 = width, t6 = bytes in char (uses at, t9)
    def charw(lab):
        return '''
            addiu $t9, $t2, -0x81
            sltiu $at, $t9, 0x1f
            bnez $at, {l}_w
            sltiu $at, $t2, 0xe0
            beqz $at, {l}_w
            nop
            addu $t3, $t8, $t2
            lbu $t3, 0($t3)
            b {l}_d
            addiu $t6, $zero, 1
        {l}_w:
            addiu $t3, $zero, 16
            addiu $t6, $zero, 2
        {l}_d:
'''.format(l=lab)
    eb.asm_alloc(('''
            lui $t8, 0x{whi:x}
            addiu $t8, $t8, {wlo}
''' + hdchk('$t9', 'tk_hd') + '''
            sll $t9, $t9, 8
            addu $t8, $t8, $t9
            move $t0, $s2
            move $t1, $zero
            move $a3, $zero                  # trailing spaces
        tk_l1:
            lbu $t2, 0($t0)
            beqz $t2, tk_l1e
            nop
''' + charw('tk_c1') + '''
            addu $t1, $t1, $t3
            addiu $at, $zero, 0x20
            bne $t2, $at, tk_ns
            addiu $a3, $a3, 1
            b tk_l1
            addu $t0, $t0, $t6
        tk_ns:
            move $a3, $zero
            b tk_l1
            addu $t0, $t0, $t6
        tk_l1e:
            beqz $t1, tk_zero
            nop
            addiu $a2, $zero, 4              # a2 = pad spaces so that the loop has a 4-space gap
            subu $a2, $a2, $a3
            bgez $a2, tk_pd
            nop
            move $a2, $zero
        tk_pd:
            lbu $v0, 0x20($t8)               # v0 = space width
            mult $a2, $v0
            mflo $at
            addu $t1, $t1, $at               # total loop width
            divu $zero, $s1, $t1
            mfhi $t4                         # pixel offset in the loop
            move $t0, $s2
            move $t5, $zero
            move $v1, $zero                  # pending pad spaces
        tk_l2:
            lbu $t2, 0($t0)
            beqz $t2, tk_l2p
            nop
''' + charw('tk_c2') + '''
            addu $t7, $t5, $t3
            sltu $at, $t4, $t7
            bnez $at, tk_l2f
            nop
            move $t5, $t7
            b tk_l2
            addu $t0, $t0, $t6
        tk_l2p:                              # offset inside the padding
            move $v1, $a2
            move $t0, $s2
        tk_l2q:
            addu $t7, $t5, $v0
            sltu $at, $t4, $t7
            bnez $at, tk_l2f
            nop
            move $t5, $t7
            addiu $v1, $v1, -1
            bgtz $v1, tk_l2q
            nop
        tk_l2f:
            subu $s1, $t4, $t5
            lui $a0, 0x{bhi:x}
            addiu $a0, $a0, {blo}
            move $a1, $a0
            move $t5, $zero
            addiu $t7, $s1, 256
        tk_l3:
            bgtz $v1, tk_pad
            nop
            lbu $t2, 0($t0)
            bnez $t2, tk_l3n
            nop
            move $t0, $s2
            move $v1, $a2
            b tk_l3
            nop
        tk_pad:
            addiu $v1, $v1, -1
            addiu $t2, $zero, 0x20
            sb $t2, 0($a1)
            addiu $a1, $a1, 1
            b tk_l3c
            addu $t5, $t5, $v0
        tk_l3n:
''' + charw('tk_c3') + '''
            sb $t2, 0($a1)
            addiu $at, $zero, 2
            bne $t6, $at, tk_l3s
            nop
            lbu $t9, 1($t0)
            sb $t9, 1($a1)
        tk_l3s:
            addu $a1, $a1, $t6
            addu $t0, $t0, $t6
            addu $t5, $t5, $t3
        tk_l3c:
            sltu $at, $t5, $t7
            beqz $at, tk_l3e
            nop
            subu $t9, $a1, $a0
            sltiu $at, $t9, 120
            bnez $at, tk_l3
            nop
        tk_l3e:
            sb $zero, 0($a1)
            jr $ra
            move $s2, $a0
        tk_zero:
            jr $ra
            move $s1, $zero
        ''').format(whi=whi, wlo=wlo, bhi=bhi, blo=blo), 'ticker_window')
    eb.asm(TICKER_HOOK, 'jal 0x%08x; nop; j 0x%08x; nop' % (eb.symbols['ticker_window'], TICKER_DRAW), expect=4)


# ---------------------------------------------------------------------------------------------
# Fit-to-width copy 0x0891B77C(dst, src, max_px, fullwidth_px, halfwidth_px): copies characters while
# the running width fits. Callers (Sound List titles, Music Folder file names) pass halfwidth_px = 10,
# the fixed width of the original font, so English stopped at 16 characters of a 160 px column.
# With halfwidth_px == 10 the width now comes from the VWF table (HD half when the HD font is on).
FIT_FN, FIT_JOIN = 0x0891B77C, 0x0891B7CC


def apply_fit(eb):
    v = eb.symbols['vwf_widths']
    hi, lo = ((v + 0x8000) >> 16) & 0xffff, (v & 0xffff) - (0x10000 if v & 0x8000 else 0)
    eb.asm_alloc(('''
            bnez $t1, fit_fw
            nop
            addiu $at, $zero, 10
            bne $t0, $at, fit_t0
            nop
''' + hdchk('$t8', 'fit_hd') + '''
            sll $t8, $t8, 8
            lui $t9, 0x{hi:x}
            addiu $t9, $t9, {lo}
            addu $t9, $t9, $t8
            andi $t8, $t3, 0xff
            addu $t9, $t9, $t8
            lbu $v1, 0($t9)
            j 0x{join:08x}
            nop
        fit_t0:
            j 0x{join:08x}
            move $v1, $t0
        fit_fw:
            j 0x{join:08x}
            move $v1, $a3
        ''').format(hi=hi, lo=lo, join=FIT_JOIN), 'vwf_fit')
    eb.asm(FIT_FN + 0x44, 'j 0x%08x; nop; nop' % eb.symbols['vwf_fit'], expect=3)


# ---------------------------------------------------------------------------------------------
# Description boxes. Three loops cut their text into fixed byte rows, which split English words:
#   events + alchemy (0x08846CC4, 10 rows of 28 bytes at x 240; source s0/s4 + 0x22, both += 0x1C),
#   monster text (0x08860A84) and item text (0x08860FD8): rows of 24 bytes at x 268, s2 = source,
#   s1 = bytes left, until s1 <= 0.
# Each row now comes from wrap_line(dst, src, max_px) -> v0 = bytes consumed: whole words while
# the VWF width (HD half when the HD font is on) fits max_px, a full-width character counts 16 px
# and may break anywhere, byte 0x0A forces a break, spaces after a break are skipped. The pixel
# limits: events 224 px (the original 14 full-width characters), descriptions 200 px (box inner
# width from x 268; the original 12 characters were 192 px).
# Real hardware: code in the cave only, same registers and stack frames as the original loops.
WRAP_EVENT, WRAP_EVENT_PX = 0x08846D08, 224
WRAP_DESC, WRAP_DESC_PX = (0x08860A84, 0x08860FD8), 200


def apply_wrap(eb):
    v = eb.symbols['vwf_widths']
    hi, lo = ((v + 0x8000) >> 16) & 0xffff, (v & 0xffff) - (0x10000 if v & 0x8000 else 0)
    eb.asm_alloc((hdchk('$t6', 'wr_hd') + '''
            sll $t6, $t6, 8
            lui $t7, 0x{hi:x}
            addiu $t7, $t7, {lo}
            addu $t6, $t6, $t7
            move $t0, $zero
            move $t1, $zero
            addiu $t2, $zero, -1
        wr_loop:
            addu $t7, $a1, $t0
            lbu $t3, 0($t7)
            beqz $t3, wr_end
            addiu $at, $zero, 0x0a
            beq $t3, $at, wr_nl
            addiu $at, $zero, 0x20
            bne $t3, $at, wr_ns
            nop
            move $t2, $t0
        wr_ns:
            sltiu $at, $t3, 0x81
            bnez $at, wr_hw
            sltiu $at, $t3, 0xa0
            bnez $at, wr_fw
            sltiu $at, $t3, 0xe0
            bnez $at, wr_hw
            sltiu $at, $t3, 0xfd
            beqz $at, wr_hw
            nop
        wr_fw:
            addiu $t4, $zero, 16
            addiu $t5, $zero, 2
            bgtz $t0, wr_fit
            move $t2, $t0
            b wr_fit
            addiu $t2, $zero, -1
        wr_hw:
            addu $t7, $t6, $t3
            lbu $t4, 0($t7)
            addiu $t5, $zero, 1
        wr_fit:
            addu $t7, $t1, $t4
            slt $at, $a2, $t7
            beqz $at, wr_adv
            nop
            beqz $t0, wr_adv
            nop
            blez $t2, wr_hard
            nop
            b wr_skip
            move $v0, $t2
        wr_hard:
            b wr_copy
            move $v0, $t0
        wr_skip:
            addu $t7, $a1, $v0
            lbu $t3, 0($t7)
            addiu $at, $zero, 0x20
            bne $t3, $at, wr_copy
            nop
            b wr_skip
            addiu $v0, $v0, 1
        wr_adv:
            move $t1, $t7
            b wr_loop
            addu $t0, $t0, $t5
        wr_nl:
            b wr_cp0
            addiu $v0, $t0, 1
        wr_end:
            move $v0, $t0
        wr_cp0:
            move $t8, $t0
            b wr_cp
            move $t9, $zero
        wr_copy:
            move $t8, $t2
            bgtz $t2, wr_cp
            move $t9, $zero
            move $t8, $t0
        wr_cp:
            beq $t9, $t8, wr_done
            addu $t7, $a1, $t9
            lbu $t3, 0($t7)
            addu $t7, $a0, $t9
            sb $t3, 0($t7)
            b wr_cp
            addiu $t9, $t9, 1
        wr_done:
            addu $t7, $a0, $t8
            jr $ra
            sb $zero, 0($t7)
        ''').format(hi=hi, lo=lo), 'wrap_line')
    wl = eb.symbols['wrap_line']
    # events / alchemy: the stub advances both source registers by (consumed - 0x1C)
    eb.asm_alloc('''
            addiu $sp, $sp, -16
            sw $ra, 0($sp)
            jal 0x{wl:08x}
            nop
            lw $ra, 0($sp)
            addiu $sp, $sp, 16
            addu $s0, $s0, $v0
            addu $s4, $s4, $v0
            addiu $s0, $s0, -0x1c
            jr $ra
            addiu $s4, $s4, -0x1c
        '''.format(wl=wl), 'wrap_event')
    _expect(eb, WRAP_EVENT, (0x0e205cd6, 0x2406001c, 0xa3a0003c))
    _expect(eb, 0x08846D48, (0xa3a0003c,))
    eb.asm(WRAP_EVENT, 'jal 0x%08x; addiu $a2, $zero, %d; nop' % (eb.symbols['wrap_event'], WRAP_EVENT_PX), expect=3)
    eb.asm(0x08846D48, 'nop', expect=1)           # was sb zero, 0x3c(sp): cut the row at 28 bytes
    for b in WRAP_DESC:
        _expect(eb, b, (0x2a210019,))
        _expect(eb, b + 0x24, (0x0e205cd6, 0x24060018, 0xa3a00028))
        _expect(eb, b + 0x58, (0x2631ffe8, 0x26520018))
        eb.asm(b, '''addiu $a0, $sp, 0x10
                     move $a1, $s2
                     jal 0x{wl:08x}
                     addiu $a2, $zero, {px}
                     addu $s2, $s2, $v0
                     subu $s1, $s1, $v0
                     addiu $s2, $s2, -0x18
                     addiu $s1, $s1, 0x18
                     nop; nop; nop; nop'''.format(wl=wl, px=WRAP_DESC_PX), expect=12)


def _expect(eb, va, words):
    got = tuple(eb.u32(va + 4 * i) for i in range(len(words)))
    assert got == tuple(words), 'unexpected code at %08x: %s' % (va, ' '.join('%08x' % w for w in got))


# ---------------------------------------------------------------------------------------------
# Battle result ('Each surviving member gained / n EP / n GP'): the template with the EP / GP labels
# is drawn first, then each number on its own ('\n%10llu', '\n\n%10llu') at the same x. With the
# fixed 10 px cell the 10-character number ended one cell before the label; with VWF the padding
# spaces are narrower than digits, so the right edge moved with the digit count and ran into the
# label. The number draws now shift x so the line ends at RESULT_COLS space widths; the labels sit
# after RESULT_COLS + 1 spaces (merge_ebt.OVERRIDE). Space width from the selected font (HD aware).
# Real hardware: a stub in the cave around three calls to the draw routine, same arguments.
RESULT_NUM_DRAWS = (0x088BB004, 0x088BB0A0, 0x088BB0EC)    # GP only; EP; GP (after EP)
RESULT_COLS = 15
DRAW_TEXT = 0x08876B7C


def apply_result_numbers(eb):
    v = eb.symbols['vwf_widths']
    hi, lo = ((v + 0x8000) >> 16) & 0xffff, (v & 0xffff) - (0x10000 if v & 0x8000 else 0)
    eb.asm_alloc((hdchk('$t6', 'rn_hd') + '''
            sll $t6, $t6, 8
            lui $t7, 0x{hi:x}
            addiu $t7, $t7, {lo}
            addu $t6, $t6, $t7
            move $t7, $a1
            move $t8, $zero
        rn_loop:
            lbu $t9, 0($t7)
            beqz $t9, rn_end
            addiu $t7, $t7, 1
            addiu $at, $zero, 0x0a
            beq $t9, $at, rn_loop
            addu $t9, $t6, $t9
            lbu $t9, 0($t9)
            b rn_loop
            addu $t8, $t8, $t9
        rn_end:
            lbu $t9, 0x20($t6)
            addiu $at, $zero, {cols}
            mult $t9, $at
            mflo $at
            subu $at, $at, $t8
            j 0x{draw:08x}
            addu $a3, $a3, $at
        ''').format(hi=hi, lo=lo, cols=RESULT_COLS, draw=DRAW_TEXT), 'result_num')
    for a in RESULT_NUM_DRAWS:
        _expect(eb, a, (0x0e21dadf,))
        eb.asm(a, 'jal 0x%08x' % eb.symbols['result_num'], expect=1)
