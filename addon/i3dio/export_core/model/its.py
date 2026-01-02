from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

import numpy as np

from ..ir import EmitAttrs


class MaterialKeyKind(str, Enum):
    """How triangles/subsets are grouped by material.

    - SLOT_INDEX: subset keys are material slot indices from Blender meshes
        (materialIds resolved per Scene node instance).
    - MATERIAL_ID: subset keys are resolved global export material IDs
        (used for merge modes where contributors may have different slot layouts).
    """

    SLOT_INDEX = "slot_index"
    MATERIAL_ID = "material_id"


Vec3f = np.ndarray  # (N,3) float32
Vec2f = np.ndarray  # (N,2) float32
ArrI = np.ndarray  # (M,) int32/uint32


@dataclass(slots=True)
class BuiltSubset:
    first_index: int
    num_indices: int
    first_vertex: int
    num_vertices: int
    material_id: int  # material key (see BuiltITS.material_kind)
    material_slot_name: str | None = None  # optional Subset@materialSlotName


@dataclass(slots=True)
class BuiltITS:
    name: str
    shape_id: int
    material_kind: MaterialKeyKind
    # Required data arrays, if not filled builder need to return None
    positions: Vec3f = field(repr=False)  # (N,3) float32
    normals: Vec3f = field(repr=False)  # (N,3) float32 (mandatory)
    indices: ArrI = field(repr=False)  # (K,) int32/uint32, flattened

    subsets: list[BuiltSubset]
    material_ids: list[int]  # material keys in subset order (see material_kind)

    # Optional/variable
    uvs: list[Vec2f] = field(repr=False, default_factory=list)  # 0..4, each (N,2) float32

    g: np.ndarray | None = None
    bi: np.ndarray | None = None

    attrs: EmitAttrs = field(default_factory=EmitAttrs)

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
    tri_mat_id: np.ndarray  # (T,) int32, material key per tri (see BuiltITS.material_kind)

    generic_value01: np.ndarray | None  # (L,) float32
    bind_idx: np.ndarray | None  # (L,) int32 (or float32 if writer expects float)
