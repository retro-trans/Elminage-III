"""Fixes for bugs of the original game (executable and map data). Script-side fixes: text_build.SCRIPT_FIXES.
Bug list: Elminage III wiki, 攻略/バグ. lost_after_battle, npc_swap and map_edges are its three "severe" bugs;
revive_hp, class_skill, repeat_flee, pact_repeat, sp_item and guard_cursor are minor ones.

lost_after_battle: freeze at the end of a battle when a level drain left a character lost
-----------------------------------------------------------------------------------------
Battle-end phase 14 (battle routine 0x088CF8B4, phase 0x08DF88A0, sub-state 0x08DF88A2):
  sub 0: level drains pending in the battle slots (+0x232 / +0x286, 0x088FE9AC); a character whose
         Vitality (stat 3, 0x08910C14) is then below 3 goes on the lost list (0x08DF89E0 count).
  sub 1: per lost character "%s has been lost.", the battle slot is cleared and the character is removed
         from the roster with 0x0887FB04(roster, index, 0).
0x0887FB04 rebuilds the battle party (0x088CB688) when the character was in the current party, and that
calls the battle-data reset 0x088B97DC: memset(0x08DF8298, 0, 0x790), which holds the phase, the sub-state
and the lost list. The phase falls to 0 (idle), the battle task (0x088499BC) never gets its 'finished'
result, and the game sits on the battle background forever (reproduced in PPSSPP: Vitality set to 2 and
one pending drain, then winning a battle).
Fix: in sub 1 the removal is queued (lost_defer) instead of done; the queue is run (lost_flush) when the
battle task finishes, right before it hands back to the dungeon (0x088499F4 -> 0x08876FC8), where a party
rebuild is what the game does anyway. Everything else in sub 1 (message, slot clear, unique-character
template restore, record clear) is unchanged.
Real hardware: about 0xD0 bytes in the code cave; no timing change.
"""
import os
import struct

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
ROSTER_PTR = 0x08DF822C          # u32: roster base (character records at +0x68, 0x3D0 each)
REMOVE_CHAR = 0x0887FB04         # (roster, index, 0): remove a character from the roster and its party
SITE_REMOVE = 0x088D1380         # battle-end sub 1: jal REMOVE_CHAR
TASK_DONE = 0x088499F4           # battle task finished: jal 0x08876FC8 (back to the dungeon)
TASK_NEXT = 0x08876FC8
MAX_LOST = 7


def _hi_lo(v):
    return (v + 0x8000) >> 16 & 0xffff, v & 0xffff


def lost_after_battle(eb):
    assert eb.u32(SITE_REMOVE) == 0x0C000000 | (REMOVE_CHAR >> 2 & 0x3ffffff), hex(eb.u32(SITE_REMOVE))
    assert eb.u32(TASK_DONE) == 0x0C000000 | (TASK_NEXT >> 2 & 0x3ffffff), hex(eb.u32(TASK_DONE))
    q = eb.alloc(bytes(4 + 4 * MAX_LOST), 'lost_q')   # in the cave (file-backed): 32 bytes
    qh, ql = _hi_lo(q)
    rh, rl = _hi_lo(ROSTER_PTR)
    # lost_defer(a0 roster, a1 index, a2): append the index to the queue
    eb.asm_alloc('''
            lui $t0, 0x%x
            addiu $t0, $t0, %d
            lw $t1, 0($t0)
            sltiu $t2, $t1, %d
            beqz $t2, ld_done
            sll $t2, $t1, 2
            addu $t2, $t0, $t2
            sw $a1, 4($t2)
            addiu $t1, $t1, 1
            sw $t1, 0($t0)
        ld_done:
            jr $ra
            nop
    ''' % (qh, struct.unpack('<h', struct.pack('<H', ql))[0], MAX_LOST), 'lost_defer')
    # lost_flush(a0..a3 = arguments of TASK_NEXT): remove the queued characters, then tail-call TASK_NEXT
    eb.asm_alloc('''
            addiu $sp, $sp, -0x30
            sw $ra, 0x2c($sp)
            sw $s0, 0x28($sp)
            sw $s1, 0x24($sp)
            sw $a0, 0x10($sp)
            sw $a1, 0x14($sp)
            sw $a2, 0x18($sp)
            sw $a3, 0x1c($sp)
            lui $s0, 0x%x
            addiu $s0, $s0, %d
            lw $s1, 0($s0)
            sw $zero, 0($s0)
        lf_loop:
            beqz $s1, lf_out
            addiu $s1, $s1, -1
            sll $t0, $s1, 2
            addu $t0, $s0, $t0
            lw $a1, 4($t0)
            lui $t1, 0x%x
            lw $a0, %d($t1)
            jal 0x%08x
            move $a2, $zero
            b lf_loop
            nop
        lf_out:
            lw $a0, 0x10($sp)
            lw $a1, 0x14($sp)
            lw $a2, 0x18($sp)
            lw $a3, 0x1c($sp)
            lw $s1, 0x24($sp)
            lw $s0, 0x28($sp)
            lw $ra, 0x2c($sp)
            j 0x%08x
            addiu $sp, $sp, 0x30
    ''' % (qh, struct.unpack('<h', struct.pack('<H', ql))[0], rh, struct.unpack('<h', struct.pack('<H', rl))[0],
           REMOVE_CHAR, TASK_NEXT), 'lost_flush')
    eb.asm(SITE_REMOVE, 'jal @lost_defer', expect=1)
    eb.asm(TASK_DONE, 'jal @lost_flush', expect=1)


NPC_FIRST_PICK = 0x0884F5A0     # 'bnel $v1, $v0, 0x884f5e0' (skip the NPC check unless list mode 1)


def npc_swap(eb):
    """npc_swap: swapping an NPC with a PC in the Training Hall lists swaps their NPC status
    -------------------------------------------------------------------------------------
    Roster slots 0x00-0x6B are player characters, 0x6C-0x6E the unique characters (NPCs); being an NPC
    is the slot, not the record. Square in a Training Hall list (Training Hall code 0x0884F000-0x08850200,
    state *(u32 *)0x08BE7094: list entries at +0x3256, cursor +0x31C, list mode at +0x3354) picks the first character (+0x2208) and Square again swaps
    the two 0x3D0-byte records (0x0884E324). The second pick is always refused for an NPC slot (message
    0x60 "An NPC's place in the list can't be changed", 0x088500A0), but the first pick only in the Roster
    list (mode 1, 0x0884F598); Edit Profile lists the NPCs too, so NPC first, then a PC, swapped the
    records: the PC became an NPC and the unique character a PC (wiki: then the NPC's personality
    comment, extra skill, face / style load could be edited).
    Fix: the branch that skips the first-pick check outside mode 1 becomes a nop, so the check runs in
    every list; its delay slot (a0 = 1) is what both paths already do next. An NPC picked first could
    never be swapped legitimately (the second pick refuses NPC slots). One instruction."""
    assert eb.u32(NPC_FIRST_PICK) == 0x5462000F, hex(eb.u32(NPC_FIRST_PICK))      # bnel v1, v0, +0xF
    assert eb.u32(NPC_FIRST_PICK - 8) == 0x92033354                                 # lbu v1, 0x3354(s0)
    assert eb.u32(NPC_FIRST_PICK + 0x18) == 0x2842006C                              # slti v0, v0, 0x6c
    eb.asm(NPC_FIRST_PICK, 'nop', expect=1)


MAP_FILE = os.path.join(ROOT, 'work', 'source', 'arc', 'PARTS', '01_67.DAT')
MAP_SIZE = 0x1900                # 20 x 20 cells of 16 bytes, row 0 = y 19 (north), column = x
# walls: byte 4 north, 5 east, 6 south, 7 west; low 3 bits type (0 open, 2 wall, 5 door, 6 outer wall),
# high bits texture; bytes 12-13 the cell event (edge exits all have one)
MAP_WALLS = [  # (floor, x, y, side byte, original, new, why)
    (53, 0, 9, 7, 0x00, 0xDE, 'Wind Castle 2F (Delita) west edge'),
    (53, 0, 8, 7, 0x00, 0xDE, 'Wind Castle 2F (Delita) west edge'),
    (53, 0, 7, 7, 0x00, 0xDE, 'Wind Castle 2F (Delita) west edge'),
]


def map_edges(info):
    """map_edges: walking off the map on Wind Castle 2F (Delita)
    -----------------------------------------------------------
    Floor maps: PARTS/01_67.DAT, floor n at (n - 1) * 0x1900 (loaded whole to 0x08C14ED0). Every open map
    edge on the 67 floors is an exit with a cell event, except (x0, y7-9) on floor 53: no west wall and no
    event, so the party could walk off the map ("can freeze or be lost in stone", wiki). Those three cells
    get the outer wall the edge has just north of them (0xDE, type 6). Data only."""
    d = bytearray(open(MAP_FILE, 'rb').read())
    for fl, x, y, side, old, new, why in MAP_WALLS:
        p = (fl - 1) * MAP_SIZE + ((19 - y) * 20 + x) * 16
        assert d[p + side] == old and d[p + 13] == 0, (fl, x, y, d[p:p + 16].hex())   # open, no event
        d[p + side] = new
    info['archives'].setdefault('PARTS', {})['01_67.DAT'] = bytes(d)


SET_HP = 0x0890F6CC               # (char, hp): HP = min(hp, max HP), at least 0
REVIVE_HALF = 0x088D6604         # battle Rizefus success: lw v0, 0x68(a0) (max HP), then a1 = max HP / 2


def revive_hp(eb):
    """revive_hp: revived at 0 HP
    -----------------------------
    Rizefus in battle (battle action routine 0x088D4708; success of the revive roll 0x08910DC0) sets HP
    to max HP / 2 with SET_HP. A character whose max HP fell to 1 (level drained to 1) came back alive
    with 0 HP (wiki: status screen garbled, dies to the next hit, even to skills that never kill).
    Rizefus outside battle (0x0884BB48: rand() % 9 + 1, capped at max HP) and Rizefade (9999, capped)
    were already at least 1. Fix: the half is at least 1. The old 'round toward zero for a negative
    max HP' pair is dropped (max HP is never negative; SET_HP keeps it >= 1). Four instructions."""
    want = [0x8C820068, 0x04410003, 0x00022843, 0x24420001, 0x00022843,
            0x0C000000 | (SET_HP >> 2 & 0x3ffffff), 0x00000000]
    got = [eb.u32(REVIVE_HALF + 4 * i) for i in range(7)]
    assert got == want, [hex(w) for w in got]
    eb.asm(REVIVE_HALF + 4, 'sra $a1, $v0, 1; bne $a1, $zero, rh_set; nop; addiu $a1, $zero, 1; rh_set:', expect=4)


SKILL_PICK = 0x08852020          # class change, Extra Skill list (mode 0x9A): jal 0x088211B8 ; sb v1, 0xDD(v0)
SKILL_CANCEL = 0x08852B4C        # 'Change to this class?' (mode 0x9B, 0x088529E4): No or Cross -> jal SET_MODE ; li a0, 0x99
SET_MODE = 0x0882F4BC
SE_PLAY = 0x088211B8


def class_skill(eb):
    """class_skill: Extra Skill changed by a cancelled class change
    ---------------------------------------------------------------
    Training Hall, Change Class (handler 0x0885075C, state *(u32 *)0x08BE7094, record +0x2E4, mode +0x2E8):
    class list (0x99) -> Extra Skill list for the new class (0x9A) -> 'Change to this class?' (0x9B) ->
    changed (0x9C). Picking the skill wrote it into the character record at once (+0xDD, the Extra Skill),
    and answering No or Cross at the prompt went back without undoing it, so the character kept the new
    class's skill in the old class (wiki: the skills of the two classes get swapped). Reproduced in PPSSPP:
    Grace (Fighter) -> Priest, pick a skill, No: +0xDD changed 0x74 -> 0x65 and stayed.
    Fix: the pick saves the record pointer and the old byte (skill_pick); the prompt's cancel path (No and
    Cross both end at 0x08852B4C, back to the class list) puts it back (skill_undo). Yes is unchanged (the
    class change keeps the picked skill itself, 0x08852A28-0x08852A3C)."""
    assert eb.u32(SKILL_PICK) == 0x0C000000 | (SE_PLAY >> 2 & 0x3ffffff)
    assert eb.u32(SKILL_PICK + 4) == 0xA04300DD                      # sb v1, 0xdd(v0)
    assert eb.u32(SKILL_CANCEL) == 0x0C000000 | (SET_MODE >> 2 & 0x3ffffff)
    assert eb.u32(SKILL_CANCEL + 4) == 0x24040099                     # addiu a0, zero, 0x99 (class list)
    sv = eb.alloc(bytes(8), 'class_skill_save', align=4)               # +0 record (0 = nothing saved), +4 old byte
    sh, sl = _hi_lo(sv)
    sl = struct.unpack('<h', struct.pack('<H', sl))[0]
    eb.asm_alloc('''
            lui $t0, 0x%x
            addiu $t0, $t0, %d
            lbu $t1, 0xdd($v0)
            sw $v0, 0($t0)
            sb $t1, 4($t0)
            sb $v1, 0xdd($v0)
            j 0x%08x
            nop
    ''' % (sh, sl, SE_PLAY), 'skill_pick')
    eb.asm_alloc('''
            lui $t0, 0x%x
            addiu $t0, $t0, %d
            lw $t1, 0($t0)
            beq $t1, $zero, su_done
            lbu $t2, 4($t0)
            sb $t2, 0xdd($t1)
            sw $zero, 0($t0)
        su_done:
            j 0x%08x
            nop
    ''' % (sh, sl, SET_MODE), 'skill_undo')
    eb.asm(SKILL_PICK, 'jal @skill_pick; nop', expect=2)
    eb.asm(SKILL_CANCEL, 'jal @skill_undo', expect=1)


FLEE_SITE = 0x088C1DCC           # battle action 'escape' (executor 0x088BFDC0, case at 0x088C1D84): jal FLEE_ROLL
FLEE_ROLL = 0x088BC4DC           # (slot) -> nonzero = this character escapes
NO_ESCAPE = 0x08DF8228           # battle flags, bit 0: escape forbidden (the Run command checks it, 0x088DD2EC)


def repeat_flee(eb):
    """repeat_flee: Command Repeat escapes from battles that forbid it
    -----------------------------------------------------------------
    In a battle where escape is forbidden (boss and event battles: flag 0x08DF8228 bit 0), choosing Run
    shows "Escape is forbidden in this battle." But Command Repeat (R) re-issues the commands of the last
    battle without that check, so a character whose last command was Run escaped (wiki: if the party is
    then wiped out, the escaped characters survive and the event goes on as if it had been won). The
    whole-party escape (0x088D20DC) already checks the flag.
    Fix: the single-character escape roll fails for a party slot (0-5) while the flag is set ("The escape
    failed."). Monsters (slots 6+) and battles that allow escape are unchanged."""
    assert eb.u32(FLEE_SITE) == 0x0C000000 | (FLEE_ROLL >> 2 & 0x3ffffff)
    nh, nl = _hi_lo(NO_ESCAPE)
    eb.asm_alloc('''
            slti $t0, $a0, 6
            beq $t0, $zero, fr_go
            lui $t1, 0x%x
            lbu $t1, %d($t1)
            andi $t1, $t1, 1
            beq $t1, $zero, fr_go
            nop
            jr $ra
            move $v0, $zero
        fr_go:
            j 0x%08x
            nop
    ''' % (nh, struct.unpack('<h', struct.pack('<H', nl))[0], FLEE_ROLL), 'flee_roll')
    eb.asm(FLEE_SITE, 'jal @flee_roll', expect=1)


PACT_ALL = 0x088D2DCC            # spell cast 0x088D2C1C: Spirit Pact upgrade 'addiu s6, zero, 3' (range -> all)
TARGET_ENEMIES = 300             # range 3 target value for 'all enemies' (else: the party, 0x088D34F4)


def pact_repeat(eb):
    """pact_repeat: Spirit Pact + Command Repeat casts at the party
    --------------------------------------------------------------
    Spell cast routine 0x088D2C1C (a0 slot, a1 spell, a2 target, s7 = target): with the Extra Skill Spirit
    Pact (0x68), an elemental attack spell of single (1) or group (2) range is cast at all (3), decided
    here at cast time (0x088D2D5C-0x088D2DCC). For range 3 the target is a side: 300 = the enemies,
    anything else = the party (0x088D34F4). The command menu knows the upgrade and stores 300, but
    Command Repeat re-issues the last battle's command, whose target is an enemy slot or group (100+n)
    if Spirit Pact was set after that command was entered (wiki: switched to Spirit Pact at the Training
    Hall, then every repeat fires the spell at the party until a command is entered by hand).
    Fix: where the range becomes 'all' through Spirit Pact, the target becomes 300 too. The upgrade only
    applies to attack spells, which only ever target enemies. Two instructions in the cave."""
    assert eb.u32(PACT_ALL) == 0x24160003, hex(eb.u32(PACT_ALL))           # addiu s6, zero, 3
    assert eb.u32(PACT_ALL + 4) == 0x24020001                               # addiu v0, zero, 1 (re-run, harmless)
    eb.asm_alloc('''
            addiu $s6, $zero, 3
            j 0x%08x
            addiu $s7, $zero, %d
    ''' % (PACT_ALL + 4, TARGET_ENEMIES), 'pact_all')
    eb.asm(PACT_ALL, 'j @pact_all', expect=1)


SP_CHANGE = 0x088C88BC           # (slot, old item, new item): turn the first inventory item 'old' into 'new'
SP_CHANGE_SUMMON = 0x088C895C    # (slot, summon, old item, new item): same, if that summon is out
SP_CALLS = {SP_CHANGE: (0x088C82CC, 0x088C8314, 0x088C83E8, 0x088C8720),
            SP_CHANGE_SUMMON: (0x088C8360, 0x088C837C, 0x088C8398, 0x088C83B4, 0x088C83D0)}


def sp_item(eb):
    """sp_item: SP release changes the wrong copy of an item
    -------------------------------------------------------
    Item SP effects (executor 0x088C7AC4, a1 -> s6 = inventory index of the item whose SP is released;
    effect = item +0x2E bits 3-9, table 0x08953A58) that transform the item call SP_CHANGE /
    SP_CHANGE_SUMMON, which search the 10 inventory slots (record +0x11A) for the FIRST item with the old
    id and change that one (0x088F6B20, then unequip it, 0x088F66FC). With two copies, the upper one
    changed even when the lower one was the equipped one that released its SP (wiki: two Mantles of
    Depravity, Succubus summoned, SP of the lower, equipped one: the other became the Black Dream Cloak).
    Fix: a wrapper around the 9 calls. When the item at s6 has the old id, the copies above it get bit 15
    set for the duration of the call (no item id uses it; the helpers read the inventory only in their
    search loop), so the search finds the item at s6; the marks are then removed. Other SP effects and the
    case where the item at s6 is not the one being changed are unchanged."""
    for f, sites in SP_CALLS.items():
        for va in sites:
            assert eb.u32(va) == 0x0C000000 | (f >> 2 & 0x3ffffff), hex(va)
    assert eb.u32(0x088C7AF4) == 0x00A0B021                  # move s6, a1 (only other write: the epilogue)
    # sp_mark(a0 slot, t8 old id): bit 15 on the copies of 'old' above index s6 if item[s6] == old
    eb.asm_alloc('''
            lw $t0, 0($a0)
            sltiu $t1, $s6, 10
            beq $t1, $zero, spm_done
            sll $t1, $s6, 1
            addu $t1, $t0, $t1
            lhu $t1, 0x11a($t1)
            bne $t1, $t8, spm_done
            move $t2, $zero
        spm_loop:
            beq $t2, $s6, spm_done
            sll $t3, $t2, 1
            addu $t3, $t0, $t3
            lhu $t4, 0x11a($t3)
            bne $t4, $t8, spm_next
            ori $t4, $t4, 0x8000
            sh $t4, 0x11a($t3)
        spm_next:
            b spm_loop
            addiu $t2, $t2, 1
        spm_done:
            jr $ra
            nop
    ''', 'sp_mark')
    # sp_unmark(a0 slot, t8 old id): marked copies back to 'old'
    eb.asm_alloc('''
            lw $t0, 0($a0)
            ori $t9, $t8, 0x8000
            move $t2, $zero
        spu_loop:
            sltiu $t1, $t2, 10
            beq $t1, $zero, spu_done
            sll $t3, $t2, 1
            addu $t3, $t0, $t3
            lhu $t4, 0x11a($t3)
            bne $t4, $t9, spu_next
            nop
            sh $t8, 0x11a($t3)
        spu_next:
            b spu_loop
            addiu $t2, $t2, 1
        spu_done:
            jr $ra
            nop
    ''', 'sp_unmark')
    for f, old_reg, name in ((SP_CHANGE, '$a1', 'sp_change'), (SP_CHANGE_SUMMON, '$a2', 'sp_change_summon')):
        eb.asm_alloc('''
                addiu $sp, $sp, -0x20
                sw $ra, 0x1c($sp)
                sw $a0, 0x08($sp)
                sw $a1, 0x0c($sp)
                sw $a2, 0x10($sp)
                sw $a3, 0x14($sp)
                jal @sp_mark
                move $t8, %s
                lw $a0, 0x08($sp)
                lw $a1, 0x0c($sp)
                lw $a2, 0x10($sp)
                jal 0x%08x
                lw $a3, 0x14($sp)
                sw $v0, 0x18($sp)
                lw $a0, 0x08($sp)
                lw $t8, %s
                jal @sp_unmark
                nop
                lw $v0, 0x18($sp)
                lw $ra, 0x1c($sp)
                jr $ra
                addiu $sp, $sp, 0x20
        ''' % (old_reg, f, {'$a1': '0x0c($sp)', '$a2': '0x10($sp)'}[old_reg]), name)
        for va in SP_CALLS[f]:
            eb.asm(va, 'jal @%s' % name, expect=1)


ALLY_MENU_CALL = 0x088E3070      # ally target picker 0x088E2EF8 (Guard and others): jal LIST_MENU ; li t0, 2
LIST_MENU = 0x088DBD04           # (state, pad, ?, entries, t0): battle list menu; cursor = MENU_CURSOR[mode]
MENU_MODE = 0x08E08B08           # s16: current battle menu mode
MENU_CURSOR = 0x08E08A2C         # s16[mode]: list index the menu opens on


def guard_cursor(eb):
    """guard_cursor: Guard target cursor one place off
    -------------------------------------------------
    The ally list of the Guard target menu (picker 0x088E2EF8, also used by two other ally pickers) is
    built from the living party and summons each time (12-byte entries at 0x0896E688, +4 battle slot,
    ended by slot -1). The menu opens on MENU_CURSOR[mode], a list index. After a revive or a summon
    (or a summon leaving) the list gains or loses an entry before the last target, so the same index is
    now the neighbour (wiki: one place to the left after a revive, a summon or a summon leaving).
    Fix: a wrapper around the menu call remembers per mode the index and the slot it was on when the
    menu closed. When the menu opens with the same index, the cursor goes to that slot's place in the new
    list (if it is still in the list). Nothing changes if the cursor was moved or reset elsewhere."""
    assert eb.u32(ALLY_MENU_CALL) == 0x0C000000 | (LIST_MENU >> 2 & 0x3ffffff)
    assert eb.u32(ALLY_MENU_CALL + 4) == 0x24080002                       # addiu t0, zero, 2
    tab = eb.alloc(bytes(4 * 64), 'guard_cursor_tab')                       # per mode: lo index, hi slot + 1
    th, tl = _hi_lo(tab)
    mh, ml = _hi_lo(MENU_MODE)
    ch, cl = _hi_lo(MENU_CURSOR)
    s = lambda v: struct.unpack('<h', struct.pack('<H', v))[0]
    eb.asm_alloc('''
            addiu $sp, $sp, -0x28
            sw $ra, 0x24($sp)
            sw $a0, 0x10($sp)
            sw $a1, 0x14($sp)
            sw $a2, 0x18($sp)
            sw $a3, 0x1c($sp)
            lui $t1, 0x%(mh)x
            lh $t1, %(ml)d($t1)
            sltiu $t2, $t1, 64
            beq $t2, $zero, gc_call
            sll $t2, $t1, 2
            lui $t3, 0x%(th)x
            addiu $t3, $t3, %(tl)d
            addu $t3, $t3, $t2
            lw $t3, 0($t3)
            srl $t4, $t3, 16
            beq $t4, $zero, gc_call
            addiu $t4, $t4, -1
            andi $t3, $t3, 0xffff
            sll $t2, $t1, 1
            lui $t5, 0x%(ch)x
            addiu $t5, $t5, %(cl)d
            addu $t5, $t5, $t2
            lh $t6, 0($t5)
            bne $t6, $t3, gc_call
            move $t7, $zero
            move $t2, $a3
        gc_find:
            lh $t6, 4($t2)
            bltz $t6, gc_call
            nop
            beq $t6, $t4, gc_found
            addiu $t2, $t2, 12
            b gc_find
            addiu $t7, $t7, 1
        gc_found:
            sh $t7, 0($t5)
        gc_call:
            jal 0x%(menu)08x
            addiu $t0, $zero, 2
            sw $v0, 0x20($sp)
            lui $t1, 0x%(mh)x
            lh $t1, %(ml)d($t1)
            sltiu $t2, $t1, 64
            beq $t2, $zero, gc_out
            sll $t2, $t1, 1
            lui $t5, 0x%(ch)x
            addiu $t5, $t5, %(cl)d
            addu $t5, $t5, $t2
            lh $t6, 0($t5)
            bltz $t6, gc_out
            lw $t2, 0x1c($sp)
            move $t7, $zero
        gc_walk:
            lh $t3, 4($t2)
            bltz $t3, gc_out
            nop
            beq $t7, $t6, gc_save
            addiu $t2, $t2, 12
            b gc_walk
            addiu $t7, $t7, 1
        gc_save:
            addiu $t3, $t3, 1
            sll $t3, $t3, 16
            or $t3, $t3, $t6
            sll $t2, $t1, 2
            lui $t4, 0x%(th)x
            addiu $t4, $t4, %(tl)d
            addu $t4, $t4, $t2
            sw $t3, 0($t4)
        gc_out:
            lw $v0, 0x20($sp)
            lw $ra, 0x24($sp)
            jr $ra
            addiu $sp, $sp, 0x28
    ''' % dict(mh=mh, ml=s(ml), th=th, tl=s(tl), ch=ch, cl=s(cl), menu=LIST_MENU), 'guard_menu')
    eb.asm(ALLY_MENU_CALL, 'jal @guard_menu', expect=1)


def apply(eb, info):
    lost_after_battle(eb)
    npc_swap(eb)
    map_edges(info)
    revive_hp(eb)
    class_skill(eb)
    repeat_flee(eb)
    pact_repeat(eb)
    sp_item(eb)
    guard_cursor(eb)
