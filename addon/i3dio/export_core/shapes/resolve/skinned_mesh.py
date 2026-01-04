# i3dio/export_core/shapes/resolve/skinned_mesh.py
from __future__ import annotations

from typing import TYPE_CHECKING

import bpy

from ...ir import NodeKind

if TYPE_CHECKING:
    from ...ctx import ExportContext


def resolve_skinned_meshes(ctx: ExportContext) -> None:
    rep = ctx.section("skinned_mesh")

    # Find bone nodes produced by resolve_armatures.
    bones_by_arm_ptr = ctx.ir.index.bone_nodes_by_armature_ptr

    processed = 0
    for node in list(ctx.ir.iter_nodes(kind=NodeKind.SHAPE, emitted_only=False)):
        obj = node.blender_ref
        if not isinstance(obj, bpy.types.Object) or obj.type != "MESH":
            continue

        # Find armature modifiers with valid armature object.
        arm_mods = [m for m in obj.modifiers if m.type == "ARMATURE" and getattr(m, "object", None) is not None]
        if not arm_mods:
            continue

        # Only treat as skinned mesh if there are vertex groups (skinning data).
        if not getattr(obj, "vertex_groups", None) or len(obj.vertex_groups) == 0:
            continue

        bind_node_ids: list[int] = []
        vgroup_to_bind: dict[int, int] = {}

        # Build bind list by scanning vertex group names against exported bones.
        # Bind index order is deterministic: armature modifiers in order, then group index order.
        bind_idx = 0
        for mod in arm_mods:
            arm_obj = mod.object
            if not isinstance(arm_obj, bpy.types.Object) or arm_obj.type != "ARMATURE":
                continue
            bone_map = bones_by_arm_ptr.get(arm_obj.as_pointer())
            if not bone_map:
                continue

            for vg in obj.vertex_groups:
                if vg.index in vgroup_to_bind:
                    continue
                if (bone_node_id := bone_map.get(vg.name)) is None:
                    continue
                vgroup_to_bind[int(vg.index)] = bind_idx
                bind_node_ids.append(int(bone_node_id))
                bind_idx += 1

        if not bind_node_ids:
            # Mesh has armature modifiers but no matching exported bones.
            ctx.object_reporter(obj, "skinned_mesh").warning(
                "Mesh has armature modifier(s) but no matching exported bones were found via vertex group names; "
                "it will be exported as a normal mesh.",
                code="skinned_mesh_no_matching_bones",
            )
            continue

        # Create distinct skinned mesh shape entry and link to node.
        entry = ctx.shapes.add_skinned_mesh_shape(obj, name=obj.data.name if obj.data else obj.name)
        entry.key  # ensure allocated

        # Inject contributor mapping
        if entry.contributors:
            entry.contributors[0].skin_vgroup_to_bind_index = vgroup_to_bind

        node.kind = NodeKind.SHAPE
        node.shape_id = entry.id
        node.skin_bind_node_ids = bind_node_ids

        processed += 1
        rep.debug("[%s] Skinned mesh shapeId=%d binds=%d", obj.name, entry.id, len(bind_node_ids))

    if not processed:
        rep.debug("No skinned meshes detected")
