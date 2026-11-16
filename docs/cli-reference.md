---
title: Command reference
nav_order: 90
---

# Command reference

Generated from the code by `tools/gen_docs_reference.py`: do not edit by hand.
The other pages explain each command step by step.

## `heat3d-r6-maps`

```text

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
```

## `map`

```text
usage: heat3d-r6-maps map [-h] [--all] [--out OUT] [--oodle OODLE] [--game GAME]
                          [--cache CACHE] [--unpacked UNPACKED] [--force] [--list]
                          [--full]
                          [maps ...]

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

positional arguments:
  maps                 map names (Clubhouse, Bank, ...); none with --all

options:
  -h, --help           show this help message and exit
  --all                all maps of your installation
  --out OUT            where the levels go (on your machine)
  --oodle OODLE        path of an oo2core_9_win64.dll from software you have installed
                       (or set HEAT3D_OODLE)
  --game GAME          your Rainbow Six Siege installation's folder (or set
                       HEAT3D_R6_GAME)
  --cache CACHE        where the archives are unpacked (default: <out>/.unpacked)
  --unpacked UNPACKED  use archives unpacked earlier (`unpack`) instead of unpacking
  --force              rebuild levels that exist already
  --list               list the maps found and stop
  --full               keep detailed props exact too (heavier to draw)
```

## `unpack`

```text
usage: heat3d-r6-maps unpack [-h] --out OUT [--game GAME] [--maps] [--first]
                             [--estimate] [--oodle OODLE]
                             [files ...]

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

positional arguments:
  files          archives to unpack (default: the selection)

options:
  -h, --help     show this help message and exit
  --out OUT
  --game GAME    your Rainbow Six Siege installation's folder (or set HEAT3D_R6_GAME)
  --maps         the map archives and the banks they draw on
  --first        Clubhouse and the mesh banks only
  --estimate     only say how much would be written
  --oodle OODLE  path of an oo2core_9_win64.dll from software you have installed (or
                 set HEAT3D_OODLE)
```

## `probe`

```text

Looking inside the forge archives while their layout is worked out:

    probe walk <file.forge>                     the entries, found by their blocks
    probe entry <file.forge> <offset> [-o dir]  one entry's resources (decompressed); -o writes each to a file
    probe types <file.forge>...                 resource kinds (first u32 of each resource) and their sizes

Read-only on the archives; anything written goes where `-o` says.
```

## `check`

```text

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
```

## Output

### `r6_<Map>.glb` parts

Part names of the synthetic test level (`<Map>` Clubhouse, made-up ids):

- `ground:r6 Clubhouse @403726925825`
- `ground:r6 Clubhouse @403726925825 plate`
- `structure:r6 Clubhouse @403726925825 breakable 770`

### `r6_<Map>.json`

Top-level keys: `game`, `map`, `world_id`, `archive`, `converter`, `frame`, `parts`, `placements`, `skipped_far`, `skipped_broken`, `ground_triangles`, `structure_triangles`, `breakable_parts`, `simplified_meshes`, `triangles_before_simplifying`, `plates`, `unique_meshes`, `detail`, `breakables`, `bytes`, `seconds`.

Each breakable: `entity`, `group`, `pieces`, `min`, `max`, `shape`.
