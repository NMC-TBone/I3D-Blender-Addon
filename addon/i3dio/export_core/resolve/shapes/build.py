# i3dio/export_core/resolve/shapes/build.py
from __future__ import annotations

from collections import defaultdict

from ...ctx import ExportContext
from ...data.shapes.types import ShapeMode
from ...geom.its.build import build_indexed_triangle_set_normal
from ...ir import NodeKind, SceneNode


def resolve_shapes_build(ctx: ExportContext) -> None:
    """
    Build BuiltITS for referenced shapes and cache them in ctx.shapes.built_its.

    Also writes materialIds onto Scene nodes that reference each shapeId.
    """
    rep = ctx.section("shapes")

    # Map shapeId -> [node]
    nodes_by_shape: dict[int, list[SceneNode]] = defaultdict(list)

    for node in ctx.ir.scene_nodes.values():
        if node.kind != NodeKind.SHAPE or not node.emit:
            continue
        sid = node.xml.node.get("shapeId")
        if isinstance(sid, int):
            nodes_by_shape[sid].append(node)

    if not nodes_by_shape:
        rep.debug("No shape nodes with shapeId; skipping build")
        return

    # Build only the shapes that are referenced by Scene nodes
    for shape_id, nodes in nodes_by_shape.items():
        if shape_id in ctx.shapes.built_its:
            built = ctx.shapes.built_its[shape_id]
        else:
            entry = ctx.shapes.get_entry(shape_id)

            # For now only NORMAL; later dispatch by entry.mode
            # match entry.mode:
            #   case ShapeMode.NORMAL: built = build_indexed_triangle_set_normal(ctx, entry)
            #   case ShapeMode.MERGE_CHILDREN_GENERIC: ...
            #   case ShapeMode.MERGE_GROUP: ...
            built = build_indexed_triangle_set_normal(ctx, entry)

            ctx.shapes.built_its[shape_id] = built

        # Write materialIds onto all nodes referencing this shape.
        # Only write if there are subsets/materials (avoid empty attribute noise).
        if built.material_ids:
            mat_ids_str = " ".join(str(mid) for mid in built.material_ids)
            for n in nodes:
                n.xml.node["materialIds"] = mat_ids_str
