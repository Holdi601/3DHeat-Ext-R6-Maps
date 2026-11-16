"""
heat3d-r6-maps: reads your own Rainbow Six Siege installation, for
interoperability and personal analysis, and builds its maps as 3D levels for
the 3DHeat viewer.

    heat3d-r6-maps map --all --game <your game folder> --out <folder> --oodle <path to oo2core_9_win64.dll>
    heat3d-r6-maps map Clubhouse Bank --game <folder> --out <folder> --oodle <dll>
    heat3d-r6-maps map --list --game <folder>
    heat3d-r6-maps check <level.glb> <match.3dheat>...      tracks against a level
    heat3d-r6-maps unpack --game <folder> --out <folder>    the archives as plain files (development)
    heat3d-r6-maps probe walk|entry|types|index|refs ...    looking inside the archives (development)

Each command has its own --help. Matches (.3dheat) come from the separate
replay reader, heat3d-r6-replay (github.com/Holdi601/3DHeat-Ext-R6).

Not affiliated with or endorsed by Ubisoft. The levels stay on your machine
for your personal analysis: do not share or redistribute them.
"""

from __future__ import annotations

import sys

from . import __version__

VERBS = ("map", "check", "unpack", "probe")


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    try:
        from . import update

        update.startup("heat3d_ext_r6maps")
    except Exception:  # an update check never stops a build
        pass
    if argv[:1] == ["--version"]:
        print(__version__)
        return 0
    if not argv or argv[0] not in VERBS:
        print(__doc__)
        return 0 if not argv or argv[0] in ("-h", "--help") else 2
    verb, rest = argv[0], argv[1:]
    if verb == "map":
        from . import mapexport

        return mapexport.main(rest)
    if verb == "check":
        from . import alignment

        return alignment.main(rest)
    if verb == "unpack":
        from . import unpack

        return unpack.main(rest)
    from . import probe

    return probe.main(rest)


if __name__ == "__main__":
    sys.exit(main())
