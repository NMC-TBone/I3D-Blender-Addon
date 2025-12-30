# i3dio/export_core/shapes/its/built.py
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ...ir import XmlBuckets

Vec3f = np.ndarray  # (N,3) float32
Vec2f = np.ndarray  # (N,2) float32
ArrI = np.ndarray  # (M,) int32/uint32


@dataclass(slots=True)
class BuiltSubset:
    first_index: int
    num_indices: int
    first_vertex: int
    num_vertices: int
    material_id: int


@dataclass(slots=True)
class BuiltITS:
    name: str
    shape_id: int
    # Required data arrays, if not filled builder need to return None
    positions: Vec3f = field(repr=False)  # (N,3) float32
    normals: Vec3f = field(repr=False)  # (N,3) float32 (mandatory)
    indices: ArrI = field(repr=False)  # (K,) int32/uint32, flattened

    subsets: list[BuiltSubset]
    material_ids: list[int]  # in subset order

    # Optional/variable
    uvs: list[Vec2f] = field(repr=False, default_factory=list)  # 0..4, each (N,2) float32

    g: np.ndarray | None = None
    bi: np.ndarray | None = None

    xml: XmlBuckets = field(default_factory=XmlBuckets)

    @property
    def vertex_count(self) -> int:
        return int(self.positions.shape[0])
