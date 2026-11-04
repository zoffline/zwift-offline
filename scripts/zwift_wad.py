#!/usr/bin/env python3
"""Reads Zwift's .wad asset archives (Zwift.app data: ~/Library/Application Support/Zwift/assets/**/*.wad).

A .wad is one compressed stream (a QFS/RefPack style LZ) wrapped in a 0x100 byte header; the decompressed stream is a
0x2000 byte table followed by the files. Format worked out in https://gitlab.com/r3dey3/zwift-utils (BSD-3-Clause,
(c) 2021 Kenny K); this is an independent in-memory implementation of the same format.

Usage:  python3 scripts/zwift_wad.py list    roads.wad
        python3 scripts/zwift_wad.py extract roads.wad OUT_DIR [NAME_SUBSTRING]
        python3 scripts/zwift_wad.py cat     roads.wad Worlds/world1/road.xml
"""
import os
import struct
import sys
import zlib

HEADER_SIZE = 0x100
TABLE_SIZE = 0x2000          # a lookup table we do not need: files follow it
ENTRY_NAME_SIZE = 0x60
ENTRY_ALIGN = 0x40


class WadError(Exception):
    pass


def _simple_chunk(src, pos, out):
    """A run of literal bytes: length byte (+2), or 0 followed by a 16 bit length."""
    length = src[pos]
    pos += 1
    if length:
        length += 2
    else:
        length = src[pos] | (src[pos + 1] << 8)
        pos += 2
    out += src[pos:pos + length]
    return pos + length


def _copy_chunk(src, pos, out):
    """Back reference. Returns (new position, number of literal bytes that follow, 3 = a block ends here)."""
    b0 = src[pos]
    kind = b0 & 0xE0
    if kind < 0xC0:
        trailing = b0 & 3
        length = (b0 >> 5) + 4
        offset = src[pos + 1] | ((b0 & 0xC) << 6)
        pos += 2
    elif kind == 0xC0:
        b1 = src[pos + 1]
        trailing = b1 & 3
        length = (b0 & 0x1F) + 4
        offset = src[pos + 2] | ((b1 & 0xFC) << 6)
        pos += 3
    elif kind == 0xE0:
        length = (b0 & 0xF) + 3
        if b0 & 0xF:
            b1 = src[pos + 1]
            trailing = b1 & 3
            offset = src[pos + 2] | ((b1 & 0xFC | ((b0 & 0x10) << 4)) << 6)
            pos += 3
        else:
            length = src[pos + 1] + 18
            if length <= 0x12:        # extra long run: 16 bit length
                length = src[pos + 3] | (src[pos + 2] << 8)
                trailing = src[pos + 4] & 3
                offset = src[pos + 5] | ((src[pos + 4] & 0xFC | ((b0 & 0x10) << 4)) << 6)
                pos += 6
            else:
                trailing = src[pos + 2] & 3
                offset = src[pos + 3] | ((src[pos + 2] & 0xFC | ((b0 & 0x10) << 4)) << 6)
                pos += 4
    else:
        raise WadError('bad compressed block 0x%02x' % b0)
    start = len(out) - offset
    if start < 0:
        raise WadError('back reference before the start of the data')
    if offset >= length:
        out += out[start:start + length]
    else:                              # overlapping copy repeats the pattern
        for i in range(length):
            out.append(out[start + i])
    return pos, trailing


def decompress(src):
    out = bytearray()
    pos = _simple_chunk(src, 0, out)
    size = len(src)
    while pos < size:
        pos, trailing = _copy_chunk(src, pos, out)
        if trailing != 3 and pos < size:
            if trailing:
                out += src[pos:pos + trailing]
                pos += trailing
            else:
                pos = _simple_chunk(src, pos, out)
    return bytes(out)


def read_wad(path):
    """The decompressed contents of a .wad file (the CRC stored in the header is checked)."""
    with open(path, 'rb') as f:
        raw = f.read()
    if raw[:4] != b'ZWF!':
        raise WadError('%s is not a Zwift wad (no ZWF! header)' % path)
    crc, _version, size, comp_size = struct.unpack_from('<4I', raw, 0xF0)
    data = decompress(raw[HEADER_SIZE:HEADER_SIZE + comp_size])
    actual = zlib.crc32(data, 0xFFFFFFFF)     # the header holds a CRC-32 that starts from 0 instead of 0xFFFFFFFF
    if len(data) != size or actual != crc:
        raise WadError('%s: decompressed %d bytes (expected %d), crc %08x (expected %08x)' % (path, len(data), size, actual, crc))
    return data


def entries(data):
    """Yields (name, bytes) for every file in the decompressed wad."""
    pos = TABLE_SIZE
    while pos + 4 + ENTRY_NAME_SIZE + 8 + 0x54 <= len(data):
        name = data[pos + 4:pos + 4 + ENTRY_NAME_SIZE].split(b'\0')[0].decode('ascii', 'replace')
        size = struct.unpack_from('<I', data, pos + 4 + ENTRY_NAME_SIZE + 4)[0]
        start = pos + 4 + ENTRY_NAME_SIZE + 8 + 0x54
        yield name.replace('\\', '/'), data[start:start + size]
        pos = start + size
        pos += -size % ENTRY_ALIGN


def main(argv):
    if len(argv) < 3 or argv[1] not in ('list', 'extract', 'cat'):
        print(__doc__)
        return 1
    command, wad = argv[1], argv[2]
    files = list(entries(read_wad(wad)))
    if command == 'list':
        for name, content in files:
            print('%9d  %s' % (len(content), name))
    elif command == 'cat':
        sys.stdout.buffer.write(dict(files)[argv[3]])
    else:
        out_dir, only = argv[3], (argv[4] if len(argv) > 4 else '')
        for name, content in files:
            if only in name:
                target = os.path.join(out_dir, *name.split('/'))
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with open(target, 'wb') as f:
                    f.write(content)
        print('%d files' % len(files))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
