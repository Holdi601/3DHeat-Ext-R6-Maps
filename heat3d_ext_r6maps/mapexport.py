"""
heat3d-r6-maps map: your own Siege installation's maps as 3D levels for the
3DHeat viewer, for interoperability and personal analysis.

    heat3d-r6-maps map --all --game <your game folder> --out <folder> --oodle <path to oo2core_9_win64.dll>
    heat3d-r6-maps map Clubhouse Bank --game <folder> --out <folder> --oodle <dll>
    heat3d-r6-maps map --list --game <folder>

Reads the game folder you name (read-only; it must hold the game's `.forge`
archives), unpacks the map archives (all of them: maps share models), the
mesh banks and the shared archives into a cache folder on your machine
(`--cache`, resumable), and writes per map `r6_<Map>.glb` and `r6_<Map>.json`:

- every placed mesh of the map, in the replays' frame (metres; the .glb holds
  (x, z, y), the way the viewer draws the replay tables), so the players'
  tracks stand on the floors;
- parts named for the viewer: `ground:r6 <Map>` (surfaces facing up: floors,
  stairs, roofs, terrain) and `structure:r6 <Map>` (walls and everything
  else); breakable objects (barricades, wooden walls, furniture, glass...)
  as their own parts, `ground:` / `structure:r6 <Map> @<world> breakable <entity>`,
  with the entity's id in the node's `extras` and in the .json (the wide
  untextured ground plates that run under the buildings likewise end in
  ` plate`). The entity id is the level-object id the replays give a mark's
  `surface`, so a converted match and its level name the same object;
- the map's world id (the replays' `worldid`, which changes when a map is
  reworked) in every part name after `@`, so the viewer offers the level for
  replays of the same version of the map;
- the .json: the map, the archive it came from, counts, and the breakables
  with their ids and bounds.

Oodle: the archives are Oodle-compressed and this tool includes no Oodle
library. Pass the path of an `oo2core_9_win64.dll` from software you have
installed (`--oodle`, or `HEAT3D_OODLE`). It is used where it is, never copied.

The levels stay on your machine, for your own analysis: do not share or
redistribute them.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

import numpy as np

from . import __version__, glb, level

#: Archive name (`datapc64_<this>...forge`) -> the map's name as the replays give it (game.MAPS).
ARCHIVE_MAPS = {
    "pvp01_house": "House",
    "pvp02_oregon": "Oregon",
    "pvp04_clubhouse": "Clubhouse",
    "pvp05_plane": "Presidential Plane",
    "pvp06_yacht": "Yacht",
    "pvp07_consulate": "Consulate",
    "pvp08_bank": "Bank",
    "pvp09_kanal": "Kanal",
    "pvp10_chalet": "Chalet",
    "pvp11_university": "Bartlett University",
    "pvp12_russiancafe": "Kafe Dostoyevsky",
    "pvp13_border": "Border",
    "pvp14_favela": "Favela",
    "pvp15_temple": "Skyscraper",
    "pvp16_ibiza": "Coastline",
    "pvp17_themepark": "Theme Park",
    "pvp19_tower": "Tower",
    "pvp20_italy": "Villa",
    "pvp22_morocco": "Fortress",
    "pvp23_australia": "Outback",
    "pvp24_countryclub": "Emerald Plains",
    "pvp25_nighthaven": "Nighthaven Labs",
    "pvp26_viperstrike": "Lair",
    "pvp27_stadiumalpha": "Stadium Alpha",
    "pvp28_stadiumbeta": "Stadium Bravo",
    "pvp29_privatecasino": "Private Casino",
}
#: Props simplified (`detail="props"`): more triangles than this and smaller than PROP_SIZE across.
PROP_TRIANGLES = 1500
PROP_SIZE = 15.0
PROP_BUDGET = 600
#: Meshes this wide or wider drawn only with untextured materials are the ground plates (their own part).
VOLUME = 20.0
#: A face whose normal points at least this far up is ground (walkable).
GROUND = 0.7
#: Meshes reaching further than this from the map's middle are backdrop (sky, distant hills).
REACH = 600.0
#: The viewer's frame from the game's: (x, y, z) -> (x, z, y).
SWAP = np.array([[1, 0, 0, 0], [0, 0, 1, 0], [0, 1, 0, 0], [0, 0, 0, 1]], dtype=np.float64)


def map_of(archive: str) -> tuple[str, str] | None:
    """(map name, archive key) for a map archive's file or folder name, None for anything else."""
    m = re.match(r"(?:datapc64_)?(pvp\d+_[a-z]+)", Path(archive).stem)
    if not m or "_bnk_" in archive:
        return None
    key = m.group(1)
    return ARCHIVE_MAPS.get(key, key), key


def file_stem(name: str) -> str:
    return "r6_" + re.sub(r"[^A-Za-z0-9]+", "-", name).strip("-")


def _normals_up(pos: np.ndarray, tris: np.ndarray, up: np.ndarray) -> np.ndarray:
    a, b, c = pos[tris[:, 0]], pos[tris[:, 1]], pos[tris[:, 2]]
    n = np.cross(b - a, c - a)
    length = np.linalg.norm(n, axis=1)
    return np.divide(n @ up, length, out=np.zeros(len(n)), where=length > 0)


def _cluster(pos: np.ndarray, tris: np.ndarray, cell: float) -> tuple[np.ndarray, np.ndarray]:
    """Vertex clustering: every vertex in a cell of `cell` metres becomes their mean; collapsed triangles go."""
    q = np.floor((pos - pos.min(0)) / cell).astype(np.int64)
    _, inv = np.unique(q, axis=0, return_inverse=True)
    inv = inv.reshape(-1)
    count = np.bincount(inv)
    merged = np.zeros((len(count), 3))
    np.add.at(merged, inv, pos)
    merged /= count[:, None]
    t = inv[tris]
    t = t[(t[:, 0] != t[:, 1]) & (t[:, 1] != t[:, 2]) & (t[:, 0] != t[:, 2])]
    if len(t):
        _, first = np.unique(np.sort(t, axis=1), axis=0, return_index=True)
        t = t[np.sort(first)]
    used = np.unique(t)
    remap = np.full(len(merged), -1, np.int64)
    remap[used] = np.arange(len(used))
    return merged[used].astype(np.float32), remap[t].astype(np.int32)


def simplify(pos: np.ndarray, tris: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """
    A detailed prop with fewer triangles: at most an eighth (never under
    PROP_BUDGET), by clustering its vertices on a grid grown until it fits.
    Floors, walls and breakables never come here (see `build`).
    """
    budget = max(PROP_BUDGET, len(tris) // 8)
    diag = float(np.linalg.norm(pos.max(0) - pos.min(0)))
    cell = diag / 256
    best = pos, tris
    while cell < diag / 6:
        p, t = _cluster(pos, tris, cell)
        if len(t) == 0:
            break
        best = p, t
        if len(t) <= budget:
            break
        cell *= 1.4
    return best


def shape_of(extent) -> str:
    """What a breakable object's bounds look like: a wall, a floor or hatch, or an object (furniture, glass...)."""
    across, thin, high = max(extent[0], extent[1]), min(extent[0], extent[1]), extent[2]
    if across >= 1.5 and thin <= 0.5 and high >= 2.0:
        return "wall"
    if high <= 0.5 and thin >= 0.8:
        return "floor"
    return "object"


def world_of(folder: str | Path) -> int | None:
    """The map's world id: the id of its world resource, the same number the replays give as `worldid`."""
    doc = json.loads((Path(folder) / "index.json").read_text(encoding="utf-8"))
    for e in doc["entries"]:
        for r in e["resources"]:
            if int(r["kind"], 16) == level.WORLD:
                return int(r["id"], 16)
    return None


def build(lib: level.Library, folder: str | Path, name: str, out: str | Path, archive_key: str,
          detail: str = "props") -> dict:
    """
    One map's level: `<out>/r6_<Map>.glb` and `.json`; returns the summary.

    `detail`: "props" (default) simplifies detailed props - trees, furniture,
    clutter: meshes of more than PROP_TRIANGLES triangles and under PROP_SIZE
    across - so a map stays light to draw; the building (floors, walls, stairs:
    large meshes) and every breakable object keep their exact geometry.
    "full" keeps everything exact.
    """
    folder = Path(folder)
    out = Path(out)
    t0 = time.time()
    world = world_of(folder)
    placed = level.placements(lib, folder)
    meshes: dict[int, tuple[np.ndarray, np.ndarray] | None] = {}
    bounds: dict[int, tuple[np.ndarray, np.ndarray]] = {}
    for p in placed:
        if p.mesh in meshes:
            continue
        try:
            pos, tris = level.decode_mesh(lib.read(p.mesh))
            meshes[p.mesh] = (pos, tris) if len(tris) else None
            if len(tris):
                bounds[p.mesh] = (pos.min(0), pos.max(0))
        except (ValueError, KeyError, OSError):
            meshes[p.mesh] = None
    # The map's middle: where its pieces are placed.
    centre = np.median(np.array([p.matrix[3, :3] for p in placed]), axis=0) if placed else np.zeros(3)
    w = glb.Writer()
    variants: dict[tuple, tuple[int | None, int | None]] = {}
    counts = {"placements": 0, "skipped_far": 0, "skipped_broken": 0, "ground_triangles": 0, "structure_triangles": 0,
              "breakable_parts": 0, "simplified_meshes": 0, "triangles_before_simplifying": 0, "plates": 0}
    plain: dict[int, bool] = {}
    breakables: dict[int, dict] = {}
    for p in placed:
        m = meshes.get(p.mesh)
        if m is None:
            counts["skipped_broken"] += 1
            continue
        lo, hi = bounds[p.mesh]
        corners = np.array([[x, y, z, 1.0] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]) @ p.matrix
        wlo, whi = corners[:, :3].min(0), corners[:, :3].max(0)
        if (np.abs(wlo[:2] - centre[:2]) > REACH).any() or (np.abs(whi[:2] - centre[:2]) > REACH).any() \
                or (whi - wlo).max() > 2 * REACH:
            counts["skipped_far"] += 1
            continue
        # A wide mesh drawn only with untextured materials: the ground plates that run under and
        # through the buildings (in a sunken room the plate passes overhead). Kept, as its own part.
        plate = bool(not p.group and (whi[:2] - wlo[:2]).max() >= VOLUME and level.untextured(lib, p.via, plain))
        counts["plates"] += int(plate)
        rot = p.matrix[:3, :3]
        up = rot[:, 2] / max(np.linalg.norm(rot[:, 2]), 1e-12)
        diag = float(np.linalg.norm(hi - lo))
        light = detail == "props" and not p.group and len(m[1]) > PROP_TRIANGLES and diag < PROP_SIZE
        key = (p.mesh, tuple(np.round(up, 3)), light)
        if key not in variants:
            pos, tris = m
            if light:
                counts["simplified_meshes"] += 1
                pos, tris = simplify(pos, tris)
            ground = _normals_up(pos, tris, up) >= GROUND
            acc = w.positions(pos[:, [0, 2, 1]])
            flipped = tris[:, [0, 2, 1]]  # the swap mirrors, so the winding turns
            g = w.mesh(f"{p.mesh:x} ground", acc, flipped[ground]) if ground.any() else None
            s = w.mesh(f"{p.mesh:x} structure", acc, flipped[~ground]) if (~ground).any() else None
            variants[key] = (g, s)
            variants[key + ("n",)] = (int(ground.sum()), int((~ground).sum()))
        g, s = variants[key]
        ng, ns = variants[key + ("n",)]
        counts["triangles_before_simplifying"] += len(m[1])
        node_matrix = SWAP @ p.matrix.T @ SWAP
        label = f"r6 {name} @{world}" if world else f"r6 {name}"
        extras = None
        if plate:
            label += " plate"
            extras = {"r6": {"entity": str(p.entity), "plate": True}}
        if p.group:
            label += f" breakable {p.entity}"
            extras = {"r6": {"entity": str(p.entity), "group": f"{p.via:x}", "mesh": f"{p.mesh:x}"}}
            b = breakables.setdefault(p.entity, {"entity": str(p.entity), "group": f"{p.via:x}", "pieces": 0,
                                                 "min": wlo.tolist(), "max": whi.tolist()})
            b["pieces"] += 1
            b["min"] = np.minimum(b["min"], wlo).round(3).tolist()
            b["max"] = np.maximum(b["max"], whi).round(3).tolist()
        if g is not None:
            w.node(f"ground:{label}", g, node_matrix, extras)
            counts["ground_triangles"] += ng
        if s is not None:
            w.node(f"structure:{label}", s, node_matrix, extras)
            counts["structure_triangles"] += ns
        counts["placements"] += 1
    counts["breakable_parts"] = len(breakables)
    for b in breakables.values():
        b["shape"] = shape_of(np.subtract(b["max"], b["min"]))
    out.mkdir(parents=True, exist_ok=True)
    stem = file_stem(name)
    info = {
        "game": "r6siege", "map": name, "world_id": world, "archive": archive_key, "converter": {"name": "heat3d-r6-maps", "version": __version__},
        "frame": "the replays' frame: metres, z up; the .glb holds (x, z, y) as the viewer draws r6 tables",
        "parts": {"ground": f"ground:r6 {name} @{world}", "structure": f"structure:r6 {name} @{world}",
                  "breakable": f"ground:|structure:r6 {name} @{world} breakable <entity>"},
        **counts, "unique_meshes": len([k for k in variants if len(k) == 3]), "detail": detail,
        "breakables": sorted(breakables.values(), key=lambda b: int(b["entity"])),
    }
    size = w.write(out / f"{stem}.glb", extras={"heat3d": {"game": "r6siege", "map": name, "world_id": world,
                                                                     "archive": archive_key}})
    info["bytes"] = size
    info["seconds"] = round(time.time() - t0, 1)
    (out / f"{stem}.json").write_text(json.dumps(info, indent=1), encoding="utf-8")
    return info


def _map_folders(unpacked: Path) -> list[tuple[str, str, Path]]:
    out = []
    for d in sorted(unpacked.iterdir()):
        found = map_of(d.name)
        if found and (d / "index.json").exists():
            out.append((found[0], found[1], d))
    return out


def _log(out: Path, text: str) -> None:
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {text}"
    print(line, flush=True)
    with open(out / "map.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def _wanted(names: list[str], name: str, key: str) -> bool:
    if not names:
        return True
    flat = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())
    return any(flat(n) in (flat(name), flat(key)) or flat(n) == flat(key.split("_", 1)[-1]) for n in names)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="heat3d-r6-maps map", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("maps", nargs="*", help="map names (Clubhouse, Bank, ...); none with --all")
    ap.add_argument("--all", action="store_true", help="all maps of your installation")
    ap.add_argument("--out", help="where the levels go (on your machine)")
    ap.add_argument("--oodle", help="path of an oo2core_9_win64.dll from software you have installed (or set HEAT3D_OODLE)")
    ap.add_argument("--game", help="your Rainbow Six Siege installation's folder (or set HEAT3D_R6_GAME)")
    ap.add_argument("--cache", help="where the archives are unpacked (default: <out>/.unpacked)")
    ap.add_argument("--unpacked", help="use archives unpacked earlier (`unpack`) instead of unpacking")
    ap.add_argument("--force", action="store_true", help="rebuild levels that exist already")
    ap.add_argument("--list", action="store_true", help="list the maps found and stop")
    ap.add_argument("--full", action="store_true", help="keep detailed props exact too (heavier to draw)")
    args = ap.parse_args(argv)

    if args.unpacked:
        unpacked = Path(args.unpacked)
    else:
        from . import install, oodle, unpack

        game = install.game_folder(args.game)
        if game is None:
            print("Name your Rainbow Six Siege installation's folder with --game <folder> (or HEAT3D_R6_GAME):\n"
                  "the folder that holds the game's .forge files.", file=sys.stderr)
            return 1
        archives = [p for p in sorted(game.glob("datapc64_pvp*.forge")) if map_of(p.name)]
        if args.list:
            for p in archives:
                print(f"{map_of(p.name)[0]:<22} {p.name}")
            return 0
        chosen = [p for p in archives if _wanted(args.maps, *map_of(p.name))] if (args.all or args.maps) else []
        if not chosen:
            print("name the maps to build, or --all (see --list)", file=sys.stderr)
            return 2
        if not args.out:
            print("--out <folder> is needed", file=sys.stderr)
            return 2
        unpacked = Path(args.cache) if args.cache else Path(args.out) / ".unpacked"
        # Every map archive, not only the chosen ones: maps share their models, and a map's
        # wrappers and breakables often live in another map's archive (Clubhouse alone places
        # under half of its meshes without them). Plus the mesh banks and the shared archives.
        banks = [p for p in sorted(game.glob("*.forge"))
                 if unpack._is_mesh_bank(p.name) or unpack._is_shared(p.name)]
        others = [p for p in archives if p not in chosen]
        try:
            oodle.load(args.oodle)
        except oodle.OodleUnavailable as e:
            print(e, file=sys.stderr)
            return 1
        unpack._below_normal()
        unpacked.mkdir(parents=True, exist_ok=True)
        print(f"unpacking {len(archives)} map archives and {len(banks)} shared archives to {unpacked} "
              "(resumes if interrupted)", flush=True)
        unpack.run(chosen + banks + others, unpacked, oodle.decompress)
    if args.list:
        for name, key, d in _map_folders(unpacked):
            print(f"{name:<22} {d.name}")
        return 0
    if not args.out:
        print("--out <folder> is needed", file=sys.stderr)
        return 2
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    todo = [(n, k, d) for n, k, d in _map_folders(unpacked) if args.all or _wanted(args.maps, n, k)]
    if not todo:
        print("no map archives to build (name them, or --all)", file=sys.stderr)
        return 2
    lib = level.Library(unpacked)
    _log(out, f"{len(todo)} maps; {len(lib.where):,} mesh resources known")
    built = failed = 0
    for name, key, d in todo:
        target = out / f"{file_stem(name)}.glb"
        if target.exists() and (out / f"{file_stem(name)}.json").exists() and not args.force:
            _log(out, f"have  {name}")
            continue
        try:
            info = build(lib, d, name, out, key, detail="full" if args.full else "props")
            built += 1
            _log(out, f"built {name}: {info['placements']:,} placements, {info['ground_triangles']:,} ground and "
                      f"{info['structure_triangles']:,} structure triangles, {info['breakable_parts']} breakables, "
                      f"{info['bytes'] / 1e6:.0f} MB in {info['seconds']} s")
        except Exception as e:  # one map failing must not stop the others
            failed += 1
            _log(out, f"FAILED {name}: {type(e).__name__}: {e}")
    _log(out, f"done: {built} built, {failed} failed")
    if args.all:
        (out / "MAPS.DONE").write_text(json.dumps({"built": built, "failed": failed}), encoding="utf-8")
    return 0 if not failed else 1
