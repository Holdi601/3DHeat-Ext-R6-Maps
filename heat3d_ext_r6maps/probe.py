"""
Looking inside the forge archives while their layout is worked out:

    probe walk <file.forge>                     the entries, found by their blocks
    probe entry <file.forge> <offset> [-o dir]  one entry's resources (decompressed); -o writes each to a file
    probe types <file.forge>...                 resource kinds (first u32 of each resource) and their sizes

Read-only on the archives; anything written goes where `-o` says.
"""

from __future__ import annotations

import collections
import struct
import sys
from pathlib import Path

from . import forge, oodle


def head(body: bytes) -> tuple[int, int, int]:
    """(kind, id, start of the payload) of a resource: u16 n, u16, n bytes, u32 size, then kind:u32 id:u64."""
    n = struct.unpack_from("<H", body, 0)[0]
    at = 4 + n + 4
    if at + 12 > len(body):
        return 0, 0, 0
    kind, rid = struct.unpack_from("<IQ", body, at)
    return kind, rid, at


def _walk(args: list[str]) -> int:
    with forge.Forge(args[0]) as f:
        for e in f.entries():
            print(f"{e.start:#010x} {e.end - e.start:>10} {'known' if e.known else 'packed'} "
                  f"{len(e.resources):>5} res {e.size:>10} B {[hex(r) for r, _ in e.resources[:3]]}")
    return 0


def _entry(args: list[str]) -> int:
    out = Path(args[args.index("-o") + 1]) if "-o" in args else None
    with forge.Forge(args[0]) as f:
        e = forge.read_entry(f.data, int(args[1], 16), oodle.decompress)
        print(f"entry {e.start:#x}: {len(e.resources)} resources, {e.size} bytes, oodle {oodle.path()}")
        for i, (rid, body) in enumerate(forge.resources(f.data, e, oodle.decompress)):
            kind, own, at = head(body)
            print(f"  {i:4} {rid:#018x} {len(body):>9} kind {kind:#010x} {'=' if own == rid else '!'} {body[at+12:at+44].hex(' ')}")
            if out:
                out.mkdir(parents=True, exist_ok=True)
                (out / f"{i:04}_{rid:016x}.bin").write_bytes(body)
    return 0


def _types(args: list[str]) -> int:
    count: collections.Counter = collections.Counter()
    size: collections.Counter = collections.Counter()
    for a in args:
        with forge.Forge(a) as f:
            for e in f.entries(oodle.decompress):
                for rid, body in forge.resources(f.data, e, oodle.decompress):
                    kind = head(body)[0]
                    count[kind] += 1
                    size[kind] += len(body)
    for kind, n in count.most_common():
        print(f"{kind:#010x} {n:>7} {size[kind]:>12}")
    return 0


def _index(args: list[str]) -> int:
    """probe index <out.tsv> <forge>...: id, kind, size, archive, entry of every single-resource entry and every resource."""
    out = Path(args[0])
    lines = 0
    with open(out, "w", encoding="utf-8") as w:
        for a in args[1:]:
            with forge.Forge(a) as f:
                name = Path(a).name
                for e in f.entries(oodle.decompress):
                    if len(e.resources) == 1:
                        kind, own, _ = head(forge.first(f.data, e, oodle.decompress))
                        kind = head(forge.first(f.data, e, oodle.decompress))[0]
                        w.write("\t".join((f"{e.resources[0][0]:x}", f"{kind:08x}", str(e.resources[0][1]), name, f"{e.start:x}")) + "\n")
                        lines += 1
                    else:
                        for rid, body in forge.resources(f.data, e, oodle.decompress):
                            w.write("\t".join((f"{rid:x}", f"{head(body)[0]:08x}", str(len(body)), name, f"{e.start:x}")) + "\n")
                            lines += 1
            print(f"{name}: {lines} so far", file=sys.stderr)
    return 0


def _load_index(path: str) -> dict[int, tuple[str, int, str, int]]:
    out = {}
    with open(path, encoding="utf-8") as r:
        for line in r:
            rid, kind, size, name, start = line.rstrip("\n").split("\t")
            out[int(rid, 16)] = (kind, int(size), name, int(start, 16))
    return out


def _hits(body: bytes, ids) -> list[tuple[int, int]]:
    """(offset, id) of every 8-byte little-endian value in `body` that is one of `ids` (a sorted numpy array)."""
    import numpy as np

    out = []
    for shift in range(8):
        n = (len(body) - shift) // 8
        if n <= 0:
            continue
        v = np.frombuffer(body, "<u8", count=n, offset=shift)
        found = np.nonzero(np.isin(v, ids))[0]
        out += [(shift + 8 * int(i), int(v[i])) for i in found]
    return sorted(out)


def _refs(args: list[str]) -> int:
    """probe refs <index.tsv> <map.forge> [kind...]: which resources of the map name which indexed ids (by the ids' kind)."""
    import numpy as np

    index = _load_index(args[0])
    kinds_wanted = set(args[2:])
    ids = np.array(sorted(r for r, v in index.items() if not kinds_wanted or v[0] in kinds_wanted), dtype=np.uint64)
    by: collections.Counter = collections.Counter()
    hits: collections.Counter = collections.Counter()
    sample: dict = {}
    with forge.Forge(args[1]) as f:
        for e in f.entries(oodle.decompress):
            for rid, body in forge.resources(f.data, e, oodle.decompress):
                kind = head(body)[0]
                h = [(o, i) for o, i in _hits(body, ids) if i != rid]
                if h:
                    by[kind] += 1
                    for o, i in h:
                        hits[(kind, index[i][0])] += 1
                    sample.setdefault(kind, (e.start, rid, h[:4]))
    for (kind, target), n in hits.most_common(40):
        print(f"{kind:#010x} -> {target}: {n} refs in {by[kind]} resources; e.g. entry {sample[kind][0]:#x} res {sample[kind][1]:#x} at {[o for o, _ in sample[kind][2]]}")
    return 0


def main(argv: list[str]) -> int:
    probes = {"walk": _walk, "entry": _entry, "types": _types, "index": _index, "refs": _refs}
    if not argv or argv[0] not in probes:
        print(__doc__, file=sys.stderr)
        return 2
    return probes[argv[0]](argv[1:])
