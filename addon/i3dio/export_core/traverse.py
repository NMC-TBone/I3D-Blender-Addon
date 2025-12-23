from __future__ import annotations

from typing import Iterable

import bpy

from ..utility import BlenderObject, sort_blender_objects_by_outliner_ordering
from .builder import AUTO_DEDUP
from .ctx import ExportContext
from .ir import NodeKind


def build_from_collection(
    ctx: ExportContext, collection: bpy.types.Collection, parent_id: int | None, *, instanced: bool = False
) -> None:
    """
    Export a collection's hierarchy:
      - child collections first (outliner-like)
      - then root objects in the collection (obj.parent is None)
    """
    # Collections show first in outliner
    for child_coll in collection.children.values():
        add_collection(ctx, child_coll, parent_id, instanced=instanced)

    # Then objects contained in the collection.
    # Important: collection.objects contains *all* objects, including children of other objects,
    # so only export object roots (parent is None) to avoid duplicates.
    roots = [obj for obj in collection.objects if obj.parent is None]
    for obj in sort_blender_objects_by_outliner_ordering(roots):
        add_object(ctx, obj, parent_id)


def add_collection(
    ctx: ExportContext, collection: bpy.types.Collection, parent_id: int | None, *, instanced: bool = False
) -> None:
    """
    Add a collection and its contents.
    If keep_collections_as_transformgroups: create a TransformGroup node for the collection itself.
    Otherwise: collection is "transparent" and its children attach to the given parent_id.
    """
    if ctx.settings.get("keep_collections_as_transformgroups", False):
        # For normal collection traversal, dedup is fine.
        # For instanced collections, you'd typically want duplicates (instanced=True).
        node_id = ctx.builder.add_scene_node(
            kind=NodeKind.TRANSFORM_GROUP,
            blender_ref=collection,
            parent_id=parent_id,
            dedup_key=None if instanced else AUTO_DEDUP,
        )
        build_from_collection(ctx, collection, node_id, instanced=instanced)
    else:
        build_from_collection(ctx, collection, parent_id, instanced=instanced)


def add_object(ctx: ExportContext, obj: bpy.types.Object, parent_id: int | None, *, instanced: bool = False) -> None:
    """
    Add an object as a TransformGroup, then recurse into its children.
    Instanced objects (coming from EMPTY.instance_collection expansion) should not dedup.
    """
    # Skip object + its subtree
    try:
        if obj.i3d_attributes.exclude_from_export:
            ctx.obj_logger(obj.name).info("Excluded from export (skip subtree)")
            return
    except Exception:
        pass

    # For now: everything becomes a TransformGroup node in IR.
    # later: this is where you'd branch by obj.type (MESH -> Shape, etc)
    node_id = ctx.builder.add_scene_node(
        kind=NodeKind.TRANSFORM_GROUP,
        blender_ref=obj,
        parent_id=parent_id,
        dedup_key=None if instanced else AUTO_DEDUP,
    )

    # Collection instances: treat instance_collection contents as children of this object.
    # These children should be created as *fresh nodes* (instanced=True), not blocked by dedup_map dedup.
    if obj.instance_collection is not None:
        add_collection(ctx, obj.instance_collection, node_id, instanced=True)
        return

    # Normal object children
    for child in sort_blender_objects_by_outliner_ordering(obj.children):
        add_object(ctx, child, node_id)


def build_from_roots(ctx: ExportContext, roots: Iterable[BlenderObject]) -> None:
    """
    Entry point for a set of "root items" which can be Objects and/or Collections.
    """
    for item in roots:
        if isinstance(item, bpy.types.Collection):
            add_collection(ctx, item, parent_id=None)
        else:
            add_object(ctx, item, parent_id=None)


def build_selected_only(ctx: ExportContext, selected_objs: list[bpy.types.Object]) -> None:
    """
    Selected-only mode without child traversal.
    Keeps the "nearest selected parent" rule from your old exporter.
    """
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
    created: dict[bpy.types.Object, int] = {}

    def ensure_node(obj: bpy.types.Object) -> int:
        if obj in created:
            return created[obj]
        pid = None
        if obj in parent_map:
            pid = ensure_node(parent_map[obj])
        node_id = ctx.builder.add_scene_node(
            kind=NodeKind.TRANSFORM_GROUP,
            blender_ref=obj,
            parent_id=pid,
            dedup_key=AUTO_DEDUP,
        )
        created[obj] = node_id
        return node_id

    for obj in roots_sorted:
        ensure_node(obj)

    # Also ensure any non-root selected objects get created (if selection list isn't sorted by hierarchy)
    for obj in sort_blender_objects_by_outliner_ordering(selected_objs):
        ensure_node(obj)
