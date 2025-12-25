from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

from mathutils import Matrix


class EmitTag(str, Enum):
    TRANSFORM_GROUP = "TransformGroup"
    SHAPE = "Shape"
    LIGHT = "Light"
    CAMERA = "Camera"


class NodeKind(Enum):
    TRANSFORM_GROUP = auto()
    BONE = auto()
    ARMATURE = auto()
    SHAPE = auto()
    LIGHT = auto()
    CAMERA = auto()


KIND_TO_TAG: dict[NodeKind, EmitTag] = {
    NodeKind.TRANSFORM_GROUP: EmitTag.TRANSFORM_GROUP,
    NodeKind.BONE: EmitTag.TRANSFORM_GROUP,
    NodeKind.ARMATURE: EmitTag.TRANSFORM_GROUP,
    NodeKind.SHAPE: EmitTag.SHAPE,
    NodeKind.LIGHT: EmitTag.LIGHT,
    NodeKind.CAMERA: EmitTag.CAMERA,
}


def node_emit_tag(node: "SceneNode") -> EmitTag:
    return node.emit_as or KIND_TO_TAG[node.kind]


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
    emit: bool = True  # whether to emit this node (e.g. armature can be collapsed)
    emit_as: EmitTag | None = None

    # generic "bag" for per-kind attributes/flags/anything
    attrs: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ExportIR:
    scene_nodes: dict[int, SceneNode] = field(default_factory=dict)
    roots: list[int] = field(default_factory=list)

    # Prevent duplicate *node creation* when the same Blender Object/Collection is encountered
    # multiple times during normal traversal (e.g. multi-collection membership).
    # Policy: first parent wins. Disabled for instance expansion.
    node_by_object_ptr_first_wins: dict[int, int] = field(default_factory=dict)
    node_by_collection_ptr_first_wins: dict[int, int] = field(default_factory=dict)
