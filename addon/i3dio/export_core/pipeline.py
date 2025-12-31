# i3dio/export_core/pipeline.py
from __future__ import annotations

from typing import TYPE_CHECKING

import bpy

from . import traverse
from .resolve import resolve_all
from .serialize.emit_i3d_mappings import emit_i3d_mappings
from .serialize.write_i3d import write_i3d

if TYPE_CHECKING:
    from .ctx import ExportContext


def run_export(ctx: ExportContext, *, context: bpy.types.Context) -> None:
    """Run the export pipeline to export the Blender scene to an I3D file."""
    rep = ctx.section("pipeline")
    rep.debug("Traverse start")
    _build_ir(ctx, context=context)
    rep.debug("Traverse done (nodes=%d roots=%d)", len(ctx.ir.scene_nodes), len(ctx.ir.roots))

    rep.debug("Resolve start")
    resolve_all(ctx)
    rep.debug("Resolve done")

    rep.debug("Serialization start")
    write_i3d(ctx)
    rep.debug("Serialization done")

    rep.debug("i3dMappings export start")
    emit_i3d_mappings(ctx)
    rep.debug("i3dMappings export done")


def _build_ir(ctx: ExportContext, *, context: bpy.types.Context) -> None:
    op = ctx.operator
    reporter = ctx.section("pipeline")
    source_collection = None
    if getattr(op, "collection", None):
        source_collection = bpy.data.collections.get(op.collection)
        if not source_collection:
            reporter.fail("Collection %r was not found", op.collection)

    if source_collection:
        reporter.info("Exporting from collection export %r", source_collection.name)
        traverse.add_collection(ctx, source_collection, parent_id=None)
        return

    match op.selection:
        case "ALL":
            reporter.info("Exporting entire scene")
            traverse.add_collection(ctx, context.scene.collection, parent_id=None, emit_self=False)
        case "ACTIVE_COLLECTION":
            reporter.info("Exporting active collection %r", context.view_layer.active_layer_collection.collection.name)
            traverse.add_collection(ctx, context.view_layer.active_layer_collection.collection, parent_id=None)
        case "ACTIVE_OBJECT":
            if context.active_object is None:
                reporter.fail("No active object for export")
            reporter.info("Exporting active object %r", context.active_object.name)
            traverse.build_from_roots(ctx, [context.active_object])
        case "SELECTED_OBJECTS":
            if not context.selected_objects:
                reporter.fail("No objects selected for export")
            reporter.info("Exporting %d selected objects", len(context.selected_objects))
            if ctx.settings.get("selection_traverse_children", False):
                traverse.build_from_roots(ctx, context.selected_objects)
            else:
                traverse.build_selected_only(ctx, context.selected_objects)
        case _:
            reporter.fail("Unknown selection mode: %r", op.selection)
