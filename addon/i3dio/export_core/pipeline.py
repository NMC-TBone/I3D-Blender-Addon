# i3dio/export_core/pipeline.py
from __future__ import annotations

import bpy

from . import traverse
from .ctx import ExportContext
from .resolve.mappings import finalize_i3d_mappings
from .resolve.names import finalize_names
from .serialize.emit_i3d_mappings import emit_i3d_mappings
from .serialize.write_i3d import write_i3d


def run_export(ctx: ExportContext, *, operator, context: bpy.types.Context) -> None:
    """Run the export pipeline to export the Blender scene to an I3D file."""
    _build_ir(ctx, operator=operator, context=context)

    # resolve/fixups (future)
    # resolve_constraints(ctx)
    # resolve_armatures(ctx)
    # resolve_instances(ctx)

    finalize_names(ctx)
    finalize_i3d_mappings(ctx)

    write_i3d(ctx)
    emit_i3d_mappings(ctx)


def _build_ir(ctx: ExportContext, *, operator, context: bpy.types.Context) -> None:
    reporter = ctx.reporter(operator=operator)
    source_collection = None
    if getattr(operator, "collection", None):
        source_collection = bpy.data.collections.get(operator.collection)
        if not source_collection:
            reporter.fail(f"Collection {operator.collection!r} was not found")

    if source_collection:
        traverse.add_collection(ctx, source_collection, parent_id=None)
        return

    match operator.selection:
        case "ALL":
            traverse.add_collection(ctx, context.scene.collection, parent_id=None)
        case "ACTIVE_COLLECTION":
            traverse.add_collection(ctx, context.view_layer.active_layer_collection.collection, parent_id=None)
        case "ACTIVE_OBJECT":
            if context.active_object is None:
                reporter.fail("No active object for export")
            traverse.build_from_roots(ctx, [context.active_object])
        case "SELECTED_OBJECTS":
            if not context.selected_objects:
                reporter.fail("No objects selected for export")
            if ctx.settings.get("selection_traverse_children", False):
                traverse.build_from_roots(ctx, context.selected_objects)
            else:
                traverse.build_selected_only(ctx, context.selected_objects)
        case _:
            reporter.fail(f"Unknown selection mode: {operator.selection!r}")
