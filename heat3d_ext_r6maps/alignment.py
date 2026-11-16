"""
How well replays sit on a level: `heat3d-r6-maps check <level.glb> <match.3dheat>...`

For a sample of the players' positions (their feet), the surface right below
each one is found in the level, and the report gives:

- the median height of the feet above that surface (0 when the tracks stand on
  the floors) and how many samples are within 0.3 m of one;
- how many samples have no surface below at all (outside the level);
- how many have a surface between 0.4 and 1.6 m above the feet, i.e. stand
  inside something: once for all geometry and once without the breakable
  objects (a barricade broken in the match is still whole in the level) and
  the ground plates (which pass overhead in sunken rooms).
"""

from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path

import numpy as np

from . import glb

CELL = 1.0
SWAP = np.array([[1, 0, 0, 0], [0, 0, 1, 0], [0, 1, 0, 0], [0, 0, 0, 1]], dtype=np.float64)


def triangles(path: str | Path) -> tuple[np.ndarray, np.ndarray]:
    """Every triangle of a level in the replays' frame ([T, 3, 3]), and whether it is a breakable's or a plate's."""
    doc, blob = glb.read(path)
    tris, breakable = [], []
    cache: dict[int, np.ndarray] = {}
    for node in doc["nodes"]:
        if "mesh" not in node:
            continue
        mi = node["mesh"]
        if mi not in cache:
            prim = doc["meshes"][mi]["primitives"][0]
            pos = glb.accessor(doc, blob, prim["attributes"]["POSITION"]).astype(np.float64)
            idx = glb.accessor(doc, blob, prim["indices"]).astype(np.int64).reshape(-1, 3)
            cache[mi] = pos[idx]
        local = cache[mi]
        m = np.array(node.get("matrix", np.eye(4).reshape(-1).tolist()), dtype=np.float64).reshape(4, 4).T
        game = SWAP @ m @ SWAP  # back to the replays' frame (x, y, z up)
        flat = local.reshape(-1, 3)[:, [0, 2, 1]]
        world = flat @ game[:3, :3].T + game[:3, 3]
        tris.append(world.reshape(-1, 3, 3))
        name = node.get("name", "")
        breakable.append(np.full(len(local), " breakable " in name or name.endswith(" plate")))
    return np.concatenate(tris), np.concatenate(breakable)


def positions(match: str | Path, limit: int = 20000, seed: int = 1) -> np.ndarray:
    """A sample of the operators' positions in a converted match (.3dheat)."""
    import pyarrow.parquet as pq

    with zipfile.ZipFile(match) as z:
        name = next(n for n in z.namelist() if n.endswith(".parquet") and n.count(".") == 1)
        t = pq.read_table(io.BytesIO(z.read(name)), columns=["x", "y", "z", "event", "pawn"]).to_pandas()
    p = t[(t.event == "position") & (t.pawn == "operator")][["x", "y", "z"]].to_numpy(dtype=np.float64)
    if len(p) > limit:
        p = p[np.random.default_rng(seed).choice(len(p), limit, replace=False)]
    return p


class Grid:
    """Triangles binned by the 1 m cells their footprint covers."""

    def __init__(self, tris: np.ndarray, near: np.ndarray, margin: float = 5.0):
        lo, hi = tris.min(1), tris.max(1)
        keep = (hi[:, 0] > near[:, 0].min() - margin) & (lo[:, 0] < near[:, 0].max() + margin) & \
               (hi[:, 1] > near[:, 1].min() - margin) & (lo[:, 1] < near[:, 1].max() + margin) & \
               ((hi - lo)[:, :2].max(1) < 80)
        self.tris = tris
        ids = np.nonzero(keep)[0]
        x0, x1 = np.floor(lo[ids, 0] / CELL).astype(np.int64), np.floor(hi[ids, 0] / CELL).astype(np.int64)
        y0, y1 = np.floor(lo[ids, 1] / CELL).astype(np.int64), np.floor(hi[ids, 1] / CELL).astype(np.int64)
        keys, owners = [], []
        for dx in range(int((x1 - x0).max(initial=0)) + 1):
            for dy in range(int((y1 - y0).max(initial=0)) + 1):
                m = (x0 + dx <= x1) & (y0 + dy <= y1)
                keys.append((x0[m] + dx) * 1_000_003 + (y0[m] + dy))
                owners.append(ids[m])
        k = np.concatenate(keys) if keys else np.zeros(0, np.int64)
        o = np.concatenate(owners) if owners else np.zeros(0, np.int64)
        order = np.argsort(k, kind="stable")
        self.keys, self.owners = k[order], o[order]

    def heights(self, x: float, y: float) -> tuple[np.ndarray, np.ndarray]:
        """(surface heights at (x, y), the triangles they are on)."""
        key = int(np.floor(x / CELL)) * 1_000_003 + int(np.floor(y / CELL))
        a, b = np.searchsorted(self.keys, key), np.searchsorted(self.keys, key, side="right")
        ids = self.owners[a:b]
        if not len(ids):
            return np.zeros(0), ids
        t = self.tris[ids]
        v0, v1 = t[:, 1] - t[:, 0], t[:, 2] - t[:, 0]
        d = np.array([x, y]) - t[:, 0, :2]
        den = v0[:, 0] * v1[:, 1] - v1[:, 0] * v0[:, 1]
        ok = np.abs(den) > 1e-12
        den = np.where(ok, den, 1.0)
        u = (d[:, 0] * v1[:, 1] - v1[:, 0] * d[:, 1]) / den
        v = (v0[:, 0] * d[:, 1] - d[:, 0] * v0[:, 1]) / den
        inside = ok & (u >= -1e-6) & (v >= -1e-6) & (u + v <= 1 + 1e-6)
        z = t[:, 0, 2] + u * v0[:, 2] + v * v1[:, 2]
        return z[inside], ids[inside]


def check(level_path: str | Path, matches: list[str | Path], limit: int = 20000) -> dict:
    tris, breakable = triangles(level_path)
    feet = np.concatenate([positions(m, limit // max(len(matches), 1)) for m in matches])
    grid = Grid(tris, feet)
    above, none, inside, inside_static = [], 0, 0, 0
    for x, y, z in feet:
        h, ids = grid.heights(x, y)
        below = h[h <= z + 0.25]
        if not len(below):
            none += 1
            continue
        above.append(z - below.max())
        hit = (h > z + 0.4) & (h < z + 1.6)
        inside += bool(hit.any())
        inside_static += bool((hit & ~breakable[ids]).any())
    above = np.array(above)
    n = len(feet)
    return {
        "samples": n,
        "median_above_floor_m": round(float(np.median(above)), 3) if len(above) else None,
        "p10_p90_m": [round(float(v), 3) for v in np.percentile(above, [10, 90])] if len(above) else None,
        "within_0_3m_pct": round(100 * float(np.mean(np.abs(above) < 0.3)), 1) if len(above) else 0.0,
        "no_surface_below_pct": round(100 * none / n, 2),
        "inside_geometry_pct": round(100 * inside / n, 1),
        "inside_static_geometry_pct": round(100 * inside_static / n, 1),
    }


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    import json

    print(json.dumps(check(argv[0], argv[1:]), indent=1))
    return 0
