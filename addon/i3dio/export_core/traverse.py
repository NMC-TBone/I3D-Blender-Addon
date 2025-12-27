from __future__ import annotations

from typing import Iterable

import bpy

from ..utility import BlenderObject, sort_blender_objects_by_outliner_ordering
from .ctx import ExportContext
from .ir import NodeKind


def _is_excluded(obj: bpy.types.Object) -> bool:
    try:
        return obj.i3d_attributes.exclude_from_export
    except Exception:
        return False


def add_object_node(ctx: ExportContext, obj: bpy.types.Object, parent_id: int | None) -> int | None:
    """Create the node for an object (no recursion). Returns node_id or None if skipped."""
    if _is_excluded(obj):
        ctx.object_reporter(obj, "traverse").debug("Excluded from export (skip subtree)")
        return None

    return ctx.builder.add_scene_node(
        kind=NodeKind.UNRESOLVED,
        blender_ref=obj,
        parent_id=parent_id,
    )


def build_from_collection(
    ctx: ExportContext, collection: bpy.types.Collection, parent_id: int | None, *, force_new_nodes: bool = False
) -> None:
    """
    Export a collection:
      - child collections first (outliner-like)
      - then *root* objects in the collection (obj.parent is None)

    Parenting wins placement: non-root objects are exported via their object-parent chain, not
    because they "live" in a collection.
    """
    for child_coll in collection.children.values():
        add_collection(ctx, child_coll, parent_id, force_new_nodes=force_new_nodes)

    roots = [obj for obj in collection.objects if obj.parent is None]
    for obj in sort_blender_objects_by_outliner_ordering(roots):
        add_object(ctx, obj, parent_id, force_new_nodes=force_new_nodes)


def add_collection(
    ctx: ExportContext,
    collection: bpy.types.Collection,
    parent_id: int | None,
    *,
    force_new_nodes: bool = False,
    emit_self: bool = True,
) -> None:
    """
    Add a collection and its contents.

    If keep_collections_as_transformgroups: create a TransformGroup node for the collection itself.
    Otherwise: the collection is "transparent" and its children attach to the given parent_id.

    force_new_nodes is used for collection instance expansion (Empty.instance_collection) so that
    every encountered element becomes a fresh node in the export tree. (Also useful as future
    "instance context" for transform resolution.)

    emit_self controls whether to create a node for the collection itself (e.g. we don't want Scene Collection with ALL)
    """
    if not emit_self or not ctx.settings.get("keep_collections_as_transformgroups", False):
        build_from_collection(ctx, collection, parent_id, force_new_nodes=force_new_nodes)
        return

    node_id = ctx.builder.add_scene_node(
        kind=NodeKind.TRANSFORM_GROUP,
        blender_ref=collection,
        parent_id=parent_id,
    )
    build_from_collection(ctx, collection, node_id, force_new_nodes=force_new_nodes)


def add_object(
    ctx: ExportContext,
    obj: bpy.types.Object,
    parent_id: int | None,
    *,
    force_new_nodes: bool = False,
) -> None:
    """
    Add an object node, then recurse into its children.

    If the object is a collection instance (Empty.instance_collection), expand the referenced
    collection under this object. Expansion uses force_new_nodes=True to create fresh nodes per placement.
    """
    if (node_id := add_object_node(ctx, obj, parent_id)) is None:
        return
    if obj.instance_collection is not None:
        ctx.object_reporter(obj, "traverse").debug("Expanding instance_collection %r", obj.instance_collection.name)
        add_collection(ctx, obj.instance_collection, node_id, force_new_nodes=True)
        return
    for child in sort_blender_objects_by_outliner_ordering(obj.children):
        add_object(ctx, child, node_id, force_new_nodes=force_new_nodes)


def build_from_roots(ctx: ExportContext, roots: Iterable[BlenderObject]) -> None:
    """Entry point for a set of root items (Objects and/or Collections)."""
    for item in roots:
        if isinstance(item, bpy.types.Collection):
            add_collection(ctx, item, parent_id=None)
        else:
            add_object(ctx, item, parent_id=None)


def build_selected_only(ctx: ExportContext, selected_objs: list[bpy.types.Object]) -> None:
    """Selected-only mode without child traversal. Keeps the "nearest selected parent" rule from the old exporter."""
    selection_set = set(selected_objs)

    # Build a parent map: obj -> nearest parent within selection
    parent_map: dict[bpy.types.Object, bpy.types.Object] = {}
    roots: list[bpy.types.Object] = []

    for obj in selected_objs:
        parent = obj.parent
        while parent and parent not in selection_set:
            parent = parent.parent
        if parent and parent in selection_set:
            parent_map[obj] = parent
        else:
            roots.append(obj)

    # Export roots first (outliner ordering)
    roots_sorted = sort_blender_objects_by_outliner_ordering(roots)

    # First pass: create nodes for all selected objects in a stable order.
    # We can just export roots, but we still need the non-traversal “selected children” too.
    # So we do a simple two-step: create node for each selected object when reached.
    created: dict[bpy.types.Object, int | None] = {}

    def ensure_node(obj: bpy.types.Object) -> int | None:
        if obj in created:
            return created[obj]
        pid: int | None = None
        if obj in parent_map:
            pid = ensure_node(parent_map[obj])
            if pid is None:
                # nearest selected parent exists but got skipped (excluded) -> skip child too
                created[obj] = None
                return None
        node_id = add_object_node(ctx, obj, pid)
        created[obj] = node_id
        return node_id

    for obj in roots_sorted:
        ensure_node(obj)

    # Also ensure any non-root selected objects get created (if selection list isn't sorted by hierarchy)
    for obj in sort_blender_objects_by_outliner_ordering(selected_objs):
        ensure_node(obj)
