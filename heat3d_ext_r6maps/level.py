"""
A Siege map as level geometry, from the forge archives' unpacked resources.

    resource   `n:u16, u16, n bytes, size:u32`, then the payload `kind:u32, id:u64, ...`
    mesh       kind 0xABEB2DFB, in the mesh banks. After `kind, id, kind` (12 + 4
               bytes), u32 words: 0, 0, a constant, size, 0x14, LODs, vertex
               stride, vertex bytes, index bytes, ... and at +96 the buffer:
               positions first, one `x, y, z, s: int16` per vertex
               (position = xyz * s / 32768, s signed: a per-vertex scale),
               then the other vertex streams, then the triangles as u16
               indices (index bytes / 2 of them, in groups of 64 triangles,
               padded with repeats)
    wrapper    kind 0x7DFEB735, in the map: names one mesh (by id) and holds
               its bounds
    entity     kind 0x3ADFCF6C, in the map: `kind, id, kind`, then its 4x4
               world matrix (16 floats, columns, translation in 12-14), then
               its components, which name wrappers (one model) or groups of
               them (kind 0xADBF7FFE, several meshes: breakable objects)

The world matrix is in the frame the replays use: metres, Z up. The level is
written for the viewer the way the replay tables are drawn (up = z, no flips),
so the .glb holds (x, z, y).

All of this was worked out here from the installed game's files; no other
reader's code is used.
"""

from __future__ import annotations

import json
import struct
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

MESH = 0xABEB2DFB
WRAPPER = 0x7DFEB735
GROUP = 0xADBF7FFE
ENTITY = 0x3ADFCF6C
#: The map's world: its id is the replays' `worldid`.
WORLD = 0xB4F9751B
#: A material (named by wrappers after their mesh) and the texture slots it names.
MATERIAL = 0x505A2021
TEXTURE = 0x87CE3D94


def head(body: bytes) -> tuple[int, int, int]:
    if len(body) < 4:
        return 0, 0, 0
    n = struct.unpack_from("<H", body, 0)[0]
    at = 4 + n + 4
    if at + 12 > len(body):
        return 0, 0, 0
    kind, rid = struct.unpack_from("<IQ", body, at)
    return kind, rid, at


class Library:
    """Every unpacked archive's resources by id (`unpack.py`'s folders)."""

    def __init__(self, root: str | Path, kinds: tuple[int, ...] = (MESH, WRAPPER, GROUP, MATERIAL, TEXTURE)):
        self.root = Path(root)
        self.where: dict[int, tuple[Path, int]] = {}
        self._ids: dict[tuple[int, ...], np.ndarray] = {}
        wanted = {f"{k:08x}" for k in kinds}
        for idx in sorted(self.root.glob("*/index.json")):
            doc = json.loads(idx.read_text(encoding="utf-8"))
            for e in doc["entries"]:
                for r in e["resources"]:
                    if r["kind"] in wanted:
                        self.where.setdefault(int(r["id"], 16), (idx.parent / r["file"], int(r["kind"], 16)))

    def kind(self, rid: int) -> int | None:
        w = self.where.get(rid)
        return w[1] if w else None

    def read(self, rid: int) -> bytes:
        return self.where[rid][0].read_bytes()

    def ids_of(self, *kinds: int) -> np.ndarray:
        key = tuple(sorted(kinds))
        if key not in self._ids:
            self._ids[key] = np.array(sorted(i for i, (_, k) in self.where.items() if k in kinds), dtype=np.uint64)
        return self._ids[key]


def refs(body: bytes, ids: np.ndarray, start: int = 0) -> list[tuple[int, int]]:
    """(offset, value) of each 8-byte value from `start` on that is one of `ids` (sorted)."""
    out: list[tuple[int, int]] = []
    if not len(ids):
        return out
    for s in range(8):
        n = (len(body) - start - s) // 8
        if n <= 0:
            continue
        v = np.frombuffer(body, "<u8", count=n, offset=start + s)
        at = np.minimum(np.searchsorted(ids, v), len(ids) - 1)
        out += [(start + s + 8 * int(i), int(v[i])) for i in np.nonzero(ids[at] == v)[0]]
    return sorted(out)


def decode_mesh(body: bytes) -> tuple[np.ndarray, np.ndarray]:
    """(positions float32 [V, 3], triangles int32 [T, 3]) of a mesh's first level of detail."""
    kind, _, at = head(body)
    if kind != MESH:
        raise ValueError(f"not a mesh ({kind:#x})")
    w = struct.unpack_from("<24I", body, at + 12)
    stride, vbytes, ibytes = w[7], w[8], w[9]
    if not stride or vbytes % stride:
        raise ValueError("mesh with an unexpected vertex layout")
    count = vbytes // stride
    buf = at + 108
    q = np.frombuffer(body, "<i2", count=count * 4, offset=buf).reshape(count, 4).astype(np.float32)
    pos = q[:, :3] * (q[:, 3:4] / 32768.0)
    idx = np.frombuffer(body, "<u2", count=ibytes // 2, offset=buf + vbytes)
    tris = idx[: len(idx) // 3 * 3].reshape(-1, 3).astype(np.int32)
    keep = (tris[:, 0] != tris[:, 1]) & (tris[:, 1] != tris[:, 2]) & (tris[:, 0] != tris[:, 2]) & (tris.max(1) < count)
    tris = tris[keep]
    # The padding repeats triangles: keep each once, in order.
    _, first = np.unique(np.sort(tris, axis=1), axis=0, return_index=True)
    return pos, tris[np.sort(first)]


def matrix_of(body: bytes) -> np.ndarray | None:
    """An entity's world matrix (4x4, row-vector form: p' = [p, 1] @ M), or None."""
    kind, _, at = head(body)
    if at + 80 > len(body) or struct.unpack_from("<I", body, at + 12)[0] != kind:
        return None
    m = np.array(struct.unpack_from("<16f", body, at + 16), dtype=np.float64).reshape(4, 4)
    if not np.all(np.isfinite(m)) or abs(m[3, 3] - 1) > 1e-4 or np.abs(m[:3, 3]).max() > 1e-4:
        return None
    return m


def untextured(lib: Library, holder: int, cache: dict[int, bool]) -> bool:
    """
    Whether a wrapper draws its mesh only with materials that name no texture.

    Such materials dress the wide flat ground plates that run under and
    through a map's buildings.
    """
    if holder in cache:
        return cache[holder]
    mats = [v for _, v in refs(lib.read(holder), lib.ids_of(MATERIAL))] if lib.kind(holder) == WRAPPER else []
    textures = lib.ids_of(TEXTURE)
    cache[holder] = bool(mats) and all(not refs(lib.read(m), textures) for m in dict.fromkeys(mats))
    return cache[holder]


@dataclass
class Placed:
    entity: int
    mesh: int
    via: int  # the wrapper or group that named the mesh
    group: bool  # through a breakable group
    matrix: np.ndarray = field(repr=False)


def placements(lib: Library, map_folder: str | Path) -> list[Placed]:
    """Every mesh an entity of the map places, with its world matrix."""
    folder = Path(map_folder)
    doc = json.loads((folder / "index.json").read_text(encoding="utf-8"))
    holders = lib.ids_of(WRAPPER, GROUP)
    meshes = lib.ids_of(MESH)
    mesh_of: dict[int, list[int]] = {}
    out: list[Placed] = []
    for e in doc["entries"]:
        for r in e["resources"]:
            if int(r["kind"], 16) != ENTITY:
                continue
            body = (folder / r["file"]).read_bytes()
            m = matrix_of(body)
            if m is None:
                continue
            eid = int(r["id"], 16)
            for _, h in dict.fromkeys(refs(body, holders, 80)):
                if h not in mesh_of:
                    hb = lib.read(h)
                    mesh_of[h] = list(dict.fromkeys(v for _, v in refs(hb, meshes)))
                for mid in mesh_of[h]:
                    out.append(Placed(eid, mid, h, lib.kind(h) == GROUP, m))
    # One entity naming the same holder twice places it once.
    seen, unique = set(), []
    for p in out:
        key = (p.entity, p.mesh, p.via)
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return unique
