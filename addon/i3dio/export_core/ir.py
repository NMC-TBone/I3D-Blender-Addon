from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

from mathutils import Matrix


class NodeKind(Enum):
    TRANSFORM_GROUP = auto()
    # later: SHAPE, LIGHT, CAMERA, etc.


@dataclass(slots=True)
class SceneNode:
    id: int
    name: str
    kind: NodeKind
    blender_ref: Any | None
    parent_id: int | None = None
    children: list[int] = field(default_factory=list)
    # store matrix in Blender space for now; convert at serialize time
    matrix_world: Matrix | None = None
    emit_as: str | None = None  # e.g. "TransformGroup", "Camera", "Light", etc.

    # generic "bag" for per-kind attributes/flags/anything
    attrs: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ExportIR:
    scene_nodes: dict[int, SceneNode] = field(default_factory=dict)
    roots: list[int] = field(default_factory=list)
    # For fast lookup / dedup:
    # key is a stable identity for the Blender datablock (pointer integer)
    dedup_map: dict[int, int] = field(default_factory=dict)  # datablock_ptr -> node id
