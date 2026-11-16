"""`unpack` on synthetic archives with a stand-in decompressor (no Oodle involved)."""

from __future__ import annotations

import json
import struct

from heat3d_ext_r6maps import forge, unpack


def _pack(raw: bytes) -> bytes:
    """The stand-in 'compression': reversed, with one marker byte (so it is never stored-sized)."""
    return b"#" + raw[::-1]


def fake(src: bytes, size: int) -> bytes:
    assert src[:1] == b"#"
    out = src[1:][::-1]
    assert len(out) == size
    return out


def _block(chunks: list[bytes], packed: bool) -> bytes:
    stored = [_pack(c) if packed else c for c in chunks]
    head = forge.BLOCK + struct.pack("<HBII", 3, 0x0F, 0x80040000, len(chunks))
    head += b"".join(struct.pack("<II", len(c), len(s)) for c, s in zip(chunks, stored))
    return head + b"".join(b"\x00" * 4 + s for s in stored)


def _resource(kind: int, rid: int, body: bytes) -> bytes:
    payload = struct.pack("<IQ", kind, rid) + body
    return struct.pack("<HH", 4, 2) + b"meta" + struct.pack("<I", len(payload)) + payload


def _archive(packed_header: bool) -> bytes:
    res = [(0x5E00000001, _resource(0xABEB2DFB, 0x5E00000001, b"mesh" * 50)),
           (0x5E00000002, _resource(0x3ADFCF6C, 0x5E00000002, b"thing"))]
    header = struct.pack("<I", len(res)) + b"".join(struct.pack("<QI", r, len(b)) for r, b in res)
    body = b"".join(b for _, b in res)
    out = bytearray(forge.MAGIC + struct.pack("<I", 34))
    out += bytes(-len(out) % forge.PAGE)
    out += _block([header], packed_header) + _block([body[:100], body[100:]], True)
    out += bytes(-len(out) % forge.PAGE)
    return bytes(out)


def test_unpack_writes_each_resource_and_an_index(tmp_path):
    src = tmp_path / "datapc64_pvp99_test_mod.forge"
    src.write_bytes(_archive(packed_header=True))
    out = tmp_path / "out"
    totals = unpack.run([src], out, fake)
    assert totals == {"archives": 1, "skipped": 0, "resources": 2, "bytes": totals["bytes"]}
    index = json.loads((out / src.stem / "index.json").read_text())
    assert index["complete"] and index["version"] == 34
    res = index["entries"][0]["resources"]
    assert [r["kind"] for r in res] == ["abeb2dfb", "3adfcf6c"]
    body = (out / src.stem / res[0]["file"]).read_bytes()
    assert forge.head(body)[:2] == (0xABEB2DFB, 0x5E00000001) and body.endswith(b"mesh" * 50)


def test_unpack_resumes_and_skips(tmp_path):
    src = tmp_path / "a.forge"
    src.write_bytes(_archive(packed_header=False))
    out = tmp_path / "out"
    unpack.run([src], out, fake)
    # A finished archive is skipped without touching the decompressor.
    assert unpack.run([src], out, lambda s, n: (_ for _ in ()).throw(AssertionError("decompressed again")))["skipped"] == 1
    # An unfinished one (no index yet) skips the entries its log already has.
    (out / "a" / "index.json").unlink()
    again = unpack.run([src], out, lambda s, n: (_ for _ in ()).throw(AssertionError("decompressed again")))
    assert again["archives"] == 1 and again["resources"] == 2


def test_estimate_and_selection(tmp_path):
    src = tmp_path / "datapc64_pvp04_clubhouse_mod.forge"
    src.write_bytes(_archive(packed_header=True))
    for n in ("datapc64_merged_bnk_mesh.forge", "datapc64_merged_bnk_meshshape.forge", "datapc64_merged_bnk_textures0.forge",
              "datapc64_pvp01_house_v3_mod.forge", "datapc64_pvp01_house_v3_bnk_gidata.forge", "datapc64.forge",
              "datapc64_mtx_bnk_mesh.forge"):
        (tmp_path / n).write_bytes(b"")
    first = [p.name for p in unpack.select(tmp_path, first=True)]
    assert first == ["datapc64_pvp04_clubhouse_mod.forge", "datapc64_merged_bnk_mesh.forge"]
    every = [p.name for p in unpack.select(tmp_path)]
    assert every[:2] == first and "datapc64_pvp01_house_v3_mod.forge" in every and "datapc64.forge" in every
    assert every[-1] == "datapc64_merged_bnk_meshshape.forge"
    assert not any("textures" in n or "gidata" in n or "mtx" in n for n in every)
    # What gets written: the resources, not the header blocks.
    assert unpack.estimate(src) == sum(len(_resource(0, 0, b)) for b in (b"mesh" * 50, b"thing"))
