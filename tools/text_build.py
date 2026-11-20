"""Insert translated script text without moving any script code.

Slot format for a translated string (original slot length L >= 7, includes terminator):
    1B 7D r0 r1 r2 l0 l1 <free space ...>
  r = signed 21-bit offset (7 bits per byte, |0x80) from the slot start to the first chunk,
  l = L (7 bits per byte, |0x80) = bytes the VM consumes.
Chunk: text bytes ... then 1B 7E r0 r1 r2 (continue at chunk_link_pos + r) or 1B 00 (end).
Chunks live in the free space of translated slots (and, if needed, in space appended to
the end of the SCD file). Short slots (L < 7) take the English inline, space-padded.

Hook: 0x08897804 (string parse/copy). If src starts 1B 7D the chain is copied into a temp
buffer, the original routine runs on it, and *consumed is set to L.
"""
import json
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scp
import textcodec

ROOT = scp.ROOT
SRC = os.path.join(ROOT, 'work', 'source', 'arc', 'SCP')
TR = os.path.join(ROOT, 'work', 'translation', 'en', 'scp')
PARSE = 0x08897804
PARSE_CONT = 0x0889780C
SCRIPT_BUF = 0x130000          # original bump buffer @0x08C88064: now holds SCDWMAP alone
CHAPTER_BUF = 0x80000          # new buffer (EBOOT bss) for the chapter / DL script file
NAME_TABLE = 0x089670EC        # script file name pointers; entry 0 = scdwmap.bin
MSG_MAX = 2000                 # dst buffer 0x08DB81D4 is 0x800 bytes
MARK, CONT = 0x7d, 0x7e
MARK4 = 0x79     # 4-byte slot form: 1B 79 r r (14-bit offset in 2-byte units, +-16 KB)
MARK6 = 0x7a     # 6-byte slot form: 1B 7A r r r L (one 7-bit length byte)
ESC4 = textcodec.ESC4


def enc7(v, n):
    return bytes(0x80 | ((v >> (7 * i)) & 0x7f) for i in range(n))


def enc_rel(rel):
    """rel = even target - (source & ~1), stored in 2-byte units (21-bit signed: +-2 MB)."""
    assert rel % 2 == 0, rel
    rel //= 2
    assert -(1 << 20) <= rel < (1 << 20), rel
    return enc7(rel & 0x1fffff, 3)


def atoms(b):
    """Split encoded text into indivisible units (SJIS pairs, escapes with operands)."""
    out = []
    i = 0
    while i < len(b):
        c = b[i]
        if c == 0x1b:
            n = 6 if b[i + 1] in ESC4 else 2
        elif 0x81 <= c <= 0x9f or 0xe0 <= c <= 0xfc:
            n = 2
        else:
            n = 1
        out.append(b[i:i + n])
        i += n
    return out


def prepare_en(s, kind=None, warn=None):
    s = s.replace('\r', '')
    for k, v in textcodec.FIX.items():
        s = s.replace(k, v)
    if kind == 'msg':
        s = s.replace('{w}' + chr(10), '{w}')
        s = wrap_msg(s, warn)
    return textcodec.encode(s)


MSG_WIDTH = 376          # px available in the message box (x 56..432)
MSG_LINES = 3            # lines per page; {w} = wait + newline, {p} = new page
INSERT_W = 64            # assumed width of a runtime insert ({0C:..} names, numbers)
_WIDTHS = None


def text_width(t):
    global _WIDTHS
    if _WIDTHS is None:
        import vwf
        _WIDTHS = vwf.text_widths()
    w = 0
    for m in re.finditer(r'\{[0-9A-F]{2}:[0-9A-F]{4}:[0-9A-F]{4}\}|\{[^}]*\}|.', t):
        g = m.group(0)
        if len(g) > 1:
            w += INSERT_W if ':' in g else 0
        else:
            w += _WIDTHS[ord(g)] if ord(g) < 0x80 else 16
    return w


def wrap_line(line):
    if text_width(line) <= MSG_WIDTH:
        return [line]          # fits: keep as written (incl. leading spaces used for centering)
    words = line.split(' ')
    out, cur = [], ''
    for wd in words:
        cand = wd if not cur else cur + ' ' + wd
        if cur and text_width(cand) > MSG_WIDTH:
            out.append(cur)
            cur = wd
        else:
            cur = cand
    out.append(cur)
    return out


def wrap_msg(s, warn=None):
    """Re-wrap each page to MSG_WIDTH; split pages longer than MSG_LINES with {w}{p}."""
    res = []
    for pg in s.split('{p}'):
        parts = re.split(r'(\n|\{w\})', pg)
        lines = []          # (text, terminator)
        for i in range(0, len(parts), 2):
            txt = parts[i]
            term = parts[i + 1] if i + 1 < len(parts) else ''
            wrapped = wrap_line(txt) if txt else ['']
            for j, wl in enumerate(wrapped):
                lines.append((wl, term if j == len(wrapped) - 1 else '\n'))
        if lines and lines[-1] == ('', ''):
            lines.pop()
        out = ''
        n = 0
        for wl, term in lines:
            if n == MSG_LINES:
                if warn is not None:
                    warn.append('page split')
                out = out.rstrip('\n')
                if not out.endswith('{w}'):
                    out += '{w}'
                out += '{p}'
                n = 0
            out += wl + term
            if term in ('\n', '{w}'):
                n += 1
        res.append(out)
    return '{p}'.join(res)


class Packer:
    def __init__(self, data):
        self.d = bytearray(data)
        self.free = []          # [start, end)

    def add_free(self, a, b):
        if b - a >= 6:
            self.free.append([a, b])

    def place(self, body):
        """Place encoded text (no terminator); return position of first chunk."""
        at = atoms(body) + [b'\x1b\x00']
        first = None
        link = None             # position of a pending 1B 7E link to patch
        while at:
            # best extent: the one that holds everything, else the largest
            need = sum(len(x) for x in at)
            self.free.sort(key=lambda e: e[1] - e[0])
            ext = next((e for e in self.free if e[1] - e[0] >= need), None)
            if ext is None:
                ext = self.free[-1] if self.free else None
            if ext is None or (ext[1] - ext[0] < need and ext[1] - ext[0] < 7):
                raise MemoryError('out of text space')
            if ext[0] & 1:
                ext[0] += 1
                if ext[1] - ext[0] < min(need, 7):
                    self.free.remove(ext)
                    continue
            start, end = ext
            p = start
            # fill: keep 5 bytes for a continuation unless the rest fits
            while at:
                rest = sum(len(x) for x in at)
                if p + rest <= end:
                    for x in at:
                        self.d[p:p + len(x)] = x
                        p += len(x)
                    at = []
                    break
                if p + len(at[0]) + 5 > end:
                    break
                x = at.pop(0)
                self.d[p:p + len(x)] = x
                p += len(x)
            if link is not None:
                self.d[link + 2:link + 5] = enc_rel(start - (link & ~1))
            if first is None:
                first = start
            if at:
                link = p
                self.d[p:p + 2] = bytes([0x1b, CONT])
                p += 5
            ext[0] = p
            if ext[1] - ext[0] < 6:
                self.free.remove(ext)
        return first


# ---------------------------------------------------------------------------------------------
# New Game font choice. In SCDWMAP 91101-ARG_TOP_IN.bin (Algrantz town entry), the new-game intro is
# the sub at +0x4079: +0x0508 fades the town screen out (op 83), the first picture (continent map) is set
# up, and the call at +0x40AB to +0x052B fades it in (op 84) right before the first narration. (A menu shown
# while faded out is invisible.) That call is redirected to a block placed in free text space of the same file
# (code and jump offsets are u16 from the sub-script base):
#   B:  0D switch var[FONT_VAR]: case 0 -> C        (0 = not asked yet)
#   R:  08 call 0x052B ; 09 return
#   C:  08 call 0x052B ; 08 call D ; 09 return      (popup over the map, before the narration)
#   D:  91(0) ; 92 choice(prompt, [Original -> J1, HD -> J2]) ; 09 return
#   J1: 8C(0) 91(1) 3D var[FONT_VAR] = 1 ; 09        J2: same with 2
# (each branch returns; D's own 09 covers both a call-like and a jump-like choice op).
# The 91 / 8C ops around the menu copy the game's own Yes/No menus (00003-WALK.bin @1d75).
# Only a new game runs the intro, so old saves keep var 0 = original font.
FONT_CHOICE = ('SCDWMAP.BIN', '91101-ARG_TOP_IN.bin', 0x40AB, 0x052B)   # file, sub, call site, its target
FONT_PROMPT = 'Choose the text font. HD is for emulators at 2x+.'
FONT_OPTIONS = ('Original pixel font', 'HD font')


def inject_font_choice(pk):
    import vwf
    name = FONT_CHOICE[1]
    sub = next((off, size) for n, off, size, _ in scp.parse_dir(bytes(pk.d)) if n == name)
    base = sub[0] + 4
    call = base + FONT_CHOICE[2]
    assert bytes(pk.d[call:call + 5]) == bytes.fromhex('080100') + struct.pack('<H', FONT_CHOICE[3]),         'unexpected call at %s +%x' % (name, FONT_CHOICE[2])
    orig = struct.unpack_from('<H', pk.d, call + 3)[0]
    var = vwf.FONT_VAR
    u16 = lambda v: struct.pack('<H', v)

    def block(B):
        r = lambda x: u16(x - base)
        H = bytes.fromhex
        lab = {}
        for pass_ in (0, 1):            # pass 0 measures label positions, pass 1 uses them
            out = bytearray()
            here = lambda k: lab.__setitem__(k, B + len(out))
            L = lambda k: r(lab.get(k, B))
            out += H('0d0300') + u16(var) + u16(0) + L('C') + H('ffffffff')      # switch var: 0 -> C
            out += H('080100') + u16(orig) + H('09')                             # R: call orig; return
            here('C')
            out += H('080100') + u16(orig) + H('080100') + L('D') + H('09')      # C: call orig; call D
            here('D')
            out += H('9101000000')                                               # D: message window
            out += H('921500') + u16(2) + L('P') + u16(0)                        # choice: 2, prompt, 0
            out += H('00') + L('T1') + L('J1') + H('01') + L('T2') + L('J2')
            out += H('09')
            for k, val in (('J1', 1), ('J2', 2)):
                here(k)
                out += H('8c01000000') + H('9101000100')                         # as the game's menus
                out += H('3d0900') + u16(var) + struct.pack('<I', val) + H('09')  # var = val; return
            here('P')
            out += prepare_en(FONT_PROMPT) + H('1b00')       # one line: no wrap in menus
            for k, t in zip(('T1', 'T2'), FONT_OPTIONS):
                here(k)
                out += prepare_en(t) + H('1b00')
        return bytes(out)

    size = len(block(base))
    cand = [e for e in pk.free if e[1] - e[0] >= size + 1 and base <= e[0] and e[1] <= base + 0xFFF0]
    if not cand:
        raise MemoryError('no free space for the font choice block')
    ext = min(cand, key=lambda e: e[1] - e[0])
    B = (ext[0] + 1) // 2 * 2
    blob = block(B)
    pk.d[B:B + len(blob)] = blob
    ext[0] = B + len(blob)
    if ext[1] - ext[0] < 6:
        pk.free.remove(ext)
    pk.d[call + 3:call + 5] = u16(B - base)
    print('  font choice: %s +%x -> block @%x (%d bytes, var %d)' % (name, call - base, B - base, len(blob), var))


# ---------------------------------------------------------------------------------------------
# Fixes for bugs in the original scripts (docs: CHANGELOG). Each replaces the op at `site` (offset from
# the sub-script base, original bytes `expect`) with a jump to a block in free text space of the same
# file; the block holds `code` and jumps back to `back`. Code and jump offsets are u16 from the sub base.
SCRIPT_FIXES = [
    # Event 56 "Crumbling Stone Tablet" (EVENT_TEXT start flg_214b = flag 0x20D, end flg_214e = 0x210).
    # Historian (Santorea Academy faculty building, 29006): flag 0x20E (tablet read, set by 02002) is
    # checked before 0x20D (request accepted), so reading the tablet first finishes the event (0x210)
    # without ever setting its start flag, and the event list never shows it. The 'told the historian'
    # branch now also sets 0x20D (already set in the normal order).
    dict(file='SCD08.BIN', sub='29006.bin', site=0x4C1, expect='40050010020100',
         code='4005000d020100' '40050010020100', back=0x4C8, name='event 56 start flag'),
]


def inject_script_fixes(pk, fname):
    for fx in SCRIPT_FIXES:
        if fx['file'] != fname:
            continue
        sub = next((off, size) for n, off, size, _ in scp.parse_dir(bytes(pk.d)) if n == fx['sub'])
        base = sub[0] + 4
        site = base + fx['site']
        exp = bytes.fromhex(fx['expect'])
        assert bytes(pk.d[site:site + len(exp)]) == exp, 'unexpected bytes at %s +%x' % (fx['sub'], fx['site'])
        assert len(exp) >= 5, 'site too small for a jump'
        blob = bytes.fromhex(fx['code']) + bytes.fromhex('0a0100') + struct.pack('<H', fx['back'])
        cand = [e for e in pk.free if (e[0] + 1) // 2 * 2 + len(blob) <= e[1]
                and base < e[0] and e[1] <= base + 0xFFF0]
        if not cand:
            raise MemoryError('no free space for script fix: %s' % fx['name'])
        ext = min(cand, key=lambda e: e[1] - e[0])
        B = (ext[0] + 1) // 2 * 2
        pk.d[B:B + len(blob)] = blob
        ext[0] = B + len(blob)
        if ext[1] - ext[0] < 6:
            pk.free.remove(ext)
        pk.d[site:site + 5] = bytes.fromhex('0a0100') + struct.pack('<H', B - base)   # rest of site: dead
        print('  script fix: %s (%s +%x -> @%x)' % (fx['name'], fx['sub'], fx['site'], B - base))


def build_file(fname, entries, font_choice=False):
    d = open(os.path.join(SRC, fname), 'rb').read()
    pk = Packer(d)
    todo = []
    four = []
    stats = dict(translated=0, inline=0, skipped_short=0)
    for e in entries:
        en = e.get('en') or ''
        if not en.strip():
            continue
        sub, pos = e['id'].rsplit('@', 1)
        a = int(pos, 16)
        L = e['len']
        warn = []
        body = prepare_en(en, e.get('kind'), warn)
        if warn:
            stats['page_split'] = stats.get('page_split', 0) + 1
            print('  page split: %s' % e['id'])
        if len(body) + 2 > MSG_MAX:
            raise ValueError('%s: text too long (%d bytes)' % (e['id'], len(body)))
        if L == 4 and len(body) + 2 > L:
            four.append((a, body))
            continue
        if L == 6 and len(body) + 2 > L:
            pk.d[a:a + 2] = bytes([0x1b, MARK6])
            pk.d[a + 5:a + 6] = enc7(L, 1)
            todo.append((a, body))
            stats['translated'] += 1
            continue
        if L < 7:
            if len(body) + 2 <= L:
                pk.d[a:a + L] = body + b' ' * (L - 2 - len(body)) + b'\x1b\x00'
                stats['inline'] += 1
            else:
                stats['skipped_short'] += 1
                print('  short slot, kept JP: %s (%d bytes, en needs %d)' % (e['id'], L, len(body) + 2))
            continue
        pk.d[a:a + 2] = bytes([0x1b, MARK])
        pk.d[a + 5:a + 7] = enc7(L, 2)
        pk.add_free(a + 7, a + L)
        todo.append((a, body))
        stats['translated'] += 1
    if font_choice and fname == FONT_CHOICE[0]:
        inject_font_choice(pk)
    inject_script_fixes(pk, fname)
    # 4-byte slots need their text within +-16 KB: take a nearby free extent (whole body)
    for a, body in four:
        blob = body + bytes([0x1b, 0x00])
        cand = [e for e in pk.free if (e[0] + 1) // 2 * 2 + len(blob) <= e[1]
                and abs((e[0] + 1) // 2 * 2 - (a & ~1)) < 16000]
        if not cand:
            stats['skipped_short'] += 1
            print('  short slot, kept JP (no space nearby): %x' % a)
            continue
        ext = min(cand, key=lambda e: abs(e[0] - a))
        start = (ext[0] + 1) // 2 * 2
        pk.d[start:start + len(blob)] = blob
        ext[0] = start + len(blob)
        if ext[1] - ext[0] < 6:
            pk.free.remove(ext)
        rel = (start - (a & ~1)) // 2
        pk.d[a:a + 4] = bytes([0x1b, MARK4]) + enc7(rel & 0x3fff, 2)
        stats['translated'] += 1
    # long strings first gives better packing
    for a, body in sorted(todo, key=lambda t: -len(t[1])):
        try:
            first = pk.place(body)
        except MemoryError:
            # grow the file: append space for the remainder
            pk.d += b'\0' * 0x4000
            pk.add_free(len(pk.d) - 0x4000, len(pk.d))
            first = pk.place(body)
        pk.d[a + 2:a + 5] = enc_rel(first - (a & ~1))
    while pk.d and len(pk.d) > len(d) and pk.d[-1] == 0:
        pk.d.pop()
    return bytes(pk.d), stats


HOOK_ASM = '''
    lbu $at, 0($a2)
    addiu $t9, $zero, 0x1b
    bne $at, $t9, scp_pass
    lbu $at, 1($a2)
    addiu $t9, $zero, 0x7d
    beq $at, $t9, scp_marked
    addiu $t9, $zero, 0x7a
    beq $at, $t9, scp_marked
    addiu $t9, $zero, 0x79
    beq $at, $t9, scp_marked
    nop
scp_pass:
    addiu $sp, $sp, -0x50
    j 0x{cont:08x}
    sw $ra, 0x2c($sp)
scp_marked:
    addiu $sp, $sp, -0x20
    sw $ra, 0x10($sp)
    sw $s0, 0x14($sp)
    sw $s1, 0x18($sp)
    sw $s2, 0x1c($sp)
    move $s0, $t0
    lbu $at, 1($a2)
    addiu $t9, $zero, 0x79
    bne $at, $t9, scp_m_long
    nop
    addiu $s1, $zero, 4
    lbu $t8, 2($a2)
    andi $t8, $t8, 0x7f
    lbu $at, 3($a2)
    andi $at, $at, 0x7f
    sll $at, $at, 7
    or $t8, $t8, $at
    sll $t8, $t8, 18
    sra $t8, $t8, 17
    addiu $at, $zero, -2
    and $t9, $a2, $at
    b scp_follow_done
    addu $t9, $t9, $t8
scp_m_long:
    lbu $s1, 5($a2)
    andi $s1, $s1, 0x7f
    lbu $at, 1($a2)
    addiu $t9, $zero, 0x7a
    beq $at, $t9, scp_len_done
    lbu $at, 6($a2)
    andi $at, $at, 0x7f
    sll $at, $at, 7
    or $s1, $s1, $at
scp_len_done:
    move $t9, $a2
scp_follow:
    lbu $t8, 2($t9)
    andi $t8, $t8, 0x7f
    lbu $at, 3($t9)
    andi $at, $at, 0x7f
    sll $at, $at, 7
    or $t8, $t8, $at
    lbu $at, 4($t9)
    andi $at, $at, 0x7f
    sll $at, $at, 14
    or $t8, $t8, $at
    sll $t8, $t8, 11
    sra $t8, $t8, 10
    addiu $at, $zero, -2
    and $t9, $t9, $at
    addu $t9, $t9, $t8
scp_follow_done:
    lui $s2, 0x{tmp_hi:x}
    addiu $s2, $s2, {tmp_lo}
    lui $v1, 0x{tmp_hi:x}
    addiu $v1, $v1, {tmp_lo}
scp_copy:
    lbu $v0, 0($t9)
    addiu $at, $zero, 0x1b
    bne $v0, $at, scp_plain
    nop
    lbu $v0, 1($t9)
    addiu $at, $zero, 0x7e
    beq $v0, $at, scp_link
    addiu $at, $zero, 0x1b
    sb $at, 0($v1)
    sb $v0, 1($v1)
    addiu $v1, $v1, 2
    beq $v0, $zero, scp_done
    addiu $t9, $t9, 2
    addiu $t8, $v0, -0x0a
    sltiu $at, $t8, 10
    beq $at, $zero, scp_copy
    addiu $at, $zero, 1
    sllv $at, $at, $t8
    andi $at, $at, 0x3c7
    beq $at, $zero, scp_copy
    nop
    lbu $at, 0($t9)
    sb $at, 0($v1)
    lbu $at, 1($t9)
    sb $at, 1($v1)
    lbu $at, 2($t9)
    sb $at, 2($v1)
    lbu $at, 3($t9)
    sb $at, 3($v1)
    addiu $v1, $v1, 4
    b scp_copy
    addiu $t9, $t9, 4
scp_plain:
    sb $v0, 0($v1)
    addiu $v1, $v1, 1
    b scp_copy
    addiu $t9, $t9, 1
scp_link:
    lbu $t8, 2($t9)
    andi $t8, $t8, 0x7f
    lbu $at, 3($t9)
    andi $at, $at, 0x7f
    sll $at, $at, 7
    or $t8, $t8, $at
    lbu $at, 4($t9)
    andi $at, $at, 0x7f
    sll $at, $at, 14
    or $t8, $t8, $at
    sll $t8, $t8, 11
    sra $t8, $t8, 10
    addiu $at, $zero, -2
    and $t9, $t9, $at
    b scp_copy
    addu $t9, $t9, $t8
scp_done:
    move $a2, $s2
    move $t0, $s0
    addiu $sp, $sp, -0x50
    jal 0x{cont:08x}
    sw $ra, 0x2c($sp)
    beq $s0, $zero, scp_ret
    nop
    sw $s1, 0($s0)
scp_ret:
    lw $ra, 0x10($sp)
    lw $s0, 0x14($sp)
    lw $s1, 0x18($sp)
    lw $s2, 0x1c($sp)
    jr $ra
    addiu $sp, $sp, 0x20
'''


LOADER_ASM = '''
    lui $at, 0x{tab_hi:x}
    ori $at, $at, 0x{tab_lo:x}
    beq $s0, $at, ld_wmap
    nop
    lui $t8, 0x{chs_hi:x}
    sltu $at, $t8, $a2
    bne $at, $zero, ld_err
    nop
    lui $s1, 0x{buf_hi:x}
    addiu $s1, $s1, {buf_lo}
    lui $v0, 0x8dc
    lw $v1, -0x7f98($v0)
    j 0x088964d0
    nop
ld_err:
    j 0x0889649c
    nop
ld_wmap:
    lui $v0, 0x8dc
    j 0x08896490
    lw $v0, -0x7f98($v0)
'''


def install_loader(eb):
    """Load chapter scripts into their own buffer; SCDWMAP keeps the whole original one.

    Loader 0x0889641C: a2 = size aligned to 0x40, s0 = &name_table[index]. Patched at
    0x08896488 (remaining-space check): for index != 0 the file goes to CHAPTER_BUF and the
    shared used/remaining counters are left alone (chapters always replace each other via the
    snapshot taken after SCDWMAP, 0x08896650).
    """
    buf = eb.bss(CHAPTER_BUF, 'scp_chapter_buf')
    lo = buf & 0xffff
    hi = ((buf + 0x8000) >> 16) & 0xffff
    if lo >= 0x8000:
        lo -= 0x10000
    eb.asm_alloc(LOADER_ASM.format(tab_hi=NAME_TABLE >> 16, tab_lo=NAME_TABLE & 0xffff,
                                   chs_hi=CHAPTER_BUF >> 16, buf_hi=hi, buf_lo=lo), 'scp_loader')
    eb.asm(0x08896488, 'j 0x%08x; nop' % eb.symbols['scp_loader'], expect=2)


def install_hook(eb):
    tmp = eb.reserve(0x1000, 'scp_tmp', align=16)
    lo = tmp & 0xffff
    hi = ((tmp + 0x8000) >> 16) & 0xffff
    if lo >= 0x8000:
        lo -= 0x10000
    eb.asm_alloc(HOOK_ASM.format(cont=PARSE_CONT, tmp_hi=hi, tmp_lo=lo), 'scp_hook')
    eb.asm(PARSE, 'j 0x%08x; nop' % eb.symbols['scp_hook'], expect=2)


def apply(eb, info, opts):
    install_hook(eb)
    install_loader(eb)
    out = {}
    sizes = {}
    for f in sorted(os.listdir(SRC)):
        tp = os.path.join(TR, f.replace('.BIN', '.json'))
        if not os.path.exists(tp):
            continue
        ents = json.load(open(tp, encoding='utf-8'))
        if not any((e.get('en') or '').strip() for e in ents):
            continue
        data, st = build_file(f, ents, info.get('font_choice', False))
        out[f] = data
        sizes[f] = len(data)
        print('  %s: %s, size %d -> %d' % (f, st, os.path.getsize(os.path.join(SRC, f)), len(data)))
    if out:
        info['archives'].setdefault('SCP', {}).update(out)
    # buffer checks: SCDWMAP alone in the original buffer, each chapter in CHAPTER_BUF
    allsz = {f: sizes.get(f, os.path.getsize(os.path.join(SRC, f))) for f in os.listdir(SRC)}
    al = lambda n: (n + 0x3f) & ~0x3f
    wm = al(allsz.pop('SCDWMAP.BIN'))
    worst_f = max(allsz, key=allsz.get)
    worst = al(allsz[worst_f])
    print('  script buffers: SCDWMAP %d / %d, largest chapter %s %d / %d bytes'
          % (wm, SCRIPT_BUF, worst_f, worst, CHAPTER_BUF))
    if wm > SCRIPT_BUF or worst > CHAPTER_BUF:
        raise MemoryError('script buffer overflow')
