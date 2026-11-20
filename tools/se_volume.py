"""Quieter sound effects: the menu confirm sound.

The sound effects are 198 VAG (PSP ADPCM) samples inside the executable, each with a 0x30-byte 'VAGp'
header (big-endian data size at +0x0C, name at +0x20: EL2PSP_SE_001 ... EL3_SE_198). The game plays them
with __sceSasSetVoice (import stub 0x0894DE70, called from 0x0894BD6C) straight from these addresses.
Seen in PPSSPP: O (confirm) in a menu plays EL2PSP_SE_001, cursor movement EL2PSP_SE_003.

A VAG frame is 16 bytes: byte 0 = predictor << 4 | shift, byte 1 = flags (7 = end), 14 bytes of 4-bit
samples; a sample is (nibble << 12) >> shift plus the predictor's mix of the last two outputs. Adding 1 to
the shift of every frame halves every output (the predictor input halves with it), so the sample is
exactly -6 dB without re-encoding: checked by decoding EL2PSP_SE_001, RMS ratio 0.50000, largest
difference from half the original 8.5 of 32768. A frame already at shift 12 (the largest) gets its
nibbles halved instead. Same size, same addresses; data only.
"""
import struct

SE_HALVE = {                     # sample name -> times to halve (1 = 50 %)
    'EL2PSP_SE_001': 1,          # menu confirm (O)
}


def find_vags(eb, lo=0x08990000, hi=0x08BC6000):
    """name -> (header va, data size) for the VAG samples in the executable."""
    out = {}
    blob = eb.read(lo, hi - lo)
    p = blob.find(b'VAGp')
    while p >= 0:
        size, = struct.unpack_from('>I', blob, p + 0x0C)
        name = blob[p + 0x20:p + 0x30].split(b'\0')[0].decode('ascii', 'replace')
        out[name] = (lo + p, size)
        p = blob.find(b'VAGp', p + 4)
    return out


def halve(data):
    d = bytearray(data)
    for i in range(0, len(d) - 15, 16):
        if d[i + 1] == 7 or not any(d[i + 2:i + 16]):
            continue                                   # end marker / silent frame
        shift = d[i] & 15
        if shift < 12:
            d[i] += 1
        else:                                          # no larger shift: halve the nibbles
            for k in range(i + 2, i + 16):
                lo_n, hi_n = d[k] & 15, d[k] >> 4
                lo_n = (lo_n - 16 if lo_n >= 8 else lo_n) // 2 & 15
                hi_n = (hi_n - 16 if hi_n >= 8 else hi_n) // 2 & 15
                d[k] = hi_n << 4 | lo_n
    return bytes(d)


def apply(eb):
    vags = find_vags(eb)
    assert len(vags) == 198, len(vags)
    for name, times in SE_HALVE.items():
        va, size = vags[name]
        data = eb.read(va + 0x30, size)
        for _ in range(times):
            data = halve(data)
        eb.write(va + 0x30, data)
        print('    sound: %s at %d%% volume' % (name, 100 >> times))
