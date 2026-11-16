---
title: Maps
nav_order: 3
---

# Maps into 3D levels

```text
heat3d-r6-maps map --all --game "<your game folder>" --out levels --oodle "<path to oo2core_9_win64.dll>"
```

builds the maps of your installation. To build a few:

```text
heat3d-r6-maps map Clubhouse Bank --game "<your game folder>" --out levels --oodle "..."
heat3d-r6-maps map --list --game "<your game folder>"   # the maps your installation has
```

What happens:

1. The map archives (all of them, even for one map: maps share their
   models), the mesh archives and the shared archives are unpacked into a cache
   on your machine
   (`levels/.unpacked`). This takes a few minutes and about 10 GB; an
   interrupted run continues where it stopped.
2. Every placed object of the map is put where the game puts it, in the same
   metres and the same orientation the replays use, so the players' tracks
   stand on the floors.
3. Per map, two files are written:

```text
levels/r6_Clubhouse.glb     the level
levels/r6_Clubhouse.json    what is in it: counts, the map's version, the breakable objects
```

`levels/map.log` keeps a line per map; `levels/MAPS.DONE` marks a finished
`--all` run. A map whose level already exists is skipped; `--force` builds it
again (after a game update).

## The parts

The viewer draws a level in two kinds of parts, and the tool names them so it
does not have to guess:

| Part | What it holds |
|---|---|
| `ground:r6 <Map> @<version>` | every surface facing up: floors, stairs, roofs, the ground outside |
| `structure:r6 <Map> @<version>` | walls, pillars, furniture, everything else |
| `ground:` / `structure:r6 <Map> @<version> breakable <id>` | one breakable object: a soft wall, a hatch, a barricade, a table... |
| `ground:r6 <Map> @<version> plate` | the wide ground plates that run under and through the buildings (in a sunken room one passes overhead: hide it there) |

`<version>` is the map's *world id*, the number the replays name the map by;
it changes when a map is reworked. `<id>` is the object's level-object id,
the same number a match gives a bullet mark's `surface`, so a mark and the
object it hit can be matched. The `.json` lists every breakable object with
its id, bounds and a rough `shape` (`wall`, `floor` or `object`).

Detailed props (trees, furniture, clutter: more than 1,500 triangles and less
than 15 m across) are simplified so the level stays light to draw; the
building and every breakable object keep their exact shape. `--full` keeps
everything exact (about twice the triangles).

## In the viewer

1. In **Background / level**, choose **3D model…** and pick
   `levels/r6_<Map>.glb`. The viewer keeps it in its level library, which is
   local: in the browser, on this computer. Nothing is uploaded.
2. From then on, when you load a match on that map, the viewer offers
   **Siege map: <Map>** and loads it by itself if no other level is loaded.
   If the library's level is of another version of the map than the match
   (the map was reworked since), the viewer says so.

## Checking a level against matches

```text
heat3d-r6-maps check levels/r6_Clubhouse.glb matches/r6_Clubhouse_*.3dheat
```

prints how far the players' feet are above the floor below them (0 when the
tracks stand on the floors) and how often a player stands inside something:

```json
{
 "samples": 20000,
 "median_above_floor_m": -0.01,
 "within_0_3m_pct": 96.0,
 "no_surface_below_pct": 0.0,
 "inside_geometry_pct": 17.0,
 "inside_static_geometry_pct": 2.0
}
```

(Example numbers.) "Inside" counts a surface between knee and head height
right above the feet: tables and shelves a player stands under, barricades
the level still shows whole that were broken in the match, and ground plates
passing over sunken rooms; "static" leaves the breakables and the plates out.

## Keep them to yourself

The levels hold the game's geometry, which belongs to Ubisoft. They are for
your personal analysis on your machine: do not share, publish or redistribute
them, and do not use them to train AI models.
