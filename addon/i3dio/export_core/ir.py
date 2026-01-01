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
    UNRESOLVED = auto()  # placeholder kind used during traversal
    TRANSFORM_GROUP = auto()
    BONE = auto()
    ARMATURE = auto()
    SHAPE = auto()
    LIGHT = auto()
    CAMERA = auto()


KIND_TO_TAG: dict[NodeKind, EmitTag] = {
    NodeKind.UNRESOLVED: EmitTag.TRANSFORM_GROUP,
    NodeKind.TRANSFORM_GROUP: EmitTag.TRANSFORM_GROUP,
    NodeKind.BONE: EmitTag.TRANSFORM_GROUP,
    NodeKind.ARMATURE: EmitTag.TRANSFORM_GROUP,
    NodeKind.SHAPE: EmitTag.SHAPE,
    NodeKind.LIGHT: EmitTag.LIGHT,
    NodeKind.CAMERA: EmitTag.CAMERA,
}


def node_emit_tag(node: "SceneNode") -> EmitTag:
    return node.emit_as or KIND_TO_TAG.get(node.kind, EmitTag.TRANSFORM_GROUP)


@dataclass(slots=True)
class XmlBuckets:
    node: dict[str, Any] = field(default_factory=dict)  # attributes for the node itself (e.g. <IndexedTriangleSet>)
    children: dict[str, dict[str, Any]] = field(default_factory=dict)  # child_name -> attrs (e.g. <Vertices>)


@dataclass(slots=True)
class SceneNode:
    """A node in the export scene graph IR."""

    id: int
    name: str
    kind: NodeKind
    blender_ref: Any | None
    parent_id: int | None = None
    children: list[int] = field(default_factory=list)
    # Computed local transform in EXPORT space (ready for serializer)
    matrix_local_export: Matrix | None = None
    emit: bool = True  # whether to emit this node (e.g. armature can be collapsed)
    emit_as: EmitTag | None = None

    xml: XmlBuckets = field(default_factory=XmlBuckets)
    # generic "bag" for per-kind attributes/flags/anything
    attrs: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class IRIndex:
    """
    Traversal-produced indices/marks that make resolve passes fast and explicit.

    These are NOT user-facing XML attrs; they are internal lookup tables.
    Keep them stable + deterministic (preserve traversal/outliner order).
    """

    merge_children_roots: list[int] = field(default_factory=list)  # node ids
    merge_group_nodes_by_index: dict[int, list[int]] = field(default_factory=dict)  # mg_index -> [node ids]
    # (future)
    # skinned_mesh_nodes: list[int] = field(default_factory=list)


@dataclass(slots=True)
class ExportIR:
    """Intermediate representation of the export scene graph."""

    scene_nodes: dict[int, SceneNode] = field(default_factory=dict)
    roots: list[int] = field(default_factory=list)
    index: IRIndex = field(default_factory=IRIndex)

    def add_node(self, node: SceneNode, *, parent_id: int | None = None) -> None:
        """Add a pre-created SceneNode into the IR and attach it."""
        self.scene_nodes[node.id] = node
        self.attach(node.id, node.parent_id if parent_id is None else parent_id)

    def detach(self, node_id: int) -> None:
        """Detach node from its parent (if any)."""
        n = self.scene_nodes[node_id]
        if n.parent_id is None:
            try:
                self.roots.remove(node_id)
            except ValueError:
                pass
        else:
            if (p := self.scene_nodes.get(n.parent_id)) is not None:
                try:
                    p.children.remove(node_id)
                except ValueError:
                    pass
        n.parent_id = None

    def attach(self, node_id: int, parent_id: int | None) -> None:
        """Attach node under parent_id (or to roots if parent_id is None)."""
        n = self.scene_nodes[node_id]
        # if already attached, detach first
        if n.parent_id is not None or node_id in self.roots:
            self.detach(node_id)

        n.parent_id = parent_id
        if parent_id is None:
            self.roots.append(node_id)
        else:
            self.scene_nodes[parent_id].children.append(node_id)

    def reparent(self, node_id: int, new_parent_id: int | None) -> None:
        """Reparent node to new_parent_id, updating both roots and children lists safely."""
        self.detach(node_id)
        self.attach(node_id, new_parent_id)
