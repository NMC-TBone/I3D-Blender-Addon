# i3dio/export_core/shapes/model.py
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

import bpy
import mathutils


class ShapeMode(Enum):
    NORMAL = auto()
    MERGE_GROUP = auto()
    MERGE_CHILDREN_GENERIC = auto()
    SKINNED_MESH = auto()


@dataclass(slots=True)
class ShapeContributor:
    obj: bpy.types.Object
    reference_frame: mathutils.Matrix | None  # Blender-space frame

    # MergeChildren / generic vertex attribute
    generic_value01: float | None = None  # normalized [0..1]

    # MergeGroup / singleblendweights
    bind_index: int | None = None  # 0..N-1

    # Skinned mesh: mapping from Blender vertex group index -> bind index in skinBindNodeIds list
    skin_vgroup_to_bind_index: dict[int, int] | None = None
