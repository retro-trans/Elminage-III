"""Fixes for bugs of the original game (executable and map data). Script-side fixes: text_build.SCRIPT_FIXES.
Bug list: Elminage III wiki, 攻略/バグ. lost_after_battle, npc_swap and map_edges are its three "severe" bugs.

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


def apply(eb, info):
    lost_after_battle(eb)
    npc_swap(eb)
    map_edges(info)
