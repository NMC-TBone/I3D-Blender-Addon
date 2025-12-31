# i3dio/export_core/shapes/its/model.py
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

    @property
    def triangle_count(self) -> int:
        return int(self.indices.shape[0] // 3)


@dataclass(slots=True)
class ItsContributorStream:
    obj_name: str
    loop_count: int

    positions: np.ndarray  # (L,3) float32
    normals: np.ndarray  # (L,3) float32 (mandatory)
    uvs: list[np.ndarray]  # 0..4 each (L,2) float32

    tri_loops: np.ndarray  # (T,3) int32, loop indices
    tri_mat_id: np.ndarray  # (T,) int32, resolved materialId per tri

    generic_value01: np.ndarray | None  # (L,) float32
    bind_idx: np.ndarray | None  # (L,) int32 (or float32 if writer expects float)
