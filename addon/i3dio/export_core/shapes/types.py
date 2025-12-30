# i3dio/export_core/shapes/types.py
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
class MeshContribution:
    obj: bpy.types.Object
    reference_frame: mathutils.Matrix | None  # Blender-space frame

    # MergeChildren / generic vertex attribute
    g_value: float | None = None  # normalized [0..1]

    # MergeGroup / singleblendweights
    bind_index: int | None = None  # 0..N-1
