---
title: Terms and licence
nav_order: 8
---

# Terms and licence

This page says what the game's licence says, what this tool does, and what
that means for you. It is not legal advice.

## Ubisoft's licence

The game installs its End-User Licence Agreement under
`Support\eula\` (read on 2026-11-15 from `EULA-v1.0-UK.htm`). Clause 1.2:

> You shall not, directly or indirectly (i) sell, rent out, lease, license,
> distribute, market, exploit the Product or any of its parts commercially,
> (ii) reverse engineer, decompile, disassemble, adapt, reproduce, or create
> derivate works of this Product [...] in whole or in part; (iii) create, use
> and/or distribute "auto", "trainer", "script" or "macro" computer programs
> or other "cheat" or "hack" programs or software applications for this
> Product [...]

This tool reads your own installation, for interoperability (the 3DHeat
viewer shows match replays on the map) and personal analysis, and builds
level files on your machine. That is close to what clause 1.2 (ii) restricts.
Some laws allow parts of such work regardless of a licence (in the EU, for
example, for interoperability); whether that covers your use depends on where
you live. **Decide for yourself whether to use this tool.**

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

Not affiliated with or endorsed by Ubisoft. Rainbow Six Siege and all other
trademarks belong to their owners. The tool is meant for non-commercial use.
Rights holders: open an issue or get in touch through the GitHub profile; we
respond within 48 hours and remove on request.

## This tool's licence

The code is MIT licensed (see `LICENSE`). What it reads and what it ships is
listed in
[`LICENSES.md`](https://github.com/Holdi601/3DHeat-Ext-R6-Maps/blob/main/LICENSES.md).
