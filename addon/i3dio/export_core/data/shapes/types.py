# export_core/shapes/types.py
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

import bpy
import mathutils


class ShapeMode(Enum):
    NORMAL = auto()
    MERGE_GROUP = auto()
    MERGE_CHILDREN_GENERIC = auto()


@dataclass(slots=True)
class MeshContribution:
    obj: bpy.types.Object
    reference_frame: mathutils.Matrix | None  # Blender-space frame
    id_value: float  # g (float) OR bind index (int stored as float)
