from __future__ import annotations

from typing import TYPE_CHECKING

import bpy

from ..blender.bones import BoneRef
from ..ids import IdKind
from ..ir import NodeKind, SceneNode

if TYPE_CHECKING:
    from ..ctx import ExportContext


def resolve_armatures(ctx: "ExportContext") -> None:
    """Create bone nodes for exported armatures.

    - Honors Object.i3d_attributes.collapse_armature by setting armature node emit=False.
    - Adds NodeKind.BONE children for armature.data.bones hierarchy.
    - Stores bone-name -> nodeId mapping on ctx.ir.index for later skin weight binding.

    This is intentionally done in resolve (not traverse) to avoid polluting traversal logic.
    """
    rep = ctx.section("armatures")

    # obj_ptr -> node_id for fast lookup
    by_obj_ptr = {
        n.blender_ref.as_pointer(): nid
        for nid, n in ctx.ir.scene_nodes.items()
        if isinstance(n.blender_ref, bpy.types.Object)
    }

    # NOTE: We will add nodes to ctx.ir during this pass.
    # Snapshot the armature nodes up-front to avoid mutating the dict while iterating.
    armature_nodes = list(ctx.ir.iter_nodes(kind=NodeKind.ARMATURE, emitted_only=False))

    created_bones = 0
    for arm_node in armature_nodes:
        arm_obj = arm_node.blender_ref
        if not isinstance(arm_obj, bpy.types.Object) or arm_obj.type != "ARMATURE":
            continue

        # Collapse behavior: armature not emitted, but children still are.
        try:
            arm_node.emit = not bool(arm_obj.i3d_attributes.collapse_armature)
        except Exception:
            arm_node.emit = True

        arm_ptr = arm_obj.as_pointer()
        if arm_ptr in ctx.ir.index.bone_nodes_by_armature_ptr:
            # Already built once.
            continue

        bone_map: dict[str, int] = {}

        def add_bone(bone: bpy.types.Bone, parent_id: int) -> None:
            nonlocal created_bones

            node_id = ctx.ids.alloc(IdKind.NODE)
            node = SceneNode(
                id=node_id,
                name=bone.name,
                kind=NodeKind.BONE,
                blender_ref=BoneRef(armature_obj=arm_obj, bone_name=bone.name),
                parent_id=parent_id,
            )
            ctx.ir.add_node(node)
            bone_map[bone.name] = node_id
            created_bones += 1

            for child in bone.children:
                add_bone(child, node_id)

        # Root bones: only those with bone.parent is None.
        for bone in arm_obj.data.bones:
            if bone.parent is None:
                add_bone(bone, by_obj_ptr.get(arm_ptr, arm_node.id))

        ctx.ir.index.bone_nodes_by_armature_ptr[arm_ptr] = bone_map

    rep.debug("Armature resolve complete: created_bones=%d", created_bones)
