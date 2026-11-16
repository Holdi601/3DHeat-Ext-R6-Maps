"""The map builder on a synthetic unpacked archive: meshes, a wrapper, a breakable group, entities, a world."""

from __future__ import annotations

import json
import struct

import numpy as np

from heat3d_ext_r6maps import glb, level, mapexport

WORLD_ID = 0x5E00000001


def _resource(kind: int, rid: int, payload: bytes) -> bytes:
    body = struct.pack("<IQ", kind, rid) + payload
    return struct.pack("<HH", 4, 2) + b"meta" + struct.pack("<I", len(body)) + body


def _mesh(rid: int, points: list[tuple[float, float, float]], tris: list[tuple[int, int, int]], scale: int = 4) -> bytes:
    """A mesh the way the banks store it: int16 x, y, z and a per-vertex scale s (position = xyz * s / 32768)."""
    q = np.round(np.array(points) * 32768 / scale).astype(np.int16)
    verts = np.c_[q, np.full(len(q), scale, np.int16)]
    stride = 24
    vbytes = len(points) * stride
    vertex_block = verts.astype("<i2").tobytes() + b"\x00" * (vbytes - verts.nbytes)
    # Padded the way the game pads: whole groups of triangles, the last one repeated.
    padded = list(tris) + [tris[-1]] * 2
    index_block = np.array(padded, dtype="<u2").tobytes()
    words = [level.MESH, 0, 0, 0xFC9E1595, 0, 0x14, 1, stride, vbytes, len(index_block)] + [0] * 14
    return _resource(level.MESH, rid, struct.pack("<24I", *words) + vertex_block + index_block)


def _entity(rid: int, matrix: np.ndarray, *holders: int) -> bytes:
    # kind, id, kind again, the matrix (row-vector form, translation in the last row), then components naming holders.
    payload = struct.pack("<I", level.ENTITY) + matrix.astype("<f4").tobytes() + b"\x01\x02" + \
        b"".join(b"\xf8\xfb" + struct.pack("<Q", h) for h in holders)
    return _resource(level.ENTITY, rid, payload)


def _write(folder, name, resources):
    folder.mkdir(parents=True, exist_ok=True)
    entries = []
    for i, (rid, kind, body) in enumerate(resources):
        f = f"{0x1000 * (i + 1):08x}_{rid:016x}.bin"
        (folder / f).write_bytes(body)
        entries.append({"entry": f"{0x1000 * (i + 1):x}",
                        "resources": [{"id": f"{rid:x}", "kind": f"{kind:08x}", "size": len(body), "file": f}]})
    (folder / "index.json").write_text(json.dumps({"archive": name, "complete": True, "entries": entries}))


def _world(tmp_path):
    root = tmp_path / "unpacked"
    floor = [(-5, -5, 0), (5, -5, 0), (5, 5, 0), (-5, 5, 0)]
    wall = [(0, 0, 0), (0, 2, 0), (0, 2, 3), (0, 0, 3)]
    _write(root / "datapc64_merged_bnk_mesh", "datapc64_merged_bnk_mesh.forge", [
        (0x101, level.MESH, _mesh(0x101, floor, [(0, 1, 2), (0, 2, 3)], scale=8)),
        (0x102, level.MESH, _mesh(0x102, wall, [(0, 1, 2), (0, 2, 3)], scale=8)),
        # A 30 m ground plate: its material names no texture.
        (0x103, level.MESH, _mesh(0x103, [(-15, -15, 0), (15, -15, 0), (15, 15, 0)], [(0, 1, 2)], scale=16)),
    ])
    move = np.eye(4)
    move[3, :3] = (-60.0, 90.0, 0.4)
    wall_at = np.eye(4)
    wall_at[3, :3] = (-58.0, 88.0, 0.4)
    wrapper = _resource(level.WRAPPER, 0x201, b"\x00" * 9 + struct.pack("<Q", 0x101))
    group = _resource(level.GROUP, 0x202, b"\x00" * 5 + struct.pack("<Q", 0x102))
    volume = _resource(level.WRAPPER, 0x203, struct.pack("<QIQ", 0x103, 1, 0x401))
    material = _resource(level.MATERIAL, 0x401, b"\x00" * 12)
    _write(root / "datapc64_pvp04_clubhouse_mod", "datapc64_pvp04_clubhouse_mod.forge", [
        (WORLD_ID, level.WORLD, _resource(level.WORLD, WORLD_ID, b"\x00" * 16)),
        (0x201, level.WRAPPER, wrapper),
        (0x202, level.GROUP, group),
        (0x301, level.ENTITY, _entity(0x301, move, 0x201)),
        (0x302, level.ENTITY, _entity(0x302, wall_at, 0x202, 0x202)),
        (0x203, level.WRAPPER, volume),
        (0x401, level.MATERIAL, material),
        (0x303, level.ENTITY, _entity(0x303, move, 0x203)),
    ])
    return root


def test_mesh_decode_scale_and_padding(tmp_path):
    body = _mesh(1, [(0, 0, 0), (1.5, 0, 0), (0, -2.25, 1)], [(0, 1, 2)])
    pos, tris = level.decode_mesh(body)
    assert np.allclose(pos, [(0, 0, 0), (1.5, 0, 0), (0, -2.25, 1)], atol=1e-3)
    assert tris.tolist() == [[0, 1, 2]]  # the padding repeats are gone


def test_placements_and_level(tmp_path):
    root = _world(tmp_path)
    lib = level.Library(root)
    placed = level.placements(lib, root / "datapc64_pvp04_clubhouse_mod")
    assert {(p.entity, p.mesh, p.group) for p in placed} == {(0x301, 0x101, False), (0x302, 0x102, True),
                                                             (0x303, 0x103, False)}
    out = tmp_path / "levels"
    info = mapexport.build(lib, root / "datapc64_pvp04_clubhouse_mod", "Clubhouse", out, "pvp04_clubhouse")
    assert info["world_id"] == WORLD_ID and info["breakable_parts"] == 1 and info["plates"] == 1
    assert info["ground_triangles"] == 3 and info["structure_triangles"] == 2  # the plate is ground too
    doc, blob = glb.read(out / "r6_Clubhouse.glb")
    names = sorted(n["name"] for n in doc["nodes"])
    assert names == [f"ground:r6 Clubhouse @{WORLD_ID}", f"ground:r6 Clubhouse @{WORLD_ID} plate",
                     f"structure:r6 Clubhouse @{WORLD_ID} breakable {0x302}"]
    # The floor lands where the entity put it, in the viewer's frame (x, z, y).
    node = next(n for n in doc["nodes"] if n["name"] == f"ground:r6 Clubhouse @{WORLD_ID}")
    m = np.array(node["matrix"]).reshape(4, 4).T
    local = glb.accessor(doc, blob, doc["meshes"][node["mesh"]]["primitives"][0]["attributes"]["POSITION"])
    world = (np.c_[local, np.ones(len(local))] @ m.T)[:, :3]
    assert np.allclose(world.min(0), (-65, 0.4, 85), atol=1e-3) and np.allclose(world.max(0), (-55, 0.4, 95), atol=1e-3)
    wall = next(n for n in doc["nodes"] if "breakable" in n["name"])
    assert wall["extras"]["r6"] == {"entity": str(0x302), "group": "202", "mesh": "102"}
    saved = json.loads((out / "r6_Clubhouse.json").read_text())
    assert saved["breakables"][0]["min"] == [-58.0, 88.0, 0.4] and saved["breakables"][0]["max"] == [-58.0, 90.0, 3.4]
    assert saved["breakables"][0]["shape"] == "wall"  # 2 m across, no thickness, 3 m high
    assert mapexport.shape_of([2.0, 0.2, 3.0]) == "wall" and mapexport.shape_of([1.2, 1.0, 0.1]) == "floor"


def test_map_names():
    assert mapexport.map_of("datapc64_pvp04_clubhouse_mod.forge") == ("Clubhouse", "pvp04_clubhouse")
    assert mapexport.map_of("datapc64_pvp04_clubhouse_mod_set01_bnk_gidata.forge") is None
    assert mapexport.map_of("datapc64_merged_bnk_mesh") is None
    assert mapexport.file_stem("Kafe Dostoyevsky") == "r6_Kafe-Dostoyevsky"


def test_map_cli_on_unpacked(tmp_path):
    root = _world(tmp_path)
    out = tmp_path / "levels"
    assert mapexport.main(["--all", "--unpacked", str(root), "--out", str(out)]) == 0
    assert (out / "r6_Clubhouse.glb").exists() and (out / "MAPS.DONE").exists()
    # A second run keeps what is built.
    assert mapexport.main(["--all", "--unpacked", str(root), "--out", str(out)]) == 0
    assert "have  Clubhouse" in (out / "map.log").read_text()


def test_simplify_keeps_the_shape_with_fewer_triangles():
    # A dense 2 m x 2 m sheet, 80 x 80 quads (12,800 triangles), bent into a ridge.
    n = 81
    xs, ys = np.meshgrid(np.linspace(0, 2, n), np.linspace(0, 2, n))
    pos = np.c_[xs.ravel(), ys.ravel(), 0.3 * np.abs(xs.ravel() - 1)].astype(np.float32)
    quads = [(i * n + j, i * n + j + 1, (i + 1) * n + j + 1, (i + 1) * n + j) for i in range(n - 1) for j in range(n - 1)]
    tris = np.array([t for a, b, c, d in quads for t in ((a, b, c), (a, c, d))], dtype=np.int32)
    p, t = mapexport.simplify(pos, tris)
    assert len(t) <= len(tris) // 8 and len(t) > 0
    assert np.allclose(p.min(0), pos.min(0), atol=0.05) and np.allclose(p.max(0), pos.max(0), atol=0.05)


def test_alignment_on_a_synthetic_level(tmp_path):
    from heat3d_ext_r6maps import alignment

    root = _world(tmp_path)
    out = tmp_path / "levels"
    mapexport.build(level.Library(root), root / "datapc64_pvp04_clubhouse_mod", "Clubhouse", out, "pvp04_clubhouse")
    tris, breakable = alignment.triangles(out / "r6_Clubhouse.glb")
    # Back in the replays' frame: the floor at z = 0.4 around (-60, 90), the wall a breakable.
    floor = tris[~breakable]
    assert np.allclose(floor[:, :, 2], 0.4, atol=1e-4) and np.allclose(floor[:, :, :2].mean((0, 1)), (-60, 90), atol=1e-3)
    assert breakable.sum() == 3  # the wall's two triangles and the plate's one
    feet = np.array([[-60.0, 90.0, 0.45], [-62.0, 91.0, 0.4], [-80.0, 90.0, 0.4]])
    grid = alignment.Grid(tris, feet)
    h, _ = grid.heights(-60.0, 90.0)
    assert np.allclose(h, 0.4, atol=1e-4) and len(h) >= 1
    assert len(grid.heights(-80.0, 90.0)[0]) == 0


def test_game_folder_is_the_one_given(tmp_path, monkeypatch):
    from heat3d_ext_r6maps import install

    game = tmp_path / "game"
    game.mkdir()
    monkeypatch.delenv("HEAT3D_R6_GAME", raising=False)
    assert install.game_folder(game) is None  # no archives in it
    (game / "datapc64.forge").write_bytes(b"scimitar\x00")
    assert install.game_folder(game) == game
    assert install.game_folder() is None  # nothing given, nothing searched
    monkeypatch.setenv("HEAT3D_R6_GAME", str(game))
    assert install.game_folder() == game


def test_oodle_only_from_the_path_given(tmp_path, monkeypatch):
    import pytest

    from heat3d_ext_r6maps import oodle

    monkeypatch.delenv("HEAT3D_OODLE", raising=False)
    monkeypatch.setattr(oodle, "_lib", None)
    with pytest.raises(oodle.OodleUnavailable):
        oodle.load()
    not_a_dll = tmp_path / "oo2core_9_win64.dll"
    not_a_dll.write_bytes(b"MZ" + b"\x00" * 200)
    with pytest.raises(oodle.OodleUnavailable):
        oodle.load(not_a_dll)
