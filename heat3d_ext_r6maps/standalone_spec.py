"""
The standalone app's description of this tool (app/spec.py): the game folder
you name (nothing is searched for), the Oodle library from that same
installation, and the installation's maps (new ones after a game update are
found by app/manifest.py). `python -m heat3d_ext_r6maps.standalone_spec` runs
the app from a checkout; the release executable runs the same.
"""

from __future__ import annotations

import os
from pathlib import Path

from . import __version__
from .app.spec import Check, GameSpec, MapSource, Spec


def _find(given: str | None) -> Path | None:
    from .install import game_folder

    return game_folder(given)


def _maps(game: Path) -> list[MapSource]:
    from .mapexport import file_stem, map_of

    found: dict[str, tuple[str, list[Path]]] = {}
    for p in sorted(game.glob("datapc64_pvp*.forge")):
        m = map_of(p.name)
        if m:
            found.setdefault(m[1], (m[0], []))[1].append(p)
    return [MapSource(file_stem(name), name, files, note=key) for key, (name, files) in sorted(found.items())]


def _oodle(game: Path | None) -> Path | None:
    """HEAT3D_OODLE when set, else the Oodle library in the game folder you chose; never searched elsewhere."""
    given = os.environ.get("HEAT3D_OODLE", "").strip()
    if given:
        p = Path(given)
        p = p / "oo2core_9_win64.dll" if p.is_dir() else p
        return p if p.is_file() else None
    if game is None:
        return None
    return next(iter(sorted(game.glob("oo2core_*_win64.dll"), reverse=True)), None)


def _extract(game: Path, m: MapSource, out: Path, log) -> list[Path]:
    from . import mapexport

    lib = _oodle(game)
    if lib is None:
        raise RuntimeError("no Oodle library: set HEAT3D_OODLE to an oo2core_9_win64.dll from your own installation")
    code = mapexport.main([m.note, "--game", str(game), "--out", str(out), "--oodle", str(lib), "--force"])
    if code != 0:
        raise RuntimeError(f"heat3d-r6-maps map exited {code}")
    return [p for p in (out / f"{m.id}.glb", out / f"{m.id}.json") if p.is_file()]


def _checks(found: dict, levels: Path) -> list[Check]:
    lib = _oodle(found.get("r6siege"))
    return [Check(
        "oodle", "Oodle library (from your own installation)", lib is not None,
        str(lib) if lib else "not found in the game folder you chose; set HEAT3D_OODLE to an "
        "oo2core_9_win64.dll from software you have installed. It is used where it is, never copied.",
    )]


SPEC = Spec(
    id="heat3d-r6-maps",
    name="3DHeat R6 Maps",
    repo="Holdi601/3DHeat-Ext-R6-Maps",
    version=__version__,
    tools={"heat3d-r6-maps": "heat3d_ext_r6maps.cli:main"},
    default_tool="heat3d-r6-maps",
    description="Rainbow Six Siege maps from your own installation as 3D levels for the 3DHeat viewer",
    module="heat3d_ext_r6maps.standalone_spec",
    games=[GameSpec(
        key="r6siege", label="Rainbow Six Siege", find=_find, subdir="r6siege",
        maps=_maps, extract=_extract,
        existing_outputs=lambda out, m: [out / f"{m.id}.glb", out / f"{m.id}.json"],
        output_version="0.1.0",
        platforms=("windows-x64",),
    )],
    checks=_checks,
    min_free_gb=20.0,
    notice="Not affiliated with or endorsed by Ubisoft. The levels stay on your machine for your personal analysis.",
)

if __name__ == "__main__":
    from . import update
    from .app.entry import main

    raise SystemExit(main(SPEC, apply_source=update.apply))
