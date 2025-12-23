from __future__ import annotations

import bpy
import mathutils

from ..ctx import ExportContext
from ..ir import SceneNode


def _node_world_blender(node: SceneNode) -> mathutils.Matrix | None:
    # If a pass/fixup provided a matrix override, use it.
    if node.matrix_world is not None:
        return node.matrix_world.copy()

    ref = node.blender_ref
    if isinstance(ref, bpy.types.Object):
        return ref.matrix_world.copy()

    return None


def world_matrix_export(ctx: ExportContext, node: SceneNode) -> mathutils.Matrix | None:
    """
    World matrix in EXPORT space for this node, or None if node has no transform.
    Currently: Objects only. Collections -> None.
    """
    ref = node.blender_ref
    if isinstance(ref, bpy.types.Object):
        return ctx.to_export(ref.matrix_world.copy())
    return None


def local_matrix_export(ctx: ExportContext, node: SceneNode, parent: SceneNode | None) -> mathutils.Matrix | None:
    """
    Local matrix in EXPORT space.
    Uses matrix_local fast-path when Blender parent matches exporter parent.
    Falls back to world-relative math when exporter parent differs.
    """
    world_bl = _node_world_blender(node)
    if world_bl is None:
        return None

    if parent is None:
        return ctx.to_export(world_bl)

    parent_world_bl = _node_world_blender(parent)
    parent_world_e = ctx.to_export(parent_world_bl) if parent_world_bl is not None else mathutils.Matrix.Identity(4)
    world_e = ctx.to_export(world_bl)

    # FAST PATH only when both refs are real objects and parenting matches
    ref = node.blender_ref
    pref = parent.blender_ref if parent else None
    if (
        isinstance(ref, bpy.types.Object)
        and isinstance(pref, bpy.types.Object)
        and ref.parent is pref
        and node.matrix_world is None
        and parent.matrix_world is None
    ):
        return ctx.to_export(ref.matrix_local.copy())

    return parent_world_e.inverted_safe() @ world_e
