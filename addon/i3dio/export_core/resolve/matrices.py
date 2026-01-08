from __future__ import annotations

from typing import TYPE_CHECKING

import mathutils

from ..ir import NodeKind, SceneNode, SourceKind

if TYPE_CHECKING:
    from ..ctx import ExportContext

_CAM_LIGHT = {NodeKind.CAMERA, NodeKind.LIGHT}
_IDENTITY = mathutils.Matrix.Identity(4)


def _node_world_blender(node: SceneNode) -> mathutils.Matrix | None:
    """World matrix in Blender space for this node, or None if node has no transform."""
    if node.source_kind is SourceKind.OBJECT:
        return node.obj.matrix_world.copy()
    if node.source_kind is SourceKind.BONE_REF:
        m = node.bone_ref.world_matrix()
        return None if m is None else m.copy()
    return None


def _node_world_export_cached(
    ctx: ExportContext, node: SceneNode, cache: dict[int, mathutils.Matrix | None]
) -> mathutils.Matrix | None:
    """World matrix in EXPORT space with per-pass caching.

    This avoids recomputing conversion math (and repeated Blender lookups)
    when resolving local matrices throughout the tree.

    Note: this cache is per resolve pass (in-memory only). We intentionally
    do not store world matrices on SceneNode to keep the IR minimal.
    """
    if (hit := cache.get(node.id)) is not None:
        return hit

    if (w_bl := _node_world_blender(node)) is None:
        cache[node.id] = None
        return None

    out = ctx.to_export_forward(w_bl) if node.kind in _CAM_LIGHT else ctx.to_export(w_bl)
    cache[node.id] = out
    return out


def _bone_local_export(
    ctx: ExportContext,
    node: SceneNode,
    parent: SceneNode | None,
    *,
    world_cache: dict[int, mathutils.Matrix | None],
    arm_world_cache: dict[int, mathutils.Matrix | None],
) -> mathutils.Matrix | None:
    """
    Bone local matrix in EXPORT space (ready for serializer):

    - bone->bone: return pure armature-space relative matrix (NO axis conversion).
    - root bone: apply ONE conversion (ctx.to_export_forward).
    - if armature is collapsed or reparented: rebase under nearest emitted parent.
    """
    br = node.bone_ref
    b = br.data_bone()
    if b is None:
        return None
    arm_obj = br.armature_obj
    bone_local_bl = b.matrix_local.copy()  # relative to armature space

    # Case 1: bone parented to another bone (both in armature space).
    if parent is not None and parent.source_kind is SourceKind.BONE_REF:
        pb = parent.bone_ref.data_bone()
        return pb.matrix_local.inverted_safe() @ bone_local_bl if pb is not None else bone_local_bl

    # Root bone exported as a node (single conversion).
    bone_in_arm_export = ctx.to_export_forward(bone_local_bl)

    # Case 2: non-collapsed armature => bone parent is armature object node in XML.
    if parent is not None and parent.source_kind is SourceKind.OBJECT and parent.obj is arm_obj:
        return bone_in_arm_export

    # Case 3: collapsed armature (or bone reparented) => rebase under nearest emitted parent.
    # ParentWorld^-1 * ArmatureWorld * BoneLocalArmature
    parent_world_e = (
        _node_world_export_cached(ctx, parent, world_cache) if parent is not None else _IDENTITY
    ) or _IDENTITY

    arm_ptr = arm_obj.as_pointer()
    arm_world_e = arm_world_cache.get(arm_ptr)
    if arm_world_e is None:
        arm_world_e = ctx.to_export(arm_obj.matrix_world.copy())
        arm_world_cache[arm_ptr] = arm_world_e
    return parent_world_e.inverted_safe() @ arm_world_e @ bone_in_arm_export


def _local_matrix_export_cached(
    ctx: "ExportContext",
    node: SceneNode,
    parent: SceneNode | None,
    world_cache: dict[int, mathutils.Matrix | None],
    arm_world_cache: dict[int, mathutils.Matrix],
) -> mathutils.Matrix | None:
    """Local matrix in EXPORT space for this node, or None if node has no transform."""
    if node.source_kind is SourceKind.BONE_REF:
        return _bone_local_export(ctx, node, parent, world_cache=world_cache, arm_world_cache=arm_world_cache)

    world_e = _node_world_export_cached(ctx, node, world_cache)
    if world_e is None:
        return None

    if parent is None:
        local_e = world_e
    else:
        parent_world_e = _node_world_export_cached(ctx, parent, world_cache) or _IDENTITY

        # fast-path: only safe when both are objects and blender parent == xml parent
        if (
            node.source_kind is SourceKind.OBJECT
            and parent.source_kind is SourceKind.OBJECT
            and node.obj.parent is parent.obj
        ):
            local_e = ctx.to_export(node.obj.matrix_local.copy())
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
    rep = ctx.reporter("matrices")
    rep.debug("Matrix resolve start")

    world_cache: dict[int, mathutils.Matrix | None] = {}
    arm_world_cache: dict[int, mathutils.Matrix] = {}

    def rec(node_id: int, emitted_parent: SceneNode | None) -> None:
        node = ctx.ir.scene_nodes[node_id]
        # XML parent is the nearest emitted ancestor (emit=False nodes are transparent).
        node.matrix_local_export = _local_matrix_export_cached(ctx, node, emitted_parent, world_cache, arm_world_cache)

        next_emitted_parent = node if node.emit else emitted_parent
        for cid in ctx.ir.children_ids(node_id):
            rec(cid, next_emitted_parent)

    for root in ctx.ir.iter_roots():
        rec(root.id, None)
    rep.debug("Matrix resolve complete")
