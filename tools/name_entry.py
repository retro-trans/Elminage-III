"""Latin name entry with VWF display (Training Hall registration, Edit Profile, other text entry).

The editor (state *(u32 *)0x08BE7094) keeps the text as 2-byte cells at state+8 (cursor +0x2210,
max cells +0x220A, mode +0x2E8, record pointer +0x2E4). The keyboard is 15x6 cells per page,
row strings via the pointer table 0x08963358 (81 pages x 6 rows); a selected cell's 2 bytes are
copied into the buffer; row 5 columns 12/13/14 are cursor left / right / end (checked by position).

Changes (everything stays 2-byte cells inside the editor, so its logic is untouched):
  - one Latin page (A-Z, a-z, 0-9, punctuation, blank cells = space) in a copy of the page table,
    so L/R paging stays on it; the end key reads 'OK'. The three users of the table read it through
    a pointer set per editor mode: the Book of the Next Age password screen (mode 0x15C) keeps the
    original kana keyboard, because its passwords are kana.
  - grid cells are drawn converted to ASCII (VWF/HD font) and centred in the cell (0x088533A4).
  - the typed text in the profile panel is drawn converted to ASCII (0x088EAA48).
  - the cursor box follows the VWF width of the text before it (wrapper of 0x08853014).
  - on confirm, the buffer is converted to ASCII (trailing spaces trimmed) before it is copied into
    the character record (hook 0x08850BEC, branch 0x08850B84 retargeted to it).
  - ASCII text in the buffer (an existing English name being edited) is converted back to cells
    every frame while the keyboard is drawn (entry of 0x088532E4), and on the 'empty -> restore old
    name' path (0x08850B2C).
  - Square (random name generator: Japanese syllable tables) is disabled (0x08850F74).
Real hardware: data/code in the cave only, no layout changes.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ROWS = [
    'ABCDEFGHIJKLM\',',
    'NOPQRSTUVWXYZ-.',
    'abcdefghijklm!?',
    'nopqrstuvwxyz&:',
    '0123456789()/+#',
    '*@~%$;="    ',          # 12 cells; then <- -> OK
]
# ASCII -> Shift-JIS full-width
FW = {' ': 0x8140, ',': 0x8143, '.': 0x8144, ':': 0x8146, ';': 0x8147, '?': 0x8148, '!': 0x8149,
      '\'': 0x8166, '"': 0x8168, '(': 0x8169, ')': 0x816A, '+': 0x817B, '-': 0x817C, '=': 0x8181,
      '/': 0x815E, '~': 0x8160, '$': 0x8190, '%': 0x8193, '#': 0x8194, '&': 0x8195, '*': 0x8196,
      '@': 0x8197}
for i in range(10):
    FW[chr(0x30 + i)] = 0x824F + i
for i in range(26):
    FW[chr(0x41 + i)] = 0x8260 + i
    FW[chr(0x61 + i)] = 0x8281 + i

STATE = 0x08BE7094
DRAW_TEXT = 0x08876B7C
GRID_FN, GRID_DRAW_CALL = 0x088532E4, 0x088533A4
FIELD_DRAW_CALLS = (0x088EAA48, 0x08854C20)     # profile panel fields; personality comment screen
# editor init 0x088502F8 (a1 = max cells): single-line fields store 1-byte ASCII, so twice as many
# letters fit the record field (title 0x10, name 0x14, nickname 0x14, comment 0x0C bytes) and the
# same pixel width as the original full-width limit
FIELD_LIMITS = ((0x0882C9A8, 8), (0x0882C9D4, 10), (0x0882C9FC, 6), (0x0882CC6C, 6))
CURSOR_FN, CURSOR_CALLS = 0x08853014, (0x088534D8, 0x0885446C, 0x08854BCC, 0x088563B0)
COMMIT_BR, COMMIT_AT = 0x08850B84, 0x08850BEC
RESTORE_CALL, FILTER_FN = 0x08850B2C, 0x0885376C
RANDOM_BR = 0x08850F74
PAGE_TABLE, PAGE_ROWS = 0x08963358, 486
PAGE_REFS = ((0x08853318, 0x08853320, '$v0'), (0x08853630, 0x08853634, '$a0'), (0x0885376C, 0x08853774, '$t3'))
PASSWORD_MODE = 0x15C                  # Book of the Next Age password entry: original kana keyboard
MULTILINE_MODES = (0x15C, 0x175, 0x176, 0x177)


def hilo(v):
    lo = v & 0xffff
    return ((v + 0x8000) >> 16) & 0xffff, lo - 0x10000 if lo >= 0x8000 else lo


def rows_data():
    out = b''
    for k, r in enumerate(ROWS):
        b = b''.join(struct.pack('>H', FW[c]) for c in r)
        if k == 5:
            b += struct.pack('>HH', 0x81A9, 0x81A8) + b'OK'       # <- -> OK (checked by position)
        assert len(b) == 30, (k, len(b))
        out += b + b'\0\0'
    return out


def apply(eb):
    import vwf
    tab = bytearray(2 * 95)
    for c, code in FW.items():
        struct.pack_into('<H', tab, 2 * (ord(c) - 0x20), code)
    eb.alloc(bytes(tab), 'ne_tab', align=4)
    eb.alloc(rows_data(), 'ne_rows', align=4)
    eb.alloc(bytes(192), 'ne_tmp', align=4)
    eb.alloc(bytes(192), 'ne_draw', align=4)   # draw scratch
    dh, dl = hilo(eb.symbols['ne_draw'])
    th, tl = hilo(eb.symbols['ne_tab'])
    mh, ml = hilo(eb.symbols['ne_tmp'])
    wh, wl = hilo(eb.symbols['vwf_widths'])
    rows = eb.symbols['ne_rows']
    # Latin page table (all pages = the Latin page); the original table stays for the Book of the Next
    # Age password screen (mode PASSWORD_MODE: kana passwords). ne_pagetab = table in use.
    eb.alloc(b''.join(struct.pack('<I', rows + 32 * (k % 6)) for k in range(PAGE_ROWS)), 'ne_pages', align=4)
    eb.alloc(struct.pack('<I', eb.symbols['ne_pages']), 'ne_pagetab', align=4)
    ph, pl = hilo(eb.symbols['ne_pagetab'])
    for lui_at, add_at, reg in PAGE_REFS:
        eb.asm(lui_at, 'lui %s, 0x%x' % (reg, ph), expect=1)
        eb.asm(add_at, 'lw %s, %d(%s)' % (reg, pl, reg), expect=1)

    # fw2hw(a0): full-width ASCII -> ASCII in place (other characters kept). Leaf; t3-t9, v0, v1, at.
    eb.asm_alloc('''
            move $t3, $a0
            move $t4, $a0
            lui $t9, 0x{th:x}
            addiu $t9, $t9, {tl}
        f_l:
            lbu $t5, 0($t3)
            beqz $t5, f_e
            sltiu $at, $t5, 0x80
            bnez $at, f_s
            addiu $t6, $t5, -0xa1
            sltiu $at, $t6, 0x3f
            bnez $at, f_s
            lbu $t6, 1($t3)
            sll $t7, $t5, 8
            or $t7, $t7, $t6
            move $t8, $zero
        f_f:
            sll $v0, $t8, 1
            addu $v0, $t9, $v0
            lhu $v1, 0($v0)
            beq $v1, $t7, f_hit
            addiu $t8, $t8, 1
            sltiu $at, $t8, 95
            bnez $at, f_f
            nop
            sb $t5, 0($t4)
            sb $t6, 1($t4)
            addiu $t3, $t3, 2
            b f_l
            addiu $t4, $t4, 2
        f_hit:
            addiu $v0, $t8, 0x1f
            sb $v0, 0($t4)
            addiu $t3, $t3, 2
            b f_l
            addiu $t4, $t4, 1
        f_s:
            sb $t5, 0($t4)
            addiu $t3, $t3, 1
            b f_l
            addiu $t4, $t4, 1
        f_e:
            jr $ra
            sb $zero, 0($t4)
        '''.format(th=th, tl=tl), 'ne_fw2hw')

    # hw2fw_copy(a0 dst, a1 src, a2 max cells): ASCII -> full-width cells; multibyte copied; leaf.
    eb.asm_alloc('''
            move $t3, $a1
            move $t4, $a0
            move $t5, $zero
            lui $t9, 0x{th:x}
            addiu $t9, $t9, {tl}
        h_l:
            slt $at, $t5, $a2
            beqz $at, h_e
            nop
            lbu $t6, 0($t3)
            beqz $t6, h_e
            sltiu $at, $t6, 0x80
            beqz $at, h_mb
            addiu $t7, $t6, -0x20
            sltiu $at, $t7, 95
            beqz $at, h_skip
            sll $t7, $t7, 1
            addu $t7, $t9, $t7
            lhu $t7, 0($t7)
            beqz $t7, h_skip
            srl $t8, $t7, 8
            sb $t8, 0($t4)
            sb $t7, 1($t4)
            addiu $t4, $t4, 2
            addiu $t5, $t5, 1
        h_skip:
            b h_l
            addiu $t3, $t3, 1
        h_mb:
            addiu $t7, $t6, -0xa1
            sltiu $at, $t7, 0x3f
            bnez $at, h_skip
            lbu $t7, 1($t3)
            sb $t6, 0($t4)
            sb $t7, 1($t4)
            addiu $t4, $t4, 2
            addiu $t5, $t5, 1
            b h_l
            addiu $t3, $t3, 2
        h_e:
            jr $ra
            sb $zero, 0($t4)
        '''.format(th=th, tl=tl), 'ne_hw2fw_copy')

    # normalize(a0 buf, a1 max cells): if the buffer holds ASCII, convert it back to cells
    eb.asm_alloc('''
            move $t3, $a0
        n_l:
            lbu $t5, 0($t3)
            beqz $t5, n_none
            sltiu $at, $t5, 0x80
            bnez $at, n_conv
            addiu $t6, $t5, -0xa1
            sltiu $at, $t6, 0x3f
            bnez $at, n_conv
            nop
            b n_l
            addiu $t3, $t3, 2
        n_conv:
            addiu $sp, $sp, -0x10
            sw $ra, 0($sp)
            sw $a0, 4($sp)
            sw $a1, 8($sp)
            lui $t3, 0x{mh:x}
            addiu $t3, $t3, {ml}
            move $t4, $a0
            addiu $t6, $t3, 190
        n_c:
            lbu $t5, 0($t4)
            sb $t5, 0($t3)
            beqz $t5, n_cd
            addiu $t4, $t4, 1
            addiu $t3, $t3, 1
            bne $t3, $t6, n_c
            nop
            sb $zero, 0($t3)
        n_cd:
            lw $a0, 4($sp)
            lw $a2, 8($sp)
            lui $a1, 0x{mh:x}
            jal 0x{cp:08x}
            addiu $a1, $a1, {ml}
            lw $ra, 0($sp)
            lw $a0, 4($sp)
            lw $a1, 8($sp)
            addiu $sp, $sp, 0x10
            addiu $t6, $a1, -1               # cursor -> end of the converted text (the game set it
            slt $at, $t5, $t6                #  from byte length / 2, i.e. mid-word for ASCII)
            bnez $at, n_cur
            nop
            move $t5, $t6
        n_cur:
            sh $t5, 0x2208($a0)              # state + 0x2210 (a0 = state + 8)
        n_none:
            jr $ra
            nop
        '''.format(mh=mh, ml=ml, cp=eb.symbols['ne_hw2fw_copy']), 'ne_normalize')

    # grid function entry: normalize the edit buffer, then the 2 replaced instructions
    eb.asm_alloc('''
            addiu $sp, $sp, -0x10
            sw $ra, 0($sp)
            sw $a0, 4($sp)
            lui $v0, 0x{sh:x}
            lw $v0, {sl}($v0)
            beqz $v0, g_skip
            nop
            lw $t3, 0x2e8($v0)               # page table for this editor mode
            lui $t4, 0x{oh:x}
            addiu $t4, $t4, {ol}
            addiu $at, $zero, {pm}
            beq $t3, $at, g_tab
            nop
            lui $t4, 0x{nh:x}
            addiu $t4, $t4, {nl}
        g_tab:
            lui $at, 0x{ph:x}
            sw $t4, {pl}($at)
            addiu $at, $zero, {pm}
            beq $t3, $at, g_skip
            nop
            lh $a1, 0x220a($v0)
            blez $a1, g_skip
            nop
            jal 0x{nm:08x}
            addiu $a0, $v0, 8
        g_skip:
            lw $ra, 0($sp)
            lw $a0, 4($sp)
            addiu $sp, $sp, 0x10
            addiu $sp, $sp, -0x30
            j 0x{back:08x}
            sw $ra, 0x1c($sp)
        '''.format(sh=hilo(STATE)[0], sl=hilo(STATE)[1], nm=eb.symbols['ne_normalize'], back=GRID_FN + 8,
                oh=hilo(PAGE_TABLE)[0], ol=hilo(PAGE_TABLE)[1], nh=hilo(eb.symbols['ne_pages'])[0],
                nl=hilo(eb.symbols['ne_pages'])[1], ph=ph, pl=pl, pm=PASSWORD_MODE),
        'ne_gridfn')
    eb.asm(GRID_FN, 'j 0x%08x; nop' % eb.symbols['ne_gridfn'], expect=2)

    # draw wrappers: convert the string (a1) then draw; grid cells centred (16 px glyph slot)
    def wrapper(name, centre):
        cen = ('''
            lbu $t5, 0($a1)
            beqz $t5, w_go
            lbu $t6, 1($a1)
            bnez $t6, w_go
            sltiu $at, $t5, 0x80
            beqz $at, w_go
            nop
''' + vwf.hdchk('$t8', 'w_hd') + '''
            sll $t8, $t8, 8
            addu $t8, $t8, $t5
            lui $t9, 0x{wh:x}
            addiu $t9, $t9, {wl}
            addu $t9, $t9, $t8
            lbu $t9, 0($t9)
            addiu $t9, $t9, -16
            subu $t9, $zero, $t9
            sra $t9, $t9, 1
            lw $a3, 0x0c($sp)
            addu $a3, $a3, $t9
            sw $a3, 0x0c($sp)
        w_go:
''').format(wh=wh, wl=wl) if centre else ''
        eb.asm_alloc(('''
            addiu $sp, $sp, -0x30
            sw $ra, 0($sp)
            sw $a0, 4($sp)
            sw $a1, 8($sp)
            sw $a3, 0x0c($sp)
            sw $t0, 0x10($sp)
            sw $t1, 0x14($sp)
            sw $t2, 0x18($sp)
            sw $a2, 0x1c($sp)
            lui $t3, 0x{sh:x}                # copy (max 190 bytes) to scratch: never convert in place
            addiu $t3, $t3, {sl}
            move $t4, $a1
            addiu $t6, $t3, 190
        w_cp:
            lbu $t5, 0($t4)
            sb $t5, 0($t3)
            beqz $t5, w_cpd
            addiu $t4, $t4, 1
            addiu $t3, $t3, 1
            bne $t3, $t6, w_cp
            nop
            sb $zero, 0($t3)
        w_cpd:
            lui $a0, 0x{sh:x}
            jal 0x{f:08x}
            addiu $a0, $a0, {sl}
            lui $a1, 0x{sh:x}
            addiu $a1, $a1, {sl}
            sw $a1, 8($sp)
''' + cen + '''
            lw $ra, 0($sp)
            lw $a0, 4($sp)
            lw $a1, 8($sp)
            lw $a3, 0x0c($sp)
            lw $t0, 0x10($sp)
            lw $t1, 0x14($sp)
            lw $t2, 0x18($sp)
            lw $a2, 0x1c($sp)
            j 0x{d:08x}
            addiu $sp, $sp, 0x30
        ''').format(f=eb.symbols['ne_fw2hw'], d=DRAW_TEXT, sh=dh, sl=dl), name)
    wrapper('ne_grid_draw', True)
    wrapper('ne_field_draw', False)
    eb.asm(GRID_DRAW_CALL, 'jal 0x%08x' % eb.symbols['ne_grid_draw'], expect=1)
    for c in FIELD_DRAW_CALLS:
        eb.asm(c, 'jal 0x%08x' % eb.symbols['ne_field_draw'], expect=1)
    for at, n in FIELD_LIMITS:
        assert eb.u32(at) == 0x24050000 | n, hex(at)
        eb.w32(at, 0x24050000 | (2 * n))

    # cursor: x = base + VWF width of the cells before the cursor (single-line fields)
    multi = ''.join('''
            addiu $at, $zero, {m}
            beq $t3, $at, c_done
            nop'''.format(m=m) for m in MULTILINE_MODES)
    eb.asm_alloc(('''
            addiu $sp, $sp, -0x10
            sw $ra, 0($sp)
            jal 0x{cf:08x}
            sw $a0, 4($sp)
            lw $a0, 4($sp)
            lui $v0, 0x{sh:x}
            lw $v0, {sl}($v0)
            lw $t3, 0x2e8($v0)''' + multi + '''
            lh $t4, 0x2210($v0)
            blez $t4, c_done
            addiu $t5, $v0, 8
''' + vwf.hdchk('$t8', 'c_hd') + '''
            sll $t8, $t8, 8
            lui $t9, 0x{wh:x}
            addiu $t9, $t9, {wl}
            addu $t9, $t9, $t8
            move $t6, $zero
        c_l:
            lbu $t7, 0($t5)
            beqz $t7, c_sp
            lbu $t8, 1($t5)
            sll $t7, $t7, 8
            or $t7, $t7, $t8
            lui $a1, 0x{th:x}
            addiu $a1, $a1, {tl}
            move $a2, $zero
        c_f:
            lhu $v1, 0($a1)
            beq $v1, $t7, c_hit
            addiu $a2, $a2, 1
            sltiu $at, $a2, 95
            bnez $at, c_f
            addiu $a1, $a1, 2
            b c_n
            addiu $t6, $t6, 16
        c_sp:
            lbu $v1, 0x20($t9)
            b c_n
            addu $t6, $t6, $v1
        c_hit:
            addiu $a2, $a2, 0x1f
            addu $v1, $t9, $a2
            lbu $v1, 0($v1)
            addu $t6, $t6, $v1
        c_n:
            addiu $t4, $t4, -1
            bgtz $t4, c_l
            addiu $t5, $t5, 2
            lh $t4, 0x2210($v0)
            sll $t4, $t4, 4
            lw $t7, 0($a0)
            subu $t7, $t7, $t4
            addu $t7, $t7, $t6
            sw $t7, 0($a0)
        c_done:
            lw $ra, 0($sp)
            jr $ra
            addiu $sp, $sp, 0x10
        ''').format(cf=CURSOR_FN, sh=hilo(STATE)[0], sl=hilo(STATE)[1], wh=wh, wl=wl, th=th, tl=tl),
        'ne_cursor')
    for c in CURSOR_CALLS:
        eb.asm(c, 'jal 0x%08x' % eb.symbols['ne_cursor'], expect=1)

    # confirm: buffer -> ASCII, trailing spaces trimmed; returns with v1 = mode, v0 = 0xa1
    eb.asm_alloc('''
            addiu $sp, $sp, -0x10
            sw $ra, 0($sp)
            jal 0x{f:08x}
            addiu $a0, $s0, 8
            addiu $t3, $s0, 8
            move $t4, $t3
        k_l:
            lbu $t5, 0($t3)
            beqz $t5, k_t
            addiu $t3, $t3, 1
            addiu $at, $zero, 0x20
            bne $t5, $at, k_l
            nop
            b k_l
            nop
        k_t:
            addiu $t3, $t3, -1
        k_b:
            beq $t3, $t4, k_d
            nop
            lbu $t5, -1($t3)
            addiu $at, $zero, 0x20
            bne $t5, $at, k_d
            nop
            addiu $t3, $t3, -1
            b k_b
            sb $zero, 0($t3)
        k_d:
            lw $ra, 0($sp)
            addiu $sp, $sp, 0x10
            lw $v1, 0x2e8($s0)
            jr $ra
            addiu $v0, $zero, 0xa1
        '''.format(f=eb.symbols['ne_fw2hw']), 'ne_commit')
    eb.asm(COMMIT_BR, 'bnel $v0, $zero, 0x%08x' % COMMIT_AT, expect=1)
    eb.asm(COMMIT_AT, 'jal 0x%08x' % eb.symbols['ne_commit'], expect=1)

    # 'empty -> restore the old name': convert the (ASCII) old name to cells first
    eb.asm_alloc('''
            addiu $sp, $sp, -0x10
            sw $ra, 0($sp)
            sw $a0, 4($sp)
            sw $a2, 8($sp)
            lui $a0, 0x{mh:x}
            jal 0x{cp:08x}
            addiu $a0, $a0, {ml}
            lw $a0, 4($sp)
            lw $a2, 8($sp)
            lui $a1, 0x{mh:x}
            jal 0x{flt:08x}
            addiu $a1, $a1, {ml}
            lw $ra, 0($sp)
            jr $ra
            addiu $sp, $sp, 0x10
        '''.format(mh=mh, ml=ml, cp=eb.symbols['ne_hw2fw_copy'], flt=FILTER_FN), 'ne_restore')
    eb.asm(RESTORE_CALL, 'jal 0x%08x' % eb.symbols['ne_restore'], expect=1)

    # Square: random (Japanese) name generator off
    assert eb.u32(RANDOM_BR) >> 26 == 0x14                        # beql v0, zero, 0x0885102C
    eb.w32(RANDOM_BR, 0x10000000 | ((0x0885102C - RANDOM_BR - 4) >> 2))   # b (delay slot as before)
