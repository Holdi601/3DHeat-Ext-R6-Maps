# heat3d-r6-maps

Reads **your own installation** of Rainbow Six Siege, for interoperability and
personal analysis, and builds its maps as 3D levels for the
[3DHeat](https://github.com/Holdi601/3DHeat) viewer: floors, stairs and walls
in the frame the match replays use, so the players' tracks stand on the
floors, with each breakable object (soft walls, hatches, barricades,
furniture) as its own part.

The matches come from the separate replay reader,
[3DHeat-Ext-R6](https://github.com/Holdi601/3DHeat-Ext-R6) (`heat3d-r6-replay`).

Files only: the tool reads the folder you name, read-only. It never starts or
touches the game, its memory or its anti-cheat.

Documentation: `docs/` (published as the project's site): before you start,
maps, terms, command reference.

## Notice

- Each game reader is its own small project with its own licence file,
  releases and issue tracker, so it can be installed, updated, maintained - or
  withdrawn on a rights holder's request - on its own, without affecting the
  viewer or the other tools.
- Nothing from the game is shipped: no game assets, no game code, no DLLs.
- Not affiliated with or endorsed by Ubisoft. Rainbow Six Siege and all other
  trademarks belong to their owners.
- The levels and the unpacked cache stay on your machine, for your personal
  analysis. Do not share or redistribute them.
- Meant for non-commercial use. Do not use the tool's output to train AI
  models.
- Rights holders: open an issue or get in touch through the GitHub profile; we
  respond within 48 hours and remove on request.

## Use

```
pip install -e .
heat3d-r6-maps map --all --game <your game folder> --out levels --oodle <path to oo2core_9_win64.dll>
heat3d-r6-maps map Clubhouse Bank --game <folder> --out levels --oodle <dll>
heat3d-r6-maps map --list --game <folder>
heat3d-r6-maps check levels/r6_Clubhouse.glb matches/r6_Clubhouse_*.3dheat     # needs pip install -e .[check]
```

`--game` is your installation's folder (the one holding the game's `.forge`
files); `HEAT3D_R6_GAME` can hold it instead. Nothing is searched for.
`map` unpacks the map archives (all of them, as maps share models), the mesh
banks and the shared archives into a cache on your machine
(`<out>/.unpacked`, about 10 GB, resumable) and writes per map
`r6_<Map>.glb` and `r6_<Map>.json`. `<out>/map.log` keeps a line per map;
`<out>/MAPS.DONE` marks a finished `--all` run; existing levels are skipped
unless `--force`.

**Load it in the viewer:** Background / level -> 3D model... -> pick
`r6_<Map>.glb` once. The viewer keeps it in its local level library (in the
browser, on this computer) and from then on offers it for matches on that map
version.

## The level

- Every placed mesh in the replays' own frame (metres, Z up; the `.glb` holds
  `(x, z, y)`, the way the viewer draws R6 tables).
- Parts: `ground:r6 <Map> @<world id>` (surfaces facing up),
  `structure:r6 <Map> @<world id>` (the rest), each breakable object
  `... breakable <level-object id>` (the id a converted match gives a bullet
  mark's `surface`), and the wide untextured ground plates `... plate`.
- The world id is the replays' `worldid`; it changes when a map is reworked.
- Detailed props are simplified (`--full` keeps them exact); the building and
  the breakables keep their exact geometry.
- The `.json`: the map, its world id and archive, counts, and every breakable
  with its id, bounds and a rough shape (`wall`, `floor`, `object`).

## Oodle

The game's archives are Oodle-compressed. This tool includes no Oodle library,
links to none and looks for none: pass the path of an `oo2core_9_win64.dll`
from software you have installed (`--oodle`, or `HEAT3D_OODLE`). It is used
where it is and never copied. See `LICENSES.md`.

## How the archives are read

`forge.py`, `level.py`: the file table at the start of an archive is not read.
Every entry starts on a 4 KB boundary with a block (`37 aa fb 57 99 fa 15 10`),
so entries are found by walking the data:

```
block    magic, version:u16, compression:u8, flags:u32, chunks:u32,
         (uncompressed:u32, compressed:u32) per chunk,
         then per chunk checksum:u32 and its bytes (stored when both sizes match)
entry    a header block: count:u32, (id:u64, size:u32) per resource;
         then data blocks holding the resources back to back
mesh     int16 x, y, z, s per vertex (position = xyz * s / 32768), u16 triangles
entity   kind, id, kind, a 4x4 world matrix, then components naming the meshes
```

For example, an entry with resources `0x11` (14 bytes) and `0x22` (6 bytes)
is a header block of 28 bytes and a data block of 20.

`unpack` writes the archives' resources as plain files on your machine (for
development); `probe` looks inside them. `check` measures how far the players'
feet are from the floors of a level.

## Licence

The code is MIT licensed. The tool is meant for non-commercial, personal
analysis of your own installation; game files, levels and Oodle are not
included and never committed. See `LICENSES.md`.
