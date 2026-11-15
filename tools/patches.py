"""All EBOOT code patches. apply_all(eb, opts) -> info dict (archives to rebuild, etc.)."""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


def apply_all(eb, opts):
    info = {'archives': {}}
    no_install(eb)
    if 'novwf' not in opts:
        import vwf
        hd = 'nohd' not in opts          # HD font sheet + New Game font choice (default: original)
        if hd:
            import font_hd
            vwf.HD_WIDTHS = font_hd.hd_widths()
            if vwf.HD_WIDTHS:            # word wrap must fit either font: per-char max width
                orig = vwf.text_widths()
                vwf.TEXT_WIDTHS = [max(a, b) for a, b in zip(orig, vwf.HD_WIDTHS)]
        vwf.apply(eb, info)
        vwf.apply12(eb)
        vwf.apply_ticker(eb)             # pixel-based scrolling help text for VWF
        vwf.apply_fit(eb)                # fit-to-width lists (Sound List, Music Folder) use VWF widths
        import name_entry
        name_entry.apply(eb)            # Latin-only name entry, VWF display, ASCII names
        if hd:
            vwf.apply_hd(eb, info)
        info['font_choice'] = hd
    if 'notext' not in opts:
        import text_build
        text_build.apply(eb, info, opts)
        import csv_build
        csv_build.apply(info)
        import img_text
        for arc, files in img_text.archive_files().items():
            info['archives'].setdefault(arc, {}).update(files)
            print('    images: %s %d file(s)' % (arc, len(files)))
        text_checks(eb)
        csv_text(eb)
        alignment_letters(eb)
        import eboot_text
        for line in eboot_text.apply(eb)[:20]:
            print('   ', line)
    return info


def no_install(eb):
    """Never use (or create) the Memory Stick data install (SAVEDATA/ULJM05883_02_INST).

    The installed archives are PGD-encrypted copies of the ORIGINAL ETC/ANIME/BTL/PARTS/
    3DPARTS and would override the patched disc files. Mount check 0x0891B260: for each
    archive it tests ms0:/PSP/SAVEDATA/ULJM05883_02_INST/<name>; we force the 'not
    installed' branch (flag +8 = 0 -> read from disc), skip the install step, and keep the
    'missing' counter at 0 so the game reports success and never prompts to install.
    Real hardware: loads come from UMD only (slightly slower than an install).
    """
    eb.asm(0x0891B2F0, 'nop', expect=1)                 # was bnel v0,zero (installed -> use it)
    eb.asm(0x0891B2FC, 'j 0x0891B474; nop', expect=2)   # was beqz s5 (install) ; addiu s3,1


def text_checks(eb):
    """Code that compares displayed text with a fixed string (breaks once the text is English).

    0x08890C2C (script VM, message op): strncmp(msgbuf, eb@089668d0, 6) and, on a match,
    calls 0x088A6884(1). eb@089668d0 is the Japanese place name 'Above the clouds' (3 kanji =
    6 bytes). merge_ebt OVERRIDEs that string to exactly the English used by the script line
    (wmap 00003-WALK.bin@c01e, 'Above the clouds'); the length is raised to 16 so that only
    the full phrase matches, not every line starting with 'Above '.
    Real hardware: one immediate changed, no layout change.
    """
    eb.asm(0x08890C30, 'addiu $a2, $zero, 16', expect=1)   # was addiu a2, zero, 6
    # 0x0884030C: strncmp(name, eb@0895FA68, 2) skips records whose name starts with full-width
    # '（' (reserved entries). The key is now ASCII '(' and the English names read '(Reserve)', so
    # compare 1 byte. Real hardware: one immediate.
    eb.asm(0x08840310, 'addiu $a2, $zero, 1', expect=1)     # was addiu a2, zero, 2


def csv_text(eb):
    """CSV cell copy (0x08909B44, the only routine that copies cell text): bytes 0x1F and 0x1E,
    written by tools/csv_build.py for English ',' and '"', are stored as ',' and '"'.
    The hook replaces the delimiter test of the copy loop (0x08909BEC..0x08909C00).
    Real hardware: code in the cave only; the original data never contains 0x1E/0x1F.
    """
    eb.asm_alloc('''
            lb $a2, 0x199c($v0)
            sll $t0, $t1, 24
            sra $t0, $t0, 24
            beq $t0, $a2, cs_end
            nop
            beq $t0, $v1, cs_end
            nop
            addiu $at, $zero, 0x1f
            bne $t0, $at, cs_q
            addiu $at, $zero, 0x1e
            b cs_st
            addiu $t1, $zero, 0x2c
        cs_q:
            bne $t0, $at, cs_st
            nop
            addiu $t1, $zero, 0x22
        cs_st:
            sb $t1, 0($a0)
            j 0x08909bd0
            nop
        cs_end:
            j 0x08909c04
            nop
        ''', 'csv_cellcopy')
    eb.asm(0x08909BEC, 'j 0x%08x; nop' % eb.symbols['csv_cellcopy'], expect=2)


def alignment_letters(eb):
    """Alignment names (table 0x08973424: 16-byte records, +0 name) read Good / Neutral / Evil on the
    character sheet and in character creation. The item details screen draws the three names in
    1-kanji slots (loop at 0x088EBE20, s3 = 0x08973434, stride 16, reads +0 only): it gets its own
    copy of the three records whose names are the letters G / N / E.
    Real hardware: data and two immediates; no layout change.
    """
    src = 0x08973434
    recs = bytearray(eb.read(src, 48))
    for k, letter in enumerate((b'G', b'N', b'E')):
        p = eb.alloc(letter + bytes(3), align=4)
        struct.pack_into('<I', recs, 16 * k, p)
    t = eb.alloc(bytes(recs), align=4)
    lo = t & 0xffff
    eb.asm(0x088EBE18, 'lui $s3, 0x%x' % (((t + 0x8000) >> 16) & 0xffff), expect=1)
    eb.asm(0x088EBE20, 'addiu $s3, $s3, %d' % (lo - 0x10000 if lo >= 0x8000 else lo), expect=1)
