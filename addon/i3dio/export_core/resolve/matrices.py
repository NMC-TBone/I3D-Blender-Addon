from __future__ import annotations

from typing import TYPE_CHECKING

import bpy
import mathutils

from ..blender.bones import BoneRef
from ..ir import NodeKind, SceneNode

if TYPE_CHECKING:
    from ..ctx import ExportContext

_CAM_LIGHT = {NodeKind.CAMERA, NodeKind.LIGHT}
_IDENTITY = mathutils.Matrix.Identity(4)


def _node_world_blender(node: SceneNode) -> mathutils.Matrix | None:
    """World matrix in Blender space for this node, or None if node has no transform."""
    ref = node.blender_ref
    if isinstance(ref, bpy.types.Object):
        return ref.matrix_world.copy()
    if isinstance(ref, BoneRef):
        m = ref.world_matrix()
        return None if m is None else m.copy()
    return None


def _node_world_export_cached(
    ctx: "ExportContext", node: SceneNode, cache: dict[int, mathutils.Matrix | None]
) -> mathutils.Matrix | None:
    """World matrix in EXPORT space with per-pass caching.

    This avoids recomputing conversion math (and repeated Blender lookups)
    when resolving local matrices throughout the tree.

    Note: this cache is per resolve pass (in-memory only). We intentionally
    do not store world matrices on SceneNode to keep the IR minimal.
    """
    if node.id in cache:
        return cache[node.id]

    w_bl = _node_world_blender(node)
    if w_bl is None:
        cache[node.id] = None
        return None

    if node.kind in _CAM_LIGHT:
        out = ctx.to_export_forward(w_bl)
        cache[node.id] = out
        return out

    out = ctx.to_export(w_bl)
    cache[node.id] = out
    return out


def _local_matrix_export_cached(
    ctx: "ExportContext",
    node: SceneNode,
    parent: SceneNode | None,
    world_cache: dict[int, mathutils.Matrix | None],
) -> mathutils.Matrix | None:
    """Local matrix in EXPORT space for this node, or None if node has no transform."""
    # Bone transforms are special.
    #
    # Key idea: Blender bones live in *armature space*.
    # - Rest pose: Bone.matrix_local is already a transform in armature space.
    # - Child bones: parent^-1 @ child gives a purely armature-space relative matrix.
    #   In that case we must NOT apply exporter axis conversion again.
    # - Root bones: need exporter axis conversion when becoming an I3D node.
    #
    # GIANTS/I3D expects bones as TransformGroups with local TRS relative to their exported parent
    # (either the armature node, or the nearest emitted ancestor when the armature is collapsed).
    if isinstance(node.blender_ref, BoneRef):
        bone_ref = node.blender_ref
        arm_obj = bone_ref.armature_obj
        b = bone_ref.data_bone()
        if b is None:
            return None

        bone_local_bl = b.matrix_local.copy()  # relative to armature space

        # Case 1: bone parented to another bone.
        # Both matrices are in armature space already, so we just compute the relative matrix in that same space.
        if parent is not None and isinstance(parent.blender_ref, BoneRef):
            pb = parent.blender_ref.data_bone()
            if pb is not None:
                return pb.matrix_local.inverted_safe() @ bone_local_bl
            return bone_local_bl

        # Case 2+: root bone (in armature space) exported as a node.
        # Convert axes once from Blender space to export space.
        bone_in_arm_export = ctx.to_export_forward(bone_local_bl)

        # Case 2: non-collapsed armature.
        # The bone is parented to the armature node in XML, so this local matrix is ready as-is.
        if parent is not None and parent.kind == NodeKind.ARMATURE:
            return bone_in_arm_export

        # Case 3: collapsed armature (or the bone node is effectively reparented).
        # The armature node is transparent in XML, so the bone must inherit the armature's world transform.
        # We rebase the bone transform under the nearest emitted parent:
        #   ParentWorld^-1 * ArmatureWorld * BoneLocalArmature
        parent_world_e = _node_world_export_cached(ctx, parent, world_cache) if parent is not None else _IDENTITY
        arm_world_e = ctx.to_export(arm_obj.matrix_world.copy())
        return parent_world_e.inverted_safe() @ arm_world_e @ bone_in_arm_export

    world_e = _node_world_export_cached(ctx, node, world_cache)
    if world_e is None:
        return None

    if parent is None:
        local_e = world_e
    else:
        parent_world_e = _node_world_export_cached(ctx, parent, world_cache) or _IDENTITY

        # fast-path: only safe when both are real objects and exporter parent == Blender parent
        ref = node.blender_ref
        parent_ref = parent.blender_ref if parent else None
        if isinstance(ref, bpy.types.Object) and isinstance(parent_ref, bpy.types.Object) and ref.parent is parent_ref:
            local_e = ctx.to_export(ref.matrix_local.copy())
        else:
            local_e = parent_world_e.inverted_safe() @ world_e

    # If parent is a camera/light, we need to adjust for the flipped z-axis in GE space
    if parent and parent.kind in _CAM_LIGHT:
        local_e = ctx.conversion_matrix_inv @ local_e
        ctx.node_reporter(node, "matrices").debug(
            "Adjusted local matrix due to parent %s axis handling", parent.kind.name
        )

    return local_e


def resolve_matrices(ctx: "ExportContext") -> None:
    """Compute local EXPORT-space matrices for all nodes and store them on the node."""
    rep = ctx.section("matrices")
    rep.debug("Matrix resolve start")

    world_cache: dict[int, mathutils.Matrix | None] = {}

    def rec(node_id: int, emitted_parent: SceneNode | None) -> None:
        node = ctx.ir.scene_nodes[node_id]
        # XML parent is the nearest emitted ancestor (emit=False nodes are transparent).
        node.matrix_local_export = _local_matrix_export_cached(ctx, node, emitted_parent, world_cache)

        next_emitted_parent = node if node.emit else emitted_parent
        for cid in node.children:
            rec(cid, next_emitted_parent)

    for rid in ctx.ir.roots:
        rec(rid, None)
    rep.debug("Matrix resolve complete")
