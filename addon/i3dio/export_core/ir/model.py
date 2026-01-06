# i3dio/export_core/ir/model.py
from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, cast

import bpy
from mathutils import Matrix

from ..blender.bones import BoneRef


class NodeKind(Enum):
    UNRESOLVED = "TransformGroup"  # placeholder kind used during traversal
    TRANSFORM_GROUP = "TransformGroup"
    SHAPE = "Shape"
    LIGHT = "Light"
    CAMERA = "Camera"


@dataclass(slots=True)
class EmitAttrs:
    node: dict[str, Any] = field(default_factory=dict)  # attributes for the node itself (e.g. <IndexedTriangleSet>)
    children: dict[str, dict[str, Any]] = field(default_factory=dict)  # child_name -> attrs (e.g. <Vertices>)

    def child(self, tag: str) -> dict[str, Any]:
        return self.children.setdefault(tag, {})


@dataclass(slots=True)
class NodeReference:
    id: int | None = None
    child_path: str | None = None
    runtime_loaded: bool | None = None


class SourceKind(Enum):
    OBJECT = auto()
    COLLECTION = auto()
    BONE_REF = auto()
    OTHER = auto()


@dataclass(slots=True)
class SceneNode:
    """A node in the export scene graph IR."""

    id: int
    name: str
    # Trustworthy identity (set once by builder)
    source_kind: SourceKind
    source_ptr: int | None
    source_object_type: str | None  # only for OBJECT (snapshot of obj.type)

    kind: NodeKind
    blender_ref: object | None
    parent_id: int | None = None
    children: list[int] = field(default_factory=list)
    # Computed local transform in EXPORT space (ready for serializer)
    matrix_local_export: Matrix | None = None
    emit: bool = True  # whether to emit this node (e.g. armature can be collapsed)

    attrs: EmitAttrs = field(default_factory=EmitAttrs)

    # For Shapes in the Scene graph, resolved global export material IDs in subset order.
    # Formatting into the I3D "materialIds" attribute is handled by the serializer.
    material_ids: list[int] | None = None

    # For merge groups / skinned meshes: node ids (not shape ids) that provide skin bind transforms.
    # Formatting into the I3D "skinBindNodeIds" attribute is handled by the serializer.
    skin_bind_node_ids: list[int] | None = None

    # Optional reference info for TransformGroups.
    # Formatting into I3D reference attributes is handled by the serializer.
    reference: "NodeReference" | None = None

    # i3dMappings export fields
    i3d_mapping: bool = False
    i3d_mapping_name: str | None = None

    @property
    def obj(self) -> bpy.types.Object:
        if self.source_kind is not SourceKind.OBJECT:
            raise RuntimeError(f"Node {self.id} is not an Object node")
        return cast(bpy.types.Object, self.blender_ref)

    @property
    def collection(self) -> bpy.types.Collection:
        if self.source_kind is not SourceKind.COLLECTION:
            raise RuntimeError(f"Node {self.id} is not a Collection node")
        return cast(bpy.types.Collection, self.blender_ref)

    @property
    def bone_ref(self) -> "BoneRef":
        if self.source_kind is not SourceKind.BONE_REF:
            raise RuntimeError(f"Node {self.id} is not a BoneRef node")
        return cast(BoneRef, self.blender_ref)

    @property
    def shape_id(self) -> int | None:
        sid = self.attrs.node.get("shapeId")
        return sid if isinstance(sid, int) else None

    @shape_id.setter
    def shape_id(self, value: int | None) -> None:
        if value is None:
            self.attrs.node.pop("shapeId", None)
        else:
            self.attrs.node["shapeId"] = int(value)


@dataclass(slots=True)
class IRIndex:
    """
    Traversal-produced indices/marks that make resolve passes fast and explicit.

    These are NOT user-facing XML attrs; they are internal lookup tables.
    Keep them stable + deterministic (preserve traversal/outliner order).
    """

    node_id_by_blender_ptr: dict[int, list[int]] = field(default_factory=dict)  # blender_ref ptr -> node_id

    merge_children_roots: list[int] = field(default_factory=list)  # node ids
    merge_group_nodes_by_index: dict[int, list[int]] = field(default_factory=dict)  # mg_index -> [node ids]
    skinned_mesh_nodes: list[int] = field(default_factory=list)

    # Armature ptr -> {bone_name: bone_node_id} (built in resolve_armatures)
    bone_nodes_by_armature_ptr: dict[int, dict[str, int]] = field(default_factory=dict)
    armature_nodes: list[int] = field(default_factory=list)  # node ids of armatures


@dataclass(slots=True)
class ExportIR:
    """Intermediate representation of the export scene graph."""

    scene_nodes: dict[int, SceneNode] = field(default_factory=dict)
    node_order: list[int] = field(default_factory=list)  # node ids in creation order (stable)
    roots: list[int] = field(default_factory=list)
    index: IRIndex = field(default_factory=IRIndex)

    def _index_node_blender_ref(self, node: SceneNode) -> None:
        """Index node by its Blender reference pointer (if any)."""
        if (ptr := node.source_ptr) is not None:
            self.index.node_id_by_blender_ptr.setdefault(ptr, []).append(node.id)

    def add_node(self, node: SceneNode, *, parent_id: int | None = None) -> None:
        """Add a pre-created SceneNode into the IR and attach it."""
        self.scene_nodes[node.id] = node
        self.node_order.append(node.id)
        self._index_node_blender_ref(node)
        self.attach(node.id, node.parent_id if parent_id is None else parent_id)

    def iter_nodes(
        self,
        *,
        kind: NodeKind | None = None,
        source_kind: SourceKind | None = None,
        source_object_type: str | None = None,
        emitted_only: bool = False,
    ) -> Iterator[SceneNode]:
        for node_id in self.node_order:
            n = self.scene_nodes[node_id]
            if kind is not None and n.kind != kind:
                continue
            if source_kind is not None and n.source_kind != source_kind:
                continue
            if source_object_type is not None and n.source_object_type != source_object_type:
                continue
            if emitted_only and not n.emit:
                continue
            yield n

    def iter_objects(self, *, obj_type: str | None = None, emitted_only: bool = False) -> Iterator[SceneNode]:
        return self.iter_nodes(source_kind=SourceKind.OBJECT, source_object_type=obj_type, emitted_only=emitted_only)

    def nodes_snapshot(self, *, kind: NodeKind | None = None, emitted_only: bool = False) -> list[SceneNode]:
        return list(self.iter_nodes(kind=kind, emitted_only=emitted_only))

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
        # if already attached, detach first to avoid duplicates
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
