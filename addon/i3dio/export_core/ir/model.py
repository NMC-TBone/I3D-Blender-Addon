# i3dio/export_core/ir/model.py
from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import Enum, StrEnum, auto
from typing import Any, cast

import bpy
from mathutils import Matrix

from ..blender.bones import BoneRef

BlenderRef = bpy.types.Object | bpy.types.Collection | BoneRef


class NodeKind(StrEnum):
    TRANSFORM_GROUP = "TransformGroup"
    REFERENCE_NODE = "ReferenceNode"
    SHAPE = "Shape"
    LIGHT = "Light"
    CAMERA = "Camera"
    UNRESOLVED = "__UNRESOLVED__"  # placeholder kind used during traversal, should not appear in final IR


class SourceKind(Enum):
    OBJECT = auto()
    COLLECTION = auto()
    BONE_REF = auto()
    OTHER = auto()


@dataclass(slots=True)
class EmitAttrs:
    node: dict[str, Any] = field(default_factory=dict)  # attributes for the node itself (e.g. <IndexedTriangleSet>)
    children: dict[str, dict[str, Any]] = field(default_factory=dict)  # child_name -> attrs (e.g. <Vertices>)

    def child(self, tag: str) -> dict[str, Any]:
        return self.children.setdefault(tag, {})


@dataclass(slots=True)
class ShapeSceneExt:
    shape_id: int | None = None
    # For Shapes in the Scene graph, resolved global export material IDs in subset order.
    # Formatting into the I3D "materialIds" attribute is handled by the serializer.
    material_ids: list[int] | None = None
    # For merge groups / skinned meshes: node ids (not shape ids) that provide skin bind transforms.
    # Formatting into the I3D "skinBindNodeIds" attribute is handled by the serializer.
    skin_bind_node_ids: list[int] | None = None


@dataclass(slots=True)
class ReferenceNodeExt:
    reference_id: int | None = None
    runtime_loaded: bool = False
    child_path: str | None = None


@dataclass(slots=True)
class SceneNode:
    """A node in the export scene graph IR."""

    id: int
    name: str
    kind: NodeKind
    # Trustworthy identity (set once by builder)
    source_kind: SourceKind
    parent_id: int | None = None

    matrix_local_export: Matrix | None = None  # Computed local transform in EXPORT space (ready for serializer)
    emit: bool = True  # whether to emit this node (e.g. armature can be collapsed)
    attrs: EmitAttrs = field(default_factory=EmitAttrs)

    source_ptr: int | None = None
    source_object_type: str | None = None  # only for OBJECT (snapshot of obj.type)
    blender_ref: BlenderRef | None = None

    # Kind-specific extensions (all Scene nodes in i3D is a extension of TransformGroup)
    _shape: ShapeSceneExt | None = None
    _ref: ReferenceNodeExt | None = None

    @property
    def shape(self) -> ShapeSceneExt:
        if self.kind is not NodeKind.SHAPE:
            raise RuntimeError(f"Node {self.id} (kind={self.kind}) is not a Shape node")
        if self._shape is None:
            raise RuntimeError(f"Node {self.id} is a Shape but _shape extension is None (not initialized)")
        return self._shape

    @property
    def ref(self) -> ReferenceNodeExt:
        if self.kind is not NodeKind.REFERENCE_NODE:
            raise RuntimeError(f"Node {self.id} (kind={self.kind}) is not a Reference node")
        if self._ref is None:
            raise RuntimeError(f"Node {self.id} is a ReferenceNode but _ref extension is None (not initialized)")
        return self._ref

    @property
    def obj(self) -> bpy.types.Object:
        if self.source_kind is not SourceKind.OBJECT:
            raise RuntimeError(f"Node {self.id} is not an Object node")
        return cast(bpy.types.Object, self.blender_ref)

    @property
    def bone_ref(self) -> BoneRef:
        if self.source_kind is not SourceKind.BONE_REF:
            raise RuntimeError(f"Node {self.id} is not a BoneRef node")
        return cast(BoneRef, self.blender_ref)


@dataclass(slots=True)
class IRIndex:
    """
    Internal lookup tables built during traversal/resolve.
    Not user-facing XML attrs; keep them stable and deterministic.
    """

    node_id_by_blender_ptr: dict[int, list[int]] = field(default_factory=dict)  # blender_ref ptr -> node_id
    merge_children_roots: list[int] = field(default_factory=list)  # node ids
    merge_group_nodes_by_index: dict[int, list[int]] = field(default_factory=dict)  # mg_index -> [node ids]
    # Armature object ptr -> {bone_name: bone_node_id} (built in resolve_armatures)
    bone_nodes_by_armature_ptr: dict[int, dict[str, int]] = field(default_factory=dict)
    mapping_id_by_node_id: dict[int, str] = field(default_factory=dict)  # node_id -> i3dMapping id


@dataclass(slots=True)
class ExportIR:
    """Intermediate representation of the export scene graph.

    This is the central data structure for export, built during traversal and
    consumed by resolve/serialize phases.

    Core concepts:
    - Nodes stored by ID in `scene_nodes` dict
    - Hierarchy via `parent_id` (single source of truth)
    - Caches built on-demand for efficient queries
    - `node_order` preserves creation order for deterministic output

    Usage:
    - Builder: Creates nodes via `add_node()`
    - Resolve: Queries via `iter_nodes()`, `iter_roots()`, etc.
    - Serialize: Traverses via `emitted_child_ids()` which flattens emit=False nodes
    """

    scene_nodes: dict[int, SceneNode] = field(default_factory=dict)
    node_order: list[int] = field(default_factory=list)  # node ids in creation order (stable)
    index: IRIndex = field(default_factory=IRIndex)

    # Caches for fast hierarchy queries (built on-demand)
    _children_cache: dict[int | None, list[int]] = field(default_factory=dict, init=False)  # parent_id -> [child_ids]
    _roots_cache: list[int] = field(default_factory=list, init=False)  # cached root node ids

    def _index_node_blender_ref(self, node: SceneNode) -> None:
        """Index node by its Blender reference pointer (if any)."""
        if (ptr := node.source_ptr) is not None:
            self.index.node_id_by_blender_ptr.setdefault(ptr, []).append(node.id)

    def add_node(self, node: SceneNode, *, parent_id: int | None = None) -> None:
        """Add a pre-created SceneNode into the IR and attach it."""
        self.scene_nodes[node.id] = node
        self.node_order.append(node.id)
        self._index_node_blender_ref(node)
        # Override node's parent_id if parent_id parameter is provided
        if parent_id is not None:
            node.parent_id = parent_id
        self._roots_cache.clear()  # invalidate roots cache
        self._children_cache.clear()  # invalidate children cache

    def _ensure_hierarchy(self) -> None:
        """Build hierarchy caches from parent_id relationships (internal use only)."""
        if self._children_cache and self._roots_cache:
            return  # already built
        self._children_cache.clear()
        self._roots_cache.clear()
        for node in self.scene_nodes.values():
            self._children_cache.setdefault(node.id, [])
            if node.parent_id is None:
                self._roots_cache.append(node.id)
                # Also add roots to cache under None key for emitted_child_ids(None)
                self._children_cache.setdefault(None, []).append(node.id)
            elif node.parent_id in self.scene_nodes:
                self._children_cache.setdefault(node.parent_id, []).append(node.id)

    def iter_roots(self) -> Iterator[SceneNode]:
        """Iterate over root nodes (those with parent_id=None)."""
        self._ensure_hierarchy()
        for root_id in self._roots_cache:
            yield self.scene_nodes[root_id]

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
            if kind is not None and n.kind is not kind:
                continue
            if source_kind is not None and n.source_kind is not source_kind:
                continue
            if source_object_type is not None and n.source_object_type != source_object_type:
                continue
            if emitted_only and not n.emit:
                continue
            yield n

    def iter_objects(self, *, obj_type: str | None = None, emitted_only: bool = False) -> Iterator[SceneNode]:
        """Convenience method to iterate over OBJECT source nodes."""
        return self.iter_nodes(source_kind=SourceKind.OBJECT, source_object_type=obj_type, emitted_only=emitted_only)

    def children_ids(self, parent_id: int) -> list[int]:
        """Get direct child node IDs for a given parent (no emit filtering)."""
        self._ensure_hierarchy()
        return self._children_cache.get(parent_id, [])

    def emitted_child_ids(self, node_id: int | None) -> list[int]:
        """Get child node IDs that should be emitted, flattening emit=False nodes.

        This matches serializer behavior: nodes with emit=False are transparent,
        and their emitted children appear at the parent's level instead.

        Args:
            node_id: Parent node ID, or None for roots

        Returns:
            List of node IDs that should be emitted as children
        """
        self._ensure_hierarchy()
        children = self._children_cache.get(node_id, [])
        result: list[int] = []
        for cid in children:
            if self.scene_nodes[cid].emit:
                result.append(cid)
            else:
                # Flatten: include this node's emitted children instead
                result.extend(self.emitted_child_ids(cid))
        return result

    def attach(self, node_id: int, parent_id: int | None) -> None:
        """Change a node's parent (reparent operation).

        This is the primary method for modifying hierarchy during resolve phases.

        Common use cases:
        - Reparenting bones with "Child Of" constraints to their constraint targets
        - Collapsing armatures (bones become children of armature's parent)
        - Restructuring hierarchy based on export settings

        Args:
            node_id: Node to reparent
            parent_id: New parent ID, or None to make it a root node
        """
        n = self.scene_nodes[node_id]
        if n.parent_id == parent_id:
            return  # already attached correctly
        n.parent_id = parent_id
        self._roots_cache.clear()
        self._children_cache.clear()
