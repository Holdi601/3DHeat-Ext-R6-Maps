---
title: Terms and licence
nav_order: 8
---

# Terms and licence

This page says what this tool reads, what it does and does not do, and what
it writes.

## What the tool reads

The files of your own installation of Rainbow Six Siege, read-only, from the
folder you name. The 3DHeat viewer uses the levels to show your match replays
on the map, for your personal analysis. Nothing from the game is shipped with
this tool or its documentation: no game assets, no game code, no DLLs.

**Not a cheat.** The tool never runs with the game, never reads its memory,
never touches its anti-cheat or its network traffic, and changes nothing in
the game folder. It works on files, after the fact.

## What the tool does and does not do

| Does | Does not |
|---|---|
| read the game folder you name, read-only | start, change or patch the game |
| load an Oodle library whose path you give, where it is | include, link to, download, look for or copy Oodle |
| write levels on your machine | upload, publish or share anything |
| | read the game's memory, its anti-cheat or its network traffic |
| | read the archives' file tables: entries are found by walking the data |

## Your levels

The levels (`.glb`) and the unpacked cache are made of the game's geometry,
which belongs to Ubisoft. Keep them on your machine for your personal
analysis; do not share, publish, redistribute or sell them, and do not use
them to train AI models. The 3DHeat viewer keeps a loaded level in its local
library, in the browser on this computer; it has no way to upload or share
one.

## Notice and contact

Each game reader is its own small project with its own licence file,
releases and issue tracker, so it can be installed, updated, maintained - or
withdrawn on a rights holder's request - on its own, without affecting the
viewer or the other tools.

Not affiliated with or endorsed by Ubisoft. Rainbow Six Siege and all other
trademarks belong to their owners. The tool is meant for non-commercial use.
Rights holders: open an issue or get in touch through the GitHub profile; we
respond within 48 hours and remove on request.

## This tool's licence

The code is MIT licensed (see `LICENSE`). What it reads and what it ships is
listed in
[`LICENSES.md`](https://github.com/Holdi601/3DHeat-Ext-R6-Maps/blob/main/LICENSES.md).
