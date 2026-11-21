"""The standalone spec on a synthetic installation (tiny fake files, no game data)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from heat3d_ext_r6maps import mapexport, standalone_spec
from heat3d_ext_r6maps.app import entry, update
from heat3d_ext_r6maps.app import spec as app_spec


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "appdata"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "appdata"))
    monkeypatch.setenv("HEAT3D_LEVELS", str(tmp_path / "levels"))
    monkeypatch.setenv("HEAT3D_NO_UPDATE", "1")
    monkeypatch.delenv("HEAT3D_OODLE", raising=False)
    monkeypatch.delenv("HEAT3D_R6_GAME", raising=False)
    update.AUTO_THIS_RUN = False


def install(tmp_path: Path) -> Path:
    game = tmp_path / "game"
    game.mkdir()
    for name in ("datapc64_pvp04_clubhouse.forge", "datapc64_pvp08_bank.forge",
                 "datapc64_pvp08_bank_bnk_0.forge", "datapc64_merged_bnk_mesh.forge"):
        (game / name).write_bytes(name.encode())
    (game / "oo2core_9_win64.dll").write_bytes(b"MZ")
    return game


def run(*argv, capsys):
    code = entry.main(standalone_spec.SPEC, list(argv))
    return code, capsys.readouterr().out


def test_find_and_maps(tmp_path):
    game = install(tmp_path)
    g = standalone_spec.SPEC.games[0]
    assert g.find(None) is None  # nothing is searched for
    assert g.find(str(tmp_path / "empty")) is None
    assert g.find(str(game)) == game
    maps = g.maps(game)
    assert [(m.id, m.title) for m in maps] == [("r6_Clubhouse", "Clubhouse"), ("r6_Bank", "Bank")]
    bank = next(m for m in maps if m.title == "Bank")
    assert [p.name for p in bank.sources] == ["datapc64_pvp08_bank.forge"]  # mesh banks are not a map


def test_install_that_gains_a_map(tmp_path, monkeypatch, capsys):
    game = install(tmp_path)
    calls = []

    def fake_map(argv):
        key, out = argv[0], Path(argv[argv.index("--out") + 1])
        assert argv[argv.index("--oodle") + 1] == str(game / "oo2core_9_win64.dll")
        name = mapexport.ARCHIVE_MAPS[key]
        out.mkdir(parents=True, exist_ok=True)
        for ext in (".glb", ".json"):
            (out / (mapexport.file_stem(name) + ext)).write_bytes(b"x")
        calls.append(key)
        return 0

    monkeypatch.setattr(mapexport, "main", fake_map)
    app_spec.save_settings("heat3d-r6-maps", {"games": {"r6siege": str(game)}})
    _, out = run("--check", "--json", capsys=capsys)
    checks = {c["id"]: c["ok"] for c in json.loads(out)["checks"]}
    assert checks["game:r6siege"] and checks["oodle"]

    code, out = run("extract", "--new", "--progress-json", capsys=capsys)
    assert code == 0 and json.loads(out.splitlines()[-1]) == {"event": "done", "ok": 2, "failed": 0}
    assert sorted(calls) == ["pvp04_clubhouse", "pvp08_bank"]

    (game / "datapc64_pvp10_chalet.forge").write_bytes(b"chalet")
    _, out = run("status", "--json", capsys=capsys)
    states = {m["id"]: m["state"] for m in json.loads(out)["games"][0]["maps"]}
    assert states == {"r6_Bank": "current", "r6_Clubhouse": "current", "r6_Chalet": "new"}
    man = json.loads((tmp_path / "levels" / "r6siege" / ".heat3d-extract.json").read_text())
    assert man["entries"]["r6_Bank"]["outputs"] == ["r6siege/r6_Bank.glb", "r6siege/r6_Bank.json"]


def test_no_oodle_is_a_failed_check(tmp_path, capsys):
    game = install(tmp_path)
    (game / "oo2core_9_win64.dll").unlink()
    app_spec.save_settings("heat3d-r6-maps", {"games": {"r6siege": str(game)}})
    _, out = run("--check", "--json", capsys=capsys)
    checks = {c["id"]: c for c in json.loads(out)["checks"]}
    assert checks["game:r6siege"]["ok"] and not checks["oodle"]["ok"]
