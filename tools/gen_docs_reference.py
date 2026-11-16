"""Write docs/cli-reference.md from the code itself, so the reference cannot drift.

The options come from the program's own `--help`; the level's parts and
classes and `.json` keys from a level built from the synthetic install the
tests make.

    python tools/gen_docs_reference.py          # rewrite the page
    python tools/gen_docs_reference.py --check  # exit 1 when the page is stale
"""
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "cli-reference.md"
COMMAND = "heat3d-r6-maps"


def run(args):
    env = dict(os.environ, HEAT3D_NO_UPDATE="1", COLUMNS="88", PYTHONIOENCODING="utf-8",
               PYTHONPATH=str(ROOT) + os.pathsep + os.environ.get("PYTHONPATH", ""))
    r = subprocess.run([sys.executable, "-m", "heat3d_ext_r6maps"] + args, capture_output=True, text=True,
                       env=env, encoding="utf-8", cwd=ROOT)
    return (r.stdout or r.stderr).rstrip()


VERBS_HELP = {"map": ["map", "--help"], "unpack": ["unpack", "--help"], "probe": ["probe"]}


def outputs():
    sys.path[:0] = [str(ROOT), str(ROOT / "tests")]
    os.environ["HEAT3D_NO_UPDATE"] = "1"
    import test_level
    from heat3d_ext_r6maps import level, mapexport

    with tempfile.TemporaryDirectory() as tmp:
        root = test_level._world(Path(tmp))
        lib = level.Library(root)
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            mapexport.build(lib, root / "datapc64_pvp04_clubhouse_mod", "Clubhouse", Path(tmp) / "levels", "pvp04_clubhouse")
        doc = json.loads((Path(tmp) / "levels" / "r6_Clubhouse.json").read_text(encoding="utf-8"))
        raw = (Path(tmp) / "levels" / "r6_Clubhouse.glb").read_bytes()
        n = int.from_bytes(raw[12:16], "little")
        nodes = sorted({x.get("name", "") for x in json.loads(raw[20:20 + n])["nodes"]})
    return ["### `r6_<Map>.glb` parts", "", "Part names of the synthetic test level (`<Map>` Clubhouse, made-up ids):", ""] + \
        [f"- `{x}`" for x in nodes] + ["", "### `r6_<Map>.json`", "",
        "Top-level keys: " + ", ".join(f"`{k}`" for k in doc) + ".", "",
        "Each breakable: " + ", ".join(f"`{k}`" for k in doc["breakables"][0]) + ".", ""]


def build():
    out = ["---", "title: Command reference", "nav_order: 90", "---", "", "# Command reference", "",
           "Generated from the code by `tools/gen_docs_reference.py`: do not edit by hand.",
           "The other pages explain each command step by step.", "",
           f"## `{COMMAND}`", "", "```text", run(["--help"]), "```", ""]
    for v, args in VERBS_HELP.items():
        out += [f"## `{v}`", "", "```text", run(args), "```", ""]
    out += ["## `check`", "", "```text", run(["check"]), "```", "", "## Output", ""]
    return "\n".join(out + outputs())


if __name__ == "__main__":
    text = build()
    if "--check" in sys.argv:
        sys.exit(0 if OUT.exists() and OUT.read_text(encoding="utf-8") == text else 1)
    OUT.write_text(text, encoding="utf-8", newline="\n")
    print("wrote", OUT.relative_to(ROOT))
