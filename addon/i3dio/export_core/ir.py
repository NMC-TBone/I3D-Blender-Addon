from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any


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
    matrix_world: Any | None = None


@dataclass(slots=True)
class ExportIR:
    nodes: dict[int, SceneNode] = field(default_factory=dict)
    roots: list[int] = field(default_factory=list)
    # For fast lookup / dedup:
    by_object: dict[Any, int] = field(default_factory=dict)  # bpy object -> node id
