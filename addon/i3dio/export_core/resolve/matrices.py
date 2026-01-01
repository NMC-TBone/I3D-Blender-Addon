from __future__ import annotations

from typing import TYPE_CHECKING

import bpy
import mathutils

from ..ir import NodeKind, SceneNode

if TYPE_CHECKING:
    from ..ctx import ExportContext


def _node_world_blender(node: SceneNode) -> mathutils.Matrix | None:
    """World matrix in Blender space for this node, or None if node has no transform."""
    if isinstance(node.blender_ref, bpy.types.Object):
        return node.blender_ref.matrix_world.copy()

    return None


def _node_world_export(ctx: "ExportContext", node: SceneNode) -> mathutils.Matrix | None:
    """World matrix in EXPORT space."""
    w_bl = _node_world_blender(node)
    if w_bl is None:
        return None

    if node.kind in {NodeKind.CAMERA, NodeKind.LIGHT}:
        return ctx.to_export_forward(w_bl)

    return ctx.to_export(w_bl)


def _local_matrix_export(ctx: "ExportContext", node: SceneNode, parent: SceneNode | None) -> mathutils.Matrix | None:
    """Local matrix in EXPORT space for this node, or None if node has no transform."""
    world_e = _node_world_export(ctx, node)
    if world_e is None:
        return None

    if parent is None:
        local_e = world_e
    else:
        parent_world_e = _node_world_export(ctx, parent) or mathutils.Matrix.Identity(4)

        # fast-path: only safe when both are real objects and exporter parent == Blender parent
        ref = node.blender_ref
        parent_ref = parent.blender_ref if parent else None
        if isinstance(ref, bpy.types.Object) and isinstance(parent_ref, bpy.types.Object) and ref.parent is parent_ref:
            local_e = ctx.to_export(ref.matrix_local.copy())
        else:
            local_e = parent_world_e.inverted_safe() @ world_e

    # If parent is a camera/light, we need to adjust for the flipped z-axis in GE space
    if parent and parent.kind in {NodeKind.CAMERA, NodeKind.LIGHT}:
        local_e = ctx.conversion_matrix_inv @ local_e
        ctx.node_reporter(node, "matrices").debug(
            "Adjusted local matrix due to parent %s axis handling", parent.kind.name
        )

    return local_e


def resolve_matrices(ctx: "ExportContext") -> None:
    """Compute local EXPORT-space matrices for all nodes and store them on the node."""
    rep = ctx.section("matrices")
    rep.debug("Matrix resolve start")

    def rec(node_id: int, parent: SceneNode | None) -> None:
        node = ctx.ir.scene_nodes[node_id]
        node.matrix_local_export = _local_matrix_export(ctx, node, parent)
        for cid in node.children:
            rec(cid, node)

    for rid in ctx.ir.roots:
        rec(rid, None)
    rep.debug("Matrix resolve complete")
