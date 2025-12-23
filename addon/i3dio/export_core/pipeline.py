# i3dio/export_core/pipeline.py
from __future__ import annotations

import bpy

from . import traverse
from .ctx import ExportContext
from .serialize.write_i3d import write_i3d


def run_export(
    ctx: ExportContext,
    *,
    operator,
    context: bpy.types.Context,
) -> None:
    """
    Minimal pipeline:
      1) traverse -> build IR
      2) serialize -> write i3d
    """
    # Handle case when export is triggered from a "export collection"
    source_collection = None
    if getattr(operator, "collection", None):
        source_collection = bpy.data.collections.get(operator.collection)
        if not source_collection:
            operator.report({"ERROR"}, f"Collection {operator.collection!r} was not found")
            raise RuntimeError(f"Collection {operator.collection!r} not found")

    if source_collection:
        traverse.add_collection(ctx, source_collection, parent_id=None)
    else:
        match operator.selection:
            case "ALL":
                traverse.add_collection(ctx, context.scene.collection, parent_id=None)
            case "ACTIVE_COLLECTION":
                traverse.add_collection(ctx, context.view_layer.active_layer_collection.collection, parent_id=None)
            case "ACTIVE_OBJECT":
                if context.active_object is None:
                    operator.report({"ERROR"}, "No active object for export")
                    raise RuntimeError("No active object for export")
                traverse.build_from_roots(ctx, [context.active_object])
            case "SELECTED_OBJECTS":
                if not context.selected_objects:
                    operator.report({"ERROR"}, "No objects selected for export")
                    raise RuntimeError("No objects selected for export")
                if ctx.settings.get("selection_traverse_children", False):
                    traverse.build_from_roots(ctx, context.selected_objects)
                else:
                    traverse.build_selected_only(ctx, context.selected_objects)
            case _:
                operator.report({"ERROR"}, f"Unknown selection mode: {operator.selection!r}")
                raise RuntimeError(f"Unknown selection mode: {operator.selection!r}")

    write_i3d(ctx, ctx.filepath)
