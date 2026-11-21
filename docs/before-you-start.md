---
title: Before you start
nav_order: 2
---

# Before you start

## The standalone program (no Python needed)

Each [release](https://github.com/Holdi601/3DHeat-Ext-R6-Maps/releases/latest)
has a ready-to-run program for Windows (`heat3d-r6-maps-<version>-windows-x64.zip`)
with a `SHA256SUMS` file to check the download. Unpack it anywhere and start
`heat3d-r6-maps.exe`.

Started without arguments it opens a window that:

- asks for your installation's folder (*Choose folder...*, the one holding the
  game's `.forge` files); nothing is searched for;
- says what is missing: the game folder, the Oodle library (it is taken from
  the folder you chose when it is there, or from `HEAT3D_OODLE`; it is used
  where it is and never copied), free disk space;
- lists the installation's maps as new, changed by a game update, built by an
  older version, or up to date, and builds the ones you pick, one at a time,
  into the 3DHeat levels folder (`HEAT3D_LEVELS`, by default
  `%LOCALAPPDATA%\3DHeat\levels`; the maps go to its `r6siege` folder), where
  the viewer finds them;
- checks for updates and asks before installing one, unless you tick
  *Update automatically*.

Each built map is recorded in `<levels>/r6siege/.heat3d-extract.json`, so after
a game update only the new and changed maps need building. The same program
runs every command below: `heat3d-r6-maps map --list --game "<your game folder>"`.
For scripts: `heat3d-r6-maps status --json` reports the maps' state,
`heat3d-r6-maps extract --new` builds only the new ones and
`heat3d-r6-maps --check --json` says what is found and missing.
The 3DHeat app's Extractors panel installs, updates and starts it for you.

## 1. Python

Install Python 3.10 or newer from [python.org](https://www.python.org/downloads/)
(tick "Add python.exe to PATH"). Then, in the folder of this tool:

```text
pip install -e .
```

That installs the `heat3d-r6-maps` command. Check it with
`heat3d-r6-maps --version`.

## 2. Your installation

The levels are built from **your own installation** of the game. Name its
folder with `--game "<your game folder>"` (the folder that holds the game's
`.forge` files), or set `HEAT3D_R6_GAME` to it once. The tool does not search
for it; it only checks that the folder holds `.forge` files.

The game does not have to run, and should not: the tool only reads its files.

## 3. An Oodle library

The game's archives are compressed with **Oodle**, a commercial library by
RAD Game Tools (Epic Games). It may not be passed around, so **this tool does
not include it, link to it or download it, and does not search for it.**
The standalone program takes it from the game folder you chose when it is
there; otherwise:

Pass the path of an `oo2core_9_win64.dll` from software you have installed:

```text
heat3d-r6-maps map --all --game "<your game folder>" --out levels --oodle "<path to oo2core_9_win64.dll>"
```

or set `HEAT3D_OODLE` to it once. The file is loaded where it is, used on your
machine only, and never copied. It must be a 64-bit (x64) build.

## 4. Where the files go

| What | Where | Size |
|---|---|---|
| levels | the folder you give with `--out` | 30-70 MB per map |
| unpacked archives (a cache) | `<out>/.unpacked`, or `--cache <folder>` | about 10 GB |

The cache lets an interrupted run continue where it stopped. Delete it when
the levels are built; a later run (after a game update) unpacks again.

**Keep the levels and the cache to yourself.** They hold the game's own
geometry, which belongs to Ubisoft: use them on your machine for your
personal analysis; do not share, publish or redistribute them, and do not use
them to train AI models.
