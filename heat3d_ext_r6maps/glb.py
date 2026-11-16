"""
Just enough glTF binary for a level: shared meshes placed by nodes.

Each mesh is stored once (positions float32, triangle indices uint32) and
every placement is a node with its matrix, so a prop used 400 times costs
400 small nodes, not 400 copies. The viewer reads node names as part names
(`ground:...`, `structure:...`) and node `extras` are kept for tools that want
the ids behind a part.
"""

from __future__ import annotations

import json
import struct
from pathlib import Path

import numpy as np


class Writer:
    def __init__(self) -> None:
        self.blob = bytearray()
        self.views: list[dict] = []
        self.accessors: list[dict] = []
        self.meshes: list[dict] = []
        self.nodes: list[dict] = []

    def _add(self, array: np.ndarray, target: int, kind: str, component: int, bounds: bool = False) -> int:
        while len(self.blob) % 4:
            self.blob.append(0)
        raw = array.tobytes()
        self.views.append({"buffer": 0, "byteOffset": len(self.blob), "byteLength": len(raw), "target": target})
        self.blob.extend(raw)
        acc = {"bufferView": len(self.views) - 1, "componentType": component, "count": int(len(array)), "type": kind}
        if bounds:
            acc["min"] = array.min(axis=0).astype(float).tolist()
            acc["max"] = array.max(axis=0).astype(float).tolist()
        self.accessors.append(acc)
        return len(self.accessors) - 1

    def positions(self, points: np.ndarray) -> int:
        return self._add(np.ascontiguousarray(points, dtype=np.float32), 34962, "VEC3", 5126, bounds=True)

    def mesh(self, name: str, positions: int, triangles: np.ndarray) -> int:
        """A mesh over an existing position accessor; returns its index."""
        tris = np.ascontiguousarray(triangles, dtype=np.uint32).reshape(-1)
        prim = {"attributes": {"POSITION": positions}, "indices": self._add(tris, 34963, "SCALAR", 5125)}
        self.meshes.append({"name": name, "primitives": [prim]})
        return len(self.meshes) - 1

    def node(self, name: str, mesh: int, matrix: np.ndarray | None = None, extras: dict | None = None) -> int:
        n: dict = {"name": name, "mesh": mesh}
        if matrix is not None and not np.allclose(matrix, np.eye(4)):
            # glTF matrices are column-major.
            n["matrix"] = [float(v) for v in np.asarray(matrix, dtype=np.float64).T.reshape(-1)]
        if extras:
            n["extras"] = extras
        self.nodes.append(n)
        return len(self.nodes) - 1

    def write(self, path: str | Path, extras: dict | None = None) -> int:
        doc = {
            "asset": {"version": "2.0", "generator": "heat3d-r6-maps"},
            "scene": 0,
            "scenes": [{"nodes": list(range(len(self.nodes)))}],
            "nodes": self.nodes,
            "meshes": self.meshes,
            "accessors": self.accessors,
            "bufferViews": self.views,
            "buffers": [{"byteLength": len(self.blob)}],
        }
        if extras:
            doc["asset"]["extras"] = extras
        text = json.dumps(doc, separators=(",", ":")).encode()
        text += b" " * (-len(text) % 4)
        while len(self.blob) % 4:
            self.blob.append(0)
        out = bytearray(struct.pack("<III", 0x46546C67, 2, 12 + 8 + len(text) + 8 + len(self.blob)))
        out += struct.pack("<II", len(text), 0x4E4F534A) + text
        out += struct.pack("<II", len(self.blob), 0x004E4942) + self.blob
        tmp = Path(str(path) + ".part")
        tmp.write_bytes(bytes(out))
        tmp.replace(path)
        return len(out)


def read(path: str | Path) -> tuple[dict, bytes]:
    """The JSON document and binary chunk of a .glb (for checks and tests)."""
    data = Path(path).read_bytes()
    magic, _, length = struct.unpack_from("<III", data, 0)
    if magic != 0x46546C67:
        raise ValueError(f"{path} is not a .glb")
    doc, blob, at = None, b"", 12
    while at < length:
        size, kind = struct.unpack_from("<II", data, at)
        chunk = data[at + 8 : at + 8 + size]
        if kind == 0x4E4F534A:
            doc = json.loads(chunk)
        elif kind == 0x004E4942:
            blob = chunk
        at += 8 + size
    if doc is None:
        raise ValueError(f"{path} has no JSON chunk")
    return doc, blob


def accessor(doc: dict, blob: bytes, index: int) -> np.ndarray:
    a = doc["accessors"][index]
    view = doc["bufferViews"][a["bufferView"]]
    kind = {5125: np.uint32, 5126: np.float32, 5123: np.uint16}[a["componentType"]]
    width = {"SCALAR": 1, "VEC3": 3}[a["type"]]
    arr = np.frombuffer(blob, kind, count=a["count"] * width, offset=view.get("byteOffset", 0) + a.get("byteOffset", 0))
    return arr.reshape(a["count"], width) if width > 1 else arr
