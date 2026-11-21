# Changelog

## 0.2.0

- A standalone program for Windows (no Python needed), built by CI with a `SHA256SUMS` file. Without
  arguments it opens a window: the game folder you choose (nothing is searched for), what is missing (the
  folder, the Oodle library from that installation, disk space), the maps as new / changed by a game update /
  built by an older version / up to date, and building the picked ones one at a time into the 3DHeat levels
  folder (`<levels>/r6siege`).
- Each built map is recorded in `<levels>/r6siege/.heat3d-extract.json` (extractor version, size and SHA-256 of
  its archives), so maps that are new after a game update are found and only those built: `status --json`,
  `extract --new` / `--changed` / `--outdated` / `<map>...`, `--progress-json`.
- Updates ask first (update now / later / skip this version) unless automatic updates were chosen
  (`--auto-update`, the window's checkbox, or `HEAT3D_AUTO_UPDATE=1`).
- The version is written in the package (`__version__`), so the built program knows it too.
- Docs: no example install paths; you give your own folder.

## 0.1.0

- `heat3d-r6-maps`: reads your own installation of Rainbow Six Siege, for interoperability and personal analysis, and builds its maps as 3D levels for the 3DHeat viewer (formerly part of the R6 replay reader, 3DHeat-Ext-R6).
- `map`: the maps of the installation you name (`--game`) as 3D levels (`r6_<Map>.glb` + `.json`) in the replays' frame: floors, stairs and walls exact, each breakable object its own part named by the level-object id that marks' `surface` uses, the wide untextured ground plates their own part, detailed props simplified (`--full` keeps them). The map's world id names its version. Oodle comes from a library whose path you pass (`--oodle`, `HEAT3D_OODLE`); none is included or looked for.
- `check`: how far the players' feet are from the floors of a level, and how often they stand inside something.
- `unpack` and `probe`: the archives' resources as plain files on your machine, and a look inside them, for development.
- Notice: not affiliated with Ubisoft; levels stay on your machine and are not to be shared; non-commercial; no AI training; rights-holder contact.
- The updater lives in this tool's package (`heat3d_ext_r6maps.update`), checking Holdi601/3DHeat-Ext-R6-Maps.
- Docs: a documentation site (`docs/`: before you start, maps, terms, command reference), `LICENSES.md`.
- Installs with one pip line from the release zip, no Git needed; a pip install knows its version and updates itself with pip when a newer release is out.
- The version comes from the package's metadata when there is no VERSION file (a pip install).
- README: a quick start for new users.
