# i3dio/export_core/shapes/resolve/assemble.py
from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from ...ir import NodeKind, SceneNode, clear_shape_binding, to_transform_group
from ...model.its import MaterialKeyKind
from ..material_resolve import resolve_slots

if TYPE_CHECKING:
    from ...ctx import ExportContext


def _index_emitted_shape_nodes_by_id(ctx: "ExportContext") -> dict[int, list[SceneNode]]:
    shape_nodes_by_id: dict[int, list[SceneNode]] = defaultdict(list)
    for node in ctx.ir.iter_nodes(kind=NodeKind.SHAPE, emitted_only=True):
        sid = node.shape.shape_id
        if sid is not None:
            shape_nodes_by_id[sid].append(node)
    return shape_nodes_by_id


def resolve_shapes_build(ctx: "ExportContext") -> dict[int, list[SceneNode]]:
    """
    Build/validate geometry for referenced shapes.

    Returns:
        shape_nodes_by_id for shapes that built successfully.

    Side-effects:
        - Invalid shapes are converted to TransformGroup (nodes mutated).
        - Built geometry is cached in ctx.shapes.built_by_id via ctx.shapes.get_built().
    """
    rep = ctx.reporter("shapes")

    # Map shapeId -> [node]
    shape_nodes_by_id = _index_emitted_shape_nodes_by_id(ctx)
    if not shape_nodes_by_id:
        rep.debug("No shape nodes with shapeId; skipping build")
        return {}

    rep.debug("Building %d referenced shapes", len(shape_nodes_by_id))

    valid: dict[int, list[SceneNode]] = {}
    for shape_id, nodes in shape_nodes_by_id.items():
        built = ctx.shapes.get_built(shape_id)
        if built is None:
            entry = ctx.shapes.get_entry(shape_id)
            rep.warning("Shape %r produced no valid mesh; exporting as TransformGroup", entry.name)
            for n in nodes:
                to_transform_group(n)
            continue

        rep.debug(
            "Shape id=%d built: vertices=%d triangles=%d materials=%d",
            shape_id,
            built.vertex_count,
            built.triangle_count,
            len(built.material_ids),
        )
        valid[shape_id] = nodes

    return valid


def finalize_shape_material_ids(ctx: "ExportContext", shape_nodes_by_id: dict[int, list[SceneNode]]) -> None:
    """Finalize materialIds for Scene nodes.

    Expects:
        shape_nodes_by_id contains only shapes that built successfully.

    Centralizes:
      - clearing stale shape bindings on non-shape nodes
      - writing materialIds on shape nodes (per-node for NORMAL, shared for merge modes)
    """
    rep = ctx.reporter("shapes")

    # Safety invariant: non-shape nodes must not carry shape bindings
    for node in ctx.ir.iter_nodes(emitted_only=True):
        if node.kind is not NodeKind.SHAPE:
            clear_shape_binding(node)

    if not shape_nodes_by_id:
        rep.debug("No valid shape nodes; skipping materialIds finalize")
        return

    default_id = ctx.materials.get_default_id()
    wrote_nodes = 0
    for shape_id, nodes in shape_nodes_by_id.items():
        built = ctx.shapes.get_built(shape_id)
        if built is None or not built.material_ids:
            for n in nodes:
                n.shape.material_ids = None
            continue

        if built.material_kind == MaterialKeyKind.MATERIAL_ID:
            # Merge shapes: subsets already keyed by resolved global material IDs.
            for n in nodes:
                n.shape.material_ids = built.material_ids
                wrote_nodes += 1
            continue

        # NORMAL shapes: built.material_ids stores material slot indices in subset order.
        for n in nodes:
            obj = n.obj
            slot_materials = (
                [s.material for s in obj.material_slots] if obj.material_slots else list(obj.data.materials)
            )
            res = resolve_slots(ctx, slot_materials=slot_materials)
            fallback_id = res.fallback_id if res.fallback_id is not None else default_id

            n.shape.material_ids = [
                int(res.slot_ids[slot_idx]) if 0 <= slot_idx < len(slot_materials) else int(fallback_id)
                for slot_idx in built.material_ids
            ]
            wrote_nodes += 1

    rep.debug("Finalized materialIds for %d nodes", wrote_nodes)
