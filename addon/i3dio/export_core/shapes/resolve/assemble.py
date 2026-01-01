# i3dio/export_core/shapes/resolve/assemble.py
from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

import bpy

from ...ir import NodeKind, SceneNode
from ...ir_node_helpers import clear_shape_binding, to_transform_group
from ..its import MaterialKeyKind
from ..its.material_resolve import resolve_slots

if TYPE_CHECKING:
    from ...ctx import ExportContext


def _get_shape_id(node: SceneNode) -> int | None:
    return node.shape_id


def _index_emitted_shape_nodes_by_id(ctx: "ExportContext") -> dict[int, list[SceneNode]]:
    shape_nodes_by_id: dict[int, list[SceneNode]] = defaultdict(list)
    for node in ctx.ir.iter_nodes(kind=NodeKind.SHAPE, emitted_only=True):
        sid = _get_shape_id(node)
        if sid is not None:
            shape_nodes_by_id[sid].append(node)
    return shape_nodes_by_id


def resolve_shapes_build(ctx: "ExportContext") -> None:
    """
    Build built geometry for referenced shapes (cached in ctx.shapes.built_by_id).

    Only builds/validates shape geometry and converts invalid shapes to TransformGroup.

    materialIds are finalized in a dedicated pass: finalize_shape_material_ids().
    """
    rep = ctx.section("shapes")

    # Map shapeId -> [node]
    shape_nodes_by_id = _index_emitted_shape_nodes_by_id(ctx)

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
                to_transform_group(n)
            continue

        rep.debug(
            "Shape id=%d built: vertices=%d triangles=%d materials=%d",
            shape_id,
            built.vertex_count,
            built.triangle_count,
            len(built.material_ids),
        )


def finalize_shape_material_ids(ctx: "ExportContext") -> None:
    """Finalize materialIds for Scene nodes.

    Centralizes:
    - clearing shape bindings on non-shape nodes
    - writing materialIds on shape nodes (per-node for NORMAL, shared for merge modes)

    This is intentionally a late pass so invalid shapes never receive materialIds.
    """
    rep = ctx.section("shapes")

    # First: clear any stale shape bindings on non-shape nodes.
    for node in ctx.ir.iter_nodes(emitted_only=True):
        if node.kind != NodeKind.SHAPE:
            clear_shape_binding(node)

    # Map shapeId -> [node]
    shape_nodes_by_id = _index_emitted_shape_nodes_by_id(ctx)

    if not shape_nodes_by_id:
        rep.debug("No shape nodes with shapeId; skipping materialIds finalize")
        return

    wrote_nodes = 0
    for shape_id, nodes in shape_nodes_by_id.items():
        built = ctx.shapes.get_built(shape_id)
        if built is None or not built.material_ids:
            for n in nodes:
                n.material_ids = None
            continue

        if built.material_kind == MaterialKeyKind.MATERIAL_ID:
            # Merge shapes: subsets already keyed by resolved global material IDs.
            for n in nodes:
                n.material_ids = built.material_ids
                wrote_nodes += 1
            continue

        # NORMAL shapes: built.material_ids stores material slot indices in subset order.
        for n in nodes:
            ref = n.blender_ref
            if not isinstance(ref, bpy.types.Object) or not isinstance(ref.data, bpy.types.Mesh):
                n.material_ids = None
                continue

            slot_materials = (
                [s.material for s in ref.material_slots] if ref.material_slots else list(ref.data.materials)
            )
            res = resolve_slots(ctx, slot_materials=slot_materials)
            default_id = ctx.materials.get_default_id()
            fallback_id = res.fallback_id if res.fallback_id is not None else default_id

            out_ids: list[int] = []
            for slot_idx in built.material_ids:
                if 0 <= slot_idx < len(slot_materials):
                    out_ids.append(int(res.slot_ids[slot_idx]))
                else:
                    out_ids.append(int(fallback_id))

            n.material_ids = out_ids
            wrote_nodes += 1

    rep.debug("Finalized materialIds for %d nodes", wrote_nodes)
