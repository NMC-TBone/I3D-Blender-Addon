from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

from .node import NodeKind, SceneNode, SourceKind, UserAttributeEntry


@dataclass(slots=True)
class IRIndex:
    """Lookup tables built during traversal/resolve.
    These are internal pipeline indexes, not values intended for direct XML emission.
    """

    node_ids_by_blender_ptr: dict[int, list[int]] = field(default_factory=dict)
    mapping_id_by_node_id: dict[int, str] = field(default_factory=dict)
    user_attributes_by_node_id: dict[int, list[UserAttributeEntry]] = field(default_factory=dict)


@dataclass(slots=True)
class ExportIR:
    """Intermediate representation of the export scene graph."""

    scene_nodes: dict[int, SceneNode] = field(default_factory=dict)
    node_order: list[int] = field(default_factory=list)
    index: IRIndex = field(default_factory=IRIndex)

    _children_by_parent_cache: dict[int | None, list[int]] | None = None

    def _invalidate_children_cache(self) -> None:
        self._children_by_parent_cache = None

    def _index_node_blender_ptr(self, node: SceneNode) -> None:
        """Index the node by its Blender data-block pointer for quick lookup during resolve."""
        if node.source.blender_ptr is not None:
            self.index.node_ids_by_blender_ptr.setdefault(node.source.blender_ptr, []).append(node.id)

    def _children_by_parent(self) -> dict[int | None, list[int]]:
        """Return cached parent-child relationships, keyed by parent node ID."""
        if self._children_by_parent_cache is not None:
            return self._children_by_parent_cache

        children: dict[int | None, list[int]] = {None: []}

        for node_id in self.node_order:
            children[node_id] = []

        for node_id in self.node_order:
            node = self.scene_nodes[node_id]
            parent_id = node.parent_id

            if parent_id is None or parent_id == node_id or parent_id not in self.scene_nodes:
                children[None].append(node_id)
            else:
                children[parent_id].append(node_id)

        self._children_by_parent_cache = children
        return children

    def add_node(self, node: SceneNode) -> None:
        """Add a node to the IR."""
        if node.id in self.scene_nodes:
            raise RuntimeError(f"Node ID {node.id} already exists in IR")

        self.scene_nodes[node.id] = node
        self.node_order.append(node.id)
        self._index_node_blender_ptr(node)
        self._invalidate_children_cache()

    def attach(self, node_id: int, parent_id: int | None) -> None:
        """Reparent a node. Missing nodes fail fast; self/cyclic reparenting is ignored."""
        if node_id not in self.scene_nodes:
            raise KeyError(f"Node ID {node_id} not found in IR")

        if parent_id == node_id:
            return

        if parent_id is not None and parent_id not in self.scene_nodes:
            raise KeyError(f"Parent node ID {parent_id} not found in IR")

        current_parent_id = parent_id
        while current_parent_id is not None:
            if current_parent_id == node_id:
                return
            if (parent := self.scene_nodes.get(current_parent_id)) is None:
                break

            current_parent_id = parent.parent_id

        node = self.scene_nodes[node_id]
        if node.parent_id == parent_id:
            return

        node.parent_id = parent_id
        self._invalidate_children_cache()

    def iter_roots(self) -> Iterator[SceneNode]:
        """Iterate root nodes (nodes with no parent)."""
        return (self.scene_nodes[node_id] for node_id in self._children_by_parent()[None])

    def iter_nodes(
        self,
        *,
        kind: NodeKind | None = None,
        source_kind: SourceKind | None = None,
        source_object_type: str | None = None,
        emitted_only: bool = False,
    ) -> Iterator[SceneNode]:
        """Iterate nodes in node_order order, optionally filtering by kind/source and/or emitted status."""
        for node_id in self.node_order:
            node = self.scene_nodes[node_id]
            if kind is not None and node.kind is not kind:
                continue
            if source_kind is not None and node.source.kind is not source_kind:
                continue
            object_type = node.source_object_type_override or node.source.object_type
            if source_object_type is not None and object_type != source_object_type:
                continue
            if emitted_only and not node.emit:
                continue

            yield node

    def children_ids(self, parent_id: int) -> tuple[int, ...]:
        """Return the IDs of the children of the given parent node."""
        return tuple(self._children_by_parent().get(parent_id, ()))

    def emitted_child_ids(self, node_id: int | None) -> list[int]:
        """Return emitted children, flattening non-emitted grouping nodes."""
        result: list[int] = []
        for child_id in self._children_by_parent().get(node_id, ()):
            child = self.scene_nodes[child_id]
            if child.emit:
                result.append(child_id)
            else:
                result.extend(self.emitted_child_ids(child_id))

        return result

    def validate_basic(self, *, require_resolved: bool = False) -> None:
        """Validate cheap IR invariants. This is not a full consistency check, but can catch common mistakes early."""
        seen: set[int] = set()

        for node_id in self.node_order:
            if node_id in seen:
                raise RuntimeError(f"Node ID {node_id} appears multiple times in node_order")
            seen.add(node_id)

            if node_id not in self.scene_nodes:
                raise RuntimeError(f"Node ID {node_id} exists in node_order but not scene_nodes")

        missing_from_order = set(self.scene_nodes) - seen
        if missing_from_order:
            raise RuntimeError(f"Nodes missing from node_order: {sorted(missing_from_order)}")

        for node in self.scene_nodes.values():
            if node.parent_id is not None and node.parent_id not in self.scene_nodes:
                raise RuntimeError(f"Node {node.id} has missing parent {node.parent_id}")

            if node.parent_id == node.id:
                raise RuntimeError(f"Node {node.id} cannot be its own parent")

            if require_resolved and node.kind is NodeKind.UNRESOLVED:
                raise RuntimeError(f"Node {node.id} is still unresolved")
