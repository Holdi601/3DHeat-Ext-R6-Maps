"""
Siege's asset archives (`.forge`), read by walking their data, not their index.

    file      "scimitar\\0", version:u32 (33 or 34), header offset:u64, ...
              then a file table and the data, entries 4 KB aligned
    entry     a header block, then the data blocks
    block     magic 37 aa fb 57 99 fa 15 10, version:u16 (3),
              compression:u8 (0x0f), flags:u32 (0x80040000: chunks of at most
              256 KB), chunks:u32, per chunk (uncompressed:u32,
              compressed:u32), then per chunk checksum:u32 and its bytes; a
              chunk whose two sizes are equal is stored as it is
    header    the header block's data: count:u32, then per resource
              id:u64 and size:u32; the data blocks hold the resources one
              after the other, `sum(size)` bytes

The file table at the start is not read: every entry starts on a 4 KB
boundary with a block, so the entries are found by walking the data itself.
Entries found this way have their resource ids (from their header block) but
no names; what a resource is comes from its content.

Packed chunks are Oodle (they start `8c 0c`, Leviathan). Oodle is not part of
this package: `decompress` takes a function, and `oodle.py` finds a library
on the machine to supply one.

The layout was worked out here from the installed game's files. RainbowForge
(parzivail, no licence) once read older versions of these archives; it is
neither used nor copied.
"""

from __future__ import annotations

import mmap
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterator

MAGIC = b"scimitar\x00"
BLOCK = bytes.fromhex("37aafb5799fa1510")
PAGE = 0x1000
#: More chunks than this in one block is not a block (chunks are at most 256 KB, entries far smaller than 64 GB).
MAX_CHUNKS = 1 << 18

Decompress = Callable[[bytes, int], bytes]


class ForgeError(ValueError):
    pass


@dataclass
class Chunk:
    size: int  # uncompressed
    packed: int  # compressed (== size when stored)
    start: int  # the chunk's bytes in the file (after its checksum)

    @property
    def stored(self) -> bool:
        return self.size == self.packed


@dataclass
class Block:
    start: int
    end: int
    version: int
    compression: int
    chunks: list[Chunk]

    @property
    def size(self) -> int:
        return sum(c.size for c in self.chunks)


@dataclass
class Entry:
    start: int  # file offset of the header block
    end: int
    resources: list[tuple[int, int]]  # (id, size)
    blocks: list[Block] = field(default_factory=list)
    known: bool = True  # False: the header block is packed and was not read

    @property
    def size(self) -> int:
        return sum(s for _, s in self.resources)


def version(path: str | Path) -> int:
    with open(path, "rb") as f:
        head = f.read(13)
    if not head.startswith(MAGIC):
        raise ForgeError(f"{path} is not a forge archive")
    return struct.unpack_from("<I", head, 9)[0]


def read_block(data, at: int) -> Block:
    if data[at : at + 8] != BLOCK:
        raise ForgeError(f"no block at {at:#x}")
    ver, comp, _flags, n = struct.unpack_from("<HBII", data, at + 8)
    if not 0 < n <= MAX_CHUNKS:
        raise ForgeError(f"block at {at:#x} claims {n} chunks")
    table = at + 19
    if table + 8 * n > len(data):
        raise ForgeError(f"block at {at:#x} runs past the file")
    chunks = []
    p = table + 8 * n
    for k in range(n):
        size, packed = struct.unpack_from("<II", data, table + 8 * k)
        if packed > size + 64 and size:  # a packed chunk is never much bigger than its data
            raise ForgeError(f"block at {at:#x}: chunk {k} is {packed} bytes for {size}")
        chunks.append(Chunk(size, packed, p + 4))
        p += 4 + packed
    if p > len(data):
        raise ForgeError(f"block at {at:#x} runs past the file")
    return Block(at, p, ver, comp, chunks)


def _stored(data, block: Block) -> bytes:
    if not all(c.stored for c in block.chunks):
        raise ForgeError(f"block at {block.start:#x} is packed")
    return b"".join(bytes(data[c.start : c.start + c.size]) for c in block.chunks)


def read_entry(data, at: int, decompress: Decompress | None = None) -> Entry:
    """
    The entry whose header block starts at `at`, with its data blocks.

    A big entry's header block is itself packed; without a decompressor such
    an entry is still found, by taking the blocks that follow back to back,
    but its resources are left empty (`known` False).
    """
    head = read_block(data, at)
    if all(c.stored for c in head.chunks):
        raw = _stored(data, head)
    elif decompress is not None:
        raw = b"".join(decompress(bytes(data[c.start : c.start + c.packed]), c.size) if not c.stored
                       else bytes(data[c.start : c.start + c.size]) for c in head.chunks)
    else:
        entry = Entry(at, head.end, [], known=False)
        p = head.end
        while data[p : p + 8] == BLOCK:
            b = read_block(data, p)
            entry.blocks.append(b)
            p = b.end
        if not entry.blocks:
            raise ForgeError(f"entry at {at:#x}: a header block and no data")
        entry.end = p
        return entry
    if len(raw) < 4:
        raise ForgeError(f"entry at {at:#x}: header of {len(raw)} bytes")
    count = struct.unpack_from("<I", raw, 0)[0]
    if not 0 < count <= (len(raw) - 4) // 12:
        raise ForgeError(f"entry at {at:#x}: {count} resources in a {len(raw)}-byte header")
    resources = [struct.unpack_from("<QI", raw, 4 + 12 * i) for i in range(count)]
    entry = Entry(at, head.end, resources)
    want, have, p = entry.size, 0, head.end
    while have < want:
        b = read_block(data, p)
        entry.blocks.append(b)
        have += b.size
        p = b.end
    if have != want:
        raise ForgeError(f"entry at {at:#x}: {have} bytes of data for {want}")
    entry.end = p
    return entry


def walk(data, decompress: Decompress | None = None) -> Iterator[Entry]:
    """Every entry, in file order, found by its header block on a 4 KB boundary."""
    at = PAGE
    n = len(data)
    while at < n:
        if data[at : at + 8] == BLOCK:
            try:
                e = read_entry(data, at, decompress)
            except (ForgeError, struct.error):
                at += PAGE
                continue
            yield e
            at = max(at + PAGE, (e.end + PAGE - 1) // PAGE * PAGE)
        else:
            at += PAGE


def unpack(data, entry: Entry, decompress: Decompress | None) -> bytes:
    """An entry's data, its resources one after the other."""
    if not entry.known:
        raise ForgeError(f"entry at {entry.start:#x}: its header was not read")
    out = bytearray()
    for b in entry.blocks:
        for c in b.chunks:
            src = bytes(data[c.start : c.start + c.packed])
            if c.stored:
                out += src
            elif decompress is None:
                raise ForgeError(f"entry at {entry.start:#x} is packed and no decompressor was given")
            else:
                got = decompress(src, c.size)
                if len(got) != c.size:
                    raise ForgeError(f"entry at {entry.start:#x}: chunk gave {len(got)} bytes for {c.size}")
                out += got
    return bytes(out)


def head(body: bytes) -> tuple[int, int, int]:
    """
    (kind, id, start of the payload) of a resource:
    `n:u16, u16, n bytes, size:u32`, then the payload, which starts `kind:u32, id:u64`.
    """
    if len(body) < 4:
        return 0, 0, 0
    n = struct.unpack_from("<H", body, 0)[0]
    at = 4 + n + 4
    if at + 12 > len(body):
        return 0, 0, 0
    kind, rid = struct.unpack_from("<IQ", body, at)
    return kind, rid, at


def first(data, entry: Entry, decompress: Decompress | None) -> bytes:
    """The first data chunk of an entry: enough to see what its first resource is."""
    c = entry.blocks[0].chunks[0]
    src = bytes(data[c.start : c.start + c.packed])
    if c.stored:
        return src
    if decompress is None:
        raise ForgeError(f"entry at {entry.start:#x} is packed and no decompressor was given")
    return decompress(src, c.size)


def resources(data, entry: Entry, decompress: Decompress | None) -> Iterator[tuple[int, bytes]]:
    """(id, bytes) of each resource in an entry."""
    body = unpack(data, entry, decompress)
    p = 0
    for rid, size in entry.resources:
        yield rid, body[p : p + size]
        p += size


class Forge:
    """An archive opened read-only and mapped, walked lazily."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._file = open(self.path, "rb")
        self.data = mmap.mmap(self._file.fileno(), 0, access=mmap.ACCESS_READ)
        if self.data[:9] != MAGIC:
            self.close()
            raise ForgeError(f"{path} is not a forge archive")
        self.version = struct.unpack_from("<I", self.data, 9)[0]

    def entries(self, decompress: Decompress | None = None) -> Iterator[Entry]:
        return walk(self.data, decompress)

    def close(self) -> None:
        try:
            self.data.close()
        except (AttributeError, ValueError):
            pass
        self._file.close()

    def __enter__(self) -> "Forge":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
