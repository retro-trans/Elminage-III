"""Game text <-> editable text.

Bytes are Shift-JIS with ESC (0x1B) control codes. Editable form:
  1B 0D -> "\\n" (newline)          1B 01 -> "{w}"  (wait for button / page)
  1B 04 -> "{p}" (new page/clear)   1B xx -> "{xx}" (other 2-byte codes, hex)
  1B xx aa bb cc dd (xx in ESC4)    -> "{xx:aabb:ccdd}" (runtime insert: u16 type, u16 value,
                                       shown as little-endian hex words)
  1B 00 terminator is not part of the text.
English text is ASCII; any leftover Japanese is kept as Shift-JIS.
"""
import re
import struct

ESC4 = {0x0a, 0x0b, 0x0c, 0x10, 0x11, 0x12, 0x13}  # 1B 0E/0F take no operands (emit 5/6)
NAMED = {0x0d: '\n', 0x01: '{w}', 0x04: '{p}'}
RNAMED = {'w': 0x01, 'p': 0x04}


def decode(b):
    """bytes (without terminator) -> str"""
    out = []
    i = 0
    while i < len(b):
        c = b[i]
        if c == 0x1b:
            x = b[i + 1]
            if x in ESC4:
                t, v = struct.unpack_from('<HH', b, i + 2)
                out.append('{%02X:%04X:%04X}' % (x, t, v))
                i += 6
            elif x in NAMED:
                out.append(NAMED[x])
                i += 2
            else:
                out.append('{%02X}' % x)
                i += 2
        elif 0x81 <= c <= 0x9f or 0xe0 <= c <= 0xfc:
            try:
                ch = b[i:i + 2].decode('cp932')
                if ch.encode('cp932') != b[i:i + 2]:
                    raise UnicodeError
                out.append(ch)
            except UnicodeError:
                out.append('{#%02X%02X}' % (b[i], b[i + 1] if i + 1 < len(b) else 0))
            i += 2
        elif c < 0x20 or c == 0x7f:
            out.append('{$%02X}' % c)
            i += 1
        elif c == ord('{'):
            out.append('{{')
            i += 1
        else:
            out.append(b[i:i + 1].decode('cp932', 'replace'))
            i += 1
    return ''.join(out)


TAG = re.compile(r'\{\{|\{#([0-9A-F]{4})\}|\{([0-9A-F]{2}):([0-9A-F]{4}):([0-9A-F]{4})\}|\{([0-9A-F]{2})\}|\{\$([0-9A-F]{2})\}|\{(w|p)\}|\n')


def encode(s):
    """str -> bytes (without terminator)"""
    out = bytearray()
    pos = 0
    for m in TAG.finditer(s):
        out += _plain(s[pos:m.start()])
        g = m.group(0)
        if g == '{{':
            out += b'{'
        elif g == '\n':
            out += b'\x1b\x0d'
        elif m.group(1):
            out += bytes.fromhex(m.group(1))
        elif m.group(2):
            out += bytes([0x1b, int(m.group(2), 16)]) + struct.pack('<HH', int(m.group(3), 16), int(m.group(4), 16))
        elif m.group(5):
            out += bytes([0x1b, int(m.group(5), 16)])
        elif m.group(6):
            out += bytes([int(m.group(6), 16)])
        elif m.group(7):
            out += bytes([0x1b, RNAMED[m.group(7)]])
        pos = m.end()
    out += _plain(s[pos:])
    return bytes(out)


# typographic characters the font cannot show -> ASCII
FIX = {'’': "'", '‘': "'", '“': '"', '”': '"', '—': '--', '–': '-',
       '…': '...', ' ': ' ', 'é': 'e', 'è': 'e', 'à': 'a', 'ü': 'u'}


def _plain(t):
    out = bytearray()
    for ch in t:
        try:
            out += ch.encode('cp932')
        except UnicodeError:
            out += FIX.get(ch, '?').encode('ascii')
    return bytes(out)


def has_jp(s):
    return any(ord(ch) > 0x7f for ch in s)
