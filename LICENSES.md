# Licences and what this tool touches

The code is MIT licensed (see `LICENSE`). It ships code only.

## What it reads

**Your own installation's archives** (`.forge`), read-only, from the folder
you name (`--game`), for interoperability and personal analysis. Nothing in
the game folder is changed, the game is never started, and its anti-cheat,
memory and network traffic are never touched. The file table at the start of
an archive is not read; entries are found by walking the archives' data.

You need your own installed copy of the game. The tool does not download game
data and does not work without an installation.

## Oodle

The archives are compressed with Oodle (RAD Game Tools / Epic Games), which
has no redistributable build. This tool **does not include, bundle, download
or link to** an Oodle library, and does not look for one: you pass the path of
an `oo2core_9_win64.dll` from software you have installed (`--oodle` or
`HEAT3D_OODLE`). It is used where it is, for decompression on your machine
only, and is never copied.

## What it writes

Levels (`.glb`, `.json`) and unpacked resources, on your machine, for your
personal analysis. They hold the game's geometry, which belongs to Ubisoft:
do not share, publish or redistribute them, and do not use them to train AI
models. The repository ignores them (`.gitignore`); no Ubisoft asset, image,
logo or content taken from the game is part of this repository, its documentation or
its releases (the documentation's pictures are drawn, not taken from the
game).

## Facts, not assets

The table of map names in `mapexport.py` names the game's map archives; world
ids are read from your installation's archives. Neither is a copy of game
data.

## How the format was worked out

From the files themselves. No other tool's code is used.

## Non-commercial

The tool is meant for non-commercial, personal analysis.

## Notice and contact

Each game reader is its own small project with its own licence file,
releases and issue tracker, so it can be installed, updated, maintained - or
withdrawn on a rights holder's request - on its own, without affecting the
viewer or the other tools.

Not affiliated with or endorsed by Ubisoft. Rainbow Six Siege and all other
trademarks belong to their owners. Rights holders: open an issue or get in
touch through the GitHub profile; we respond within 48 hours and remove on
request.
