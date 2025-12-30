# i3dio/export_core/shapes/resolve/assemble.py
from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from ...ir import NodeKind, SceneNode

if TYPE_CHECKING:
    from ...ctx import ExportContext


def resolve_shapes_build(ctx: "ExportContext") -> None:
    """
    Build built geometry for referenced shapes (cached in ctx.shapes.built_by_id).

    Also writes materialIds onto Scene nodes referencing each shapeId.
    """
    rep = ctx.section("shapes")

    # Map shapeId -> [node]
    shape_nodes_by_id: dict[int, list[SceneNode]] = defaultdict(list)

    for node in ctx.ir.scene_nodes.values():
        if node.kind != NodeKind.SHAPE or not node.emit:
            continue
        sid = node.xml.node.get("shapeId")
        if isinstance(sid, int):
            shape_nodes_by_id[sid].append(node)

    if not shape_nodes_by_id:
        rep.debug("No shape nodes with shapeId; skipping build")
        return
    rep.debug("Building %d referenced shapes", len(shape_nodes_by_id))

    # Build only the shapes that are referenced by Scene nodes
    for shape_id, nodes in shape_nodes_by_id.items():
        built = ctx.shapes.get_built(shape_id)
        if built is None:
            entry = ctx.shapes.get_entry(shape_id)
            rep.warning("Shape %r produced no valid mesh; exporting as TransformGroup", entry.name)
            for n in nodes:
                n.kind = NodeKind.TRANSFORM_GROUP
                n.xml.node.pop("shapeId", None)
                n.xml.node.pop("materialIds", None)
            continue

        if built.material_ids:
            mat_ids_str = ",".join(str(mid) for mid in built.material_ids)
            for n in nodes:
                n.xml.node["materialIds"] = mat_ids_str
        else:  # if something previously wrote it for some reason, ensure it's gone
            for n in nodes:
                n.xml.node.pop("materialIds", None)
