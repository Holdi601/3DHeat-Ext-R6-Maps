"""
The game folder: the one you name.

Nothing is searched for. You pass your own installation's folder (`--game`, or
`HEAT3D_R6_GAME` once); the tool only checks that it holds the game's `.forge`
archives, and reads them read-only.
"""

from __future__ import annotations

import os
from pathlib import Path


def game_folder(given: str | os.PathLike[str] | None = None) -> Path | None:
    """The folder given (or in `HEAT3D_R6_GAME`) when it holds `.forge` archives, else None."""
    chosen = given or os.environ.get("HEAT3D_R6_GAME")
    if not chosen:
        return None
    p = Path(chosen)
    try:
        return p if p.is_dir() and any(p.glob("*.forge")) else None
    except OSError:
        return None
