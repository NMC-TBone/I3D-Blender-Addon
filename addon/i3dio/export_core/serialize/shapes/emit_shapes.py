# i3dio/export_core/serialize/shapes/emit_shapes.py
from __future__ import annotations

from ...ctx import ExportContext
from .indexed_triangle_set import emit_indexed_triangle_set


def emit_shapes(ctx: ExportContext, shapes_elem):
    for shape_id in sorted(ctx.shapes.built_its):
        built = ctx.shapes.built_its[shape_id]
        emit_indexed_triangle_set(ctx, shapes_elem, built)
