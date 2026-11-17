"""Rainbow Six Siege maps from your own install into 3D levels for the 3DHeat viewer."""

from pathlib import Path

def _version() -> str:
    file = Path(__file__).resolve().parent.parent / "VERSION"
    if file.exists():
        return file.read_text(encoding="utf-8").strip()
    try:  # a pip install has no VERSION file; its metadata has the version
        from importlib.metadata import version

        return version("heat3d-ext-r6maps")
    except Exception:
        return "0"


__version__ = _version()
