"""Minimal PSP GIM reader/writer (enough for this game's fonts and UI sheets).

    python tools/gim.py topng in.GIM out.png
    python tools/gim.py info in.GIM

Supports image formats 0 (5650), 1 (5551), 2 (4444), 3 (8888), 4 (index4), 5 (index8),
swizzled or linear, with an RGBA palette block.
"""
import struct
import sys

import numpy as np


def _blocks(d, off, end):
    while off < end:
        bid, size, nxt, dataoff = struct.unpack_from('<HxxIII', d, off)
        yield bid, off, size, dataoff
        if bid in (2, 3):  # containers
            yield from _blocks(d, off + dataoff, off + size)
        off += nxt if nxt else size


def parse(d):
    assert d[:4] == b'MIG.', 'not a GIM'
    img = pal = None
    for bid, off, size, dataoff in _blocks(d, 0x10, len(d)):
        if bid in (4, 5):
            h = off + 0x10
            hlen, _, fmt, order, w, hgt, bpp, pw, ph = struct.unpack_from('<HHHHHHHHH', d, h)
            pix_start, = struct.unpack_from('<I', d, h + 0x1c)
            info = dict(off=off, hdr=h, fmt=fmt, swz=order, w=w, h=hgt, bpp=bpp, pw=pw, ph=ph,
                        data=h + pix_start, size=size)
            if bid == 4:
                img = info
            else:
                pal = info
    return img, pal


def _unswizzle(buf, width_bytes, height):
    out = bytearray(len(buf))
    bw = width_bytes // 16
    rowblocks = bw
    i = 0
    for by in range((height + 7) // 8):
        for bx in range(rowblocks):
            for y in range(8):
                yy = by * 8 + y
                if yy >= height:
                    i += 16
                    continue
                dst = yy * width_bytes + bx * 16
                out[dst:dst + 16] = buf[i:i + 16]
                i += 16
    return bytes(out)


def _swizzle(buf, width_bytes, height):
    out = bytearray(len(buf))
    rowblocks = width_bytes // 16
    i = 0
    for by in range((height + 7) // 8):
        for bx in range(rowblocks):
            for y in range(8):
                yy = by * 8 + y
                if yy < height:
                    src = yy * width_bytes + bx * 16
                    out[i:i + 16] = buf[src:src + 16]
                i += 16
    return bytes(out)


def _colors(raw, fmt):
    if fmt == 3:
        return np.frombuffer(raw, np.uint8).reshape(-1, 4)
    v = np.frombuffer(raw, '<u2').astype(np.uint32)
    if fmt == 0:
        r, g, b, a = (v & 31) * 255 // 31, (v >> 5 & 63) * 255 // 63, (v >> 11 & 31) * 255 // 31, v * 0 + 255
    elif fmt == 1:
        r, g, b, a = (v & 31) * 255 // 31, (v >> 5 & 31) * 255 // 31, (v >> 10 & 31) * 255 // 31, (v >> 15) * 255
    else:
        r, g, b, a = (v & 15) * 17, (v >> 4 & 15) * 17, (v >> 8 & 15) * 17, (v >> 12 & 15) * 17
    return np.stack([r, g, b, a], 1).astype(np.uint8)


def decode(d):
    """Return (rgba array HxWx4, index array or None, img info)."""
    img, pal = parse(d)
    w, h, fmt = img['w'], img['h'], img['fmt']
    bpp = {0: 16, 1: 16, 2: 16, 3: 32, 4: 4, 5: 8}[fmt]
    stride = ((w * bpp // 8) + 15) // 16 * 16
    rows = (h + 7) // 8 * 8 if img['swz'] else h
    raw = d[img['data']:img['data'] + stride * rows]
    if img['swz']:
        raw = _unswizzle(raw, stride, rows)
    idx = None
    if fmt in (4, 5):
        a = np.frombuffer(raw, np.uint8).reshape(rows, stride)
        if fmt == 4:
            a = np.stack([a & 15, a >> 4], 2).reshape(rows, stride * 2)
        idx = a[:h, :w]
        pr = d[pal['data']:pal['data'] + pal['w'] * (4 if pal['fmt'] == 3 else 2)]
        p = _colors(pr, pal['fmt'])
        rgba = p[idx]
    else:
        bp = bpp // 8
        rgba = _colors(raw, fmt).reshape(rows, stride // bp, 4)[:h, :w]
    return rgba, idx, img


def encode_index(d, idx):
    """Write an index array (same size as original) back into GIM bytes d."""
    img, _ = parse(d)
    w, h, fmt = img['w'], img['h'], img['fmt']
    bpp = 4 if fmt == 4 else 8
    stride = ((w * bpp // 8) + 15) // 16 * 16
    rows = (h + 7) // 8 * 8 if img['swz'] else h
    full = np.zeros((rows, stride * (2 if fmt == 4 else 1)), np.uint8)
    full[:h, :w] = idx
    if fmt == 4:
        full = (full[:, 0::2] & 15) | ((full[:, 1::2] & 15) << 4)
    raw = full.astype(np.uint8).tobytes()
    if img['swz']:
        raw = _swizzle(raw, stride, rows)
    out = bytearray(d)
    out[img['data']:img['data'] + len(raw)] = raw
    return bytes(out)


def write_index_resized(d, idx):
    """Return GIM bytes d with its index image replaced by idx (any size, same format/palette).

    Block sizes of the root, picture and image blocks and the header's pixel-end field are
    updated; everything after the pixel data (e.g. the file-info block) is moved along."""
    img, _ = parse(d)
    fmt = img['fmt']
    assert fmt in (4, 5)
    h, w = idx.shape
    bpp = 4 if fmt == 4 else 8
    stride = ((w * bpp // 8) + 15) // 16 * 16
    rows = (h + 7) // 8 * 8 if img['swz'] else h
    full = np.zeros((rows, stride * (2 if fmt == 4 else 1)), np.uint8)
    full[:h, :w] = idx
    if fmt == 4:
        full = (full[:, 0::2] & 15) | ((full[:, 1::2] & 15) << 4)
    raw = full.astype(np.uint8).tobytes()
    if img['swz']:
        raw = _swizzle(raw, stride, rows)
    old_w, old_h = img['w'], img['h']
    old_stride = ((old_w * bpp // 8) + 15) // 16 * 16
    old_rows = (old_h + 7) // 8 * 8 if img['swz'] else old_h
    old_len = old_stride * old_rows
    delta = len(raw) - old_len
    out = bytearray(d[:img['data']] + raw + d[img['data'] + old_len:])
    hdr = img['hdr']
    struct.pack_into('<HH', out, hdr + 8, w, h)
    pix_start, pix_end = struct.unpack_from('<II', out, hdr + 0x1c)
    struct.pack_into('<I', out, hdr + 0x20, pix_end + delta)
    # enclosing blocks: root (0x10), picture (contains image), image itself
    for bid, off, size, dataoff in list(_blocks(bytes(d), 0x10, len(d))):
        if off <= img['off'] < off + size or off == img['off']:
            nxt, = struct.unpack_from('<I', d, off + 8)
            struct.pack_into('<I', out, off + 4, size + delta)
            if nxt == size or off == img['off']:
                struct.pack_into('<I', out, off + 8, (nxt + delta) if nxt else 0)
    return bytes(out)


if __name__ == '__main__':
    from PIL import Image
    d = open(sys.argv[2], 'rb').read()
    if sys.argv[1] == 'info':
        print(parse(d))
    else:
        rgba, idx, img = decode(d)
        Image.fromarray(rgba, 'RGBA').save(sys.argv[3])
        print(img)
