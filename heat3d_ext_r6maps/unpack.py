"""
heat3d-r6-maps unpack: your installation's archive resources as plain files on
your machine, for development and personal analysis.

    heat3d-r6-maps unpack --game <your game folder> --out <folder> --oodle <dll> [--maps | --first] [file.forge...]
    heat3d-r6-maps unpack --game <folder> --out <folder> --estimate [...]

Decompressing needs Oodle (see `oodle.py`); everything after this step reads
the unpacked files and needs no library. Per archive a folder
`<out>/<archive>/` holds one file per resource, `<entry>_<id>.bin` (entry =
the archive offset of its header block, hex), and `index.json` lists them
with their kind and size once the archive is complete. Interrupted runs
resume: an archive with a complete index is skipped, and inside an
unfinished one the entries already written (logged in `entries.log`) are.
`<out>/unpack.log` keeps the progress; `<out>/UNPACK.DONE` marks a finished
run of the whole selection.

Selections: `--first` is Clubhouse and the mesh banks; `--maps` is the map
archives (`pvp*`), the mesh and collision-shape banks and the shared archives
(`datapc64`, `ondemand*`), Clubhouse first. Textures, sound, lighting data
and cosmetics are left out. The unpacked files stay on your machine.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path

from . import forge

#: Kept free on the output drive beyond the estimate.
MARGIN = 5 << 30


def _is_map(name: str) -> bool:
    return bool(re.match(r"datapc64_pvp\d+_.*\.forge$", name)) and "_bnk_" not in name


def _is_mesh_bank(name: str) -> bool:
    return bool(re.search(r"_bnk_(\d+_)?mesh\.forge$", name)) and "mtx" not in name


def _is_shape_bank(name: str) -> bool:
    return bool(re.search(r"_bnk_(\d+_)?meshshape\.forge$", name)) and "mtx" not in name


def _is_shared(name: str) -> bool:
    return name == "datapc64.forge" or bool(re.match(r"datapc64_ondemand[^.]*\.forge$", name))


def select(game: Path, first: bool = False) -> list[Path]:
    """The archives to unpack, in the order they are wanted: Clubhouse, its banks, then the rest."""
    names = sorted(p.name for p in game.glob("*.forge"))
    club = [n for n in names if _is_map(n) and "clubhouse" in n]
    meshes = [n for n in names if _is_mesh_bank(n)]
    if first:
        chosen = club + meshes
    else:
        chosen = club + meshes + [n for n in names if _is_shared(n)] + \
            [n for n in names if _is_map(n) and n not in club] + [n for n in names if _is_shape_bank(n)]
    return [game / n for n in chosen]


def estimate(path: Path) -> int:
    """Bytes the archive's entries unpack to, from the block tables alone (no decompression)."""
    with forge.Forge(path) as f:
        total = 0
        for e in f.entries():
            total += sum(b.size for b in e.blocks)
        return total


def _done(folder: Path) -> bool:
    try:
        return json.loads((folder / "index.json").read_text(encoding="utf-8")).get("complete") is True
    except (OSError, ValueError):
        return False


def _log(out: Path, text: str) -> None:
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {text}"
    print(line, flush=True)
    with open(out / "unpack.log", "a", encoding="utf-8") as w:
        w.write(line + "\n")


def unpack_one(path: Path, out: Path, decompress: forge.Decompress) -> dict:
    """One archive into `<out>/<archive>/`; returns its index."""
    folder = out / path.stem
    folder.mkdir(parents=True, exist_ok=True)
    done_log = folder / "entries.log"
    seen: dict[int, list] = {}
    if done_log.exists():
        for line in done_log.read_text(encoding="utf-8").splitlines():
            try:
                rec = json.loads(line)
                seen[rec["entry"]] = rec["resources"]
            except (ValueError, KeyError):
                continue  # a line cut short by an interruption: that entry is done again
    with forge.Forge(path) as f, open(done_log, "a", encoding="utf-8") as log:
        for e in f.entries(decompress):
            if e.start in seen:
                continue
            records = []
            for rid, body in forge.resources(f.data, e, decompress):
                name = f"{e.start:08x}_{rid:016x}.bin"
                (folder / name).write_bytes(body)
                kind = forge.head(body)[0]
                records.append({"id": f"{rid:x}", "kind": f"{kind:08x}", "size": len(body), "file": name})
            log.write(json.dumps({"entry": e.start, "resources": records}) + "\n")
            log.flush()
            seen[e.start] = records
    index = {
        "archive": path.name, "version": forge.version(path), "complete": True,
        "entries": [{"entry": f"{k:x}", "resources": v} for k, v in sorted(seen.items())],
    }
    (folder / "index.json").write_text(json.dumps(index), encoding="utf-8")
    return index


def run(paths: list[Path], out: Path, decompress: forge.Decompress) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    totals = {"archives": 0, "skipped": 0, "resources": 0, "bytes": 0}
    for p in paths:
        folder = out / p.stem
        if _done(folder):
            totals["skipped"] += 1
            continue
        t0 = time.time()
        _log(out, f"start {p.name} ({p.stat().st_size / 1e6:.0f} MB packed)")
        index = unpack_one(p, out, decompress)
        res = [r for e in index["entries"] for r in e["resources"]]
        size = sum(r["size"] for r in res)
        totals["archives"] += 1
        totals["resources"] += len(res)
        totals["bytes"] += size
        _log(out, f"done  {p.name}: {len(index['entries'])} entries, {len(res)} resources, "
                  f"{size / 1e6:.0f} MB in {time.time() - t0:.0f} s")
    return totals


def _below_normal() -> None:
    """Run gently beside the rest of the machine (Windows: below-normal priority)."""
    if os.name == "nt":
        try:
            import ctypes

            ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
        except (AttributeError, OSError):
            pass


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="heat3d-r6-maps unpack", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="*", help="archives to unpack (default: the selection)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--game", help="your Rainbow Six Siege installation's folder (or set HEAT3D_R6_GAME)")
    ap.add_argument("--maps", action="store_true", help="the map archives and the banks they draw on")
    ap.add_argument("--first", action="store_true", help="Clubhouse and the mesh banks only")
    ap.add_argument("--estimate", action="store_true", help="only say how much would be written")
    ap.add_argument("--oodle", help="path of an oo2core_9_win64.dll from software you have installed (or set HEAT3D_OODLE)")
    args = ap.parse_args(argv)
    out = Path(args.out)
    if args.files:
        paths = [Path(f) for f in args.files]
    else:
        from .install import game_folder

        game = game_folder(args.game)
        if game is None:
            print("Name your Rainbow Six Siege installation's folder with --game <folder> (or HEAT3D_R6_GAME).",
                  file=sys.stderr)
            return 1
        paths = select(game, first=args.first and not args.maps)
    if not paths:
        print(f"no archives found in {args.game}", file=sys.stderr)
        return 1
    todo = [p for p in paths if not _done(out / p.stem)]
    need = sum(estimate(p) for p in todo)
    out.mkdir(parents=True, exist_ok=True)
    free = shutil.disk_usage(out).free
    print(f"{len(paths)} archives ({len(paths) - len(todo)} already unpacked), "
          f"{sum(p.stat().st_size for p in todo) / 1e9:.1f} GB packed -> about {need / 1e9:.1f} GB unpacked; "
          f"{free / 1e9:.0f} GB free on the output drive", flush=True)
    if args.estimate:
        return 0
    if need + MARGIN > free:
        print(f"not enough room: need {need / 1e9:.1f} GB plus {MARGIN >> 30} GB spare", file=sys.stderr)
        return 1
    from . import oodle

    try:
        oodle.load(args.oodle)
    except oodle.OodleUnavailable as e:
        print(e, file=sys.stderr)
        return 1
    _below_normal()
    _log(out, f"oodle {oodle.path()}; {len(todo)} archives to unpack")
    t0 = time.time()
    totals = run(paths, out, oodle.decompress)
    _log(out, f"finished: {totals['archives']} archives unpacked, {totals['skipped']} already done, "
              f"{totals['resources']} resources, {totals['bytes'] / 1e9:.2f} GB in {(time.time() - t0) / 60:.1f} min")
    marker = "UNPACK.DONE" if args.maps or args.files else "UNPACK-FIRST.DONE"
    (out / marker).write_text(json.dumps(totals), encoding="utf-8")
    return 0
