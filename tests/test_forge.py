"""The forge walk on a synthetic archive: entries found by their blocks, no index, nothing packed."""

from __future__ import annotations

import struct

import pytest

from heat3d_ext_r6maps import forge


def _block(*chunks: bytes) -> bytes:
    head = forge.BLOCK + struct.pack("<HBII", 3, 0x0F, 0x80040000, len(chunks))
    head += b"".join(struct.pack("<II", len(c), len(c)) for c in chunks)
    return head + b"".join(b"\x00\x00\x00\x00" + c for c in chunks)


def _entry(resources: list[tuple[int, bytes]]) -> bytes:
    header = struct.pack("<I", len(resources)) + b"".join(struct.pack("<QI", rid, len(b)) for rid, b in resources)
    body = b"".join(b for _, b in resources)
    return _block(header) + _block(body[: len(body) // 2], body[len(body) // 2 :])


def _archive() -> bytes:
    # A header page whose table this reader does not use (noise here), then two entries.
    out = bytearray(forge.MAGIC + struct.pack("<I", 34) + bytes(range(256)) * 15)
    out += bytes(-len(out) % forge.PAGE)
    for entry in (_entry([(0x11, b"first resource"), (0x22, b"second")]), _entry([(0x33, b"x" * 5000)])):
        out += entry
        out += bytes(-len(out) % forge.PAGE)
    return bytes(out)


def test_walk_finds_entries_and_resources():
    data = _archive()
    entries = list(forge.walk(data))
    assert [e.start for e in entries] == [forge.PAGE, 2 * forge.PAGE]
    assert entries[0].resources == [(0x11, 14), (0x22, 6)]
    assert list(forge.resources(data, entries[0], None)) == [(0x11, b"first resource"), (0x22, b"second")]
    assert dict(forge.resources(data, entries[1], None))[0x33] == b"x" * 5000


def test_packed_chunk_needs_a_decompressor():
    data = bytearray(_archive())
    entry = next(forge.walk(bytes(data)))
    chunk = entry.blocks[0].chunks[0]
    # Mark the chunk packed (compressed size one smaller): the walk still frames it, unpacking asks for Oodle.
    table = entry.blocks[0].start + 19
    struct.pack_into("<II", data, table, chunk.size + 1, chunk.packed)
    with pytest.raises(forge.ForgeError):
        forge.unpack(bytes(data), forge.read_entry(bytes(data), entry.start), None)


def test_not_a_forge(tmp_path):
    p = tmp_path / "x.forge"
    p.write_bytes(b"nope" * 10)
    with pytest.raises(forge.ForgeError):
        forge.version(p)
