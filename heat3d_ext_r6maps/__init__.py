"""Rainbow Six Siege maps from your own install into 3D levels for the 3DHeat viewer."""

from pathlib import Path

__version__ = (Path(__file__).resolve().parent.parent / "VERSION").read_text(encoding="utf-8").strip() \
    if (Path(__file__).resolve().parent.parent / "VERSION").exists() else "0.1.0"
