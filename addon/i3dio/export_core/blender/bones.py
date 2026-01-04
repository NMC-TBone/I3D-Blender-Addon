from __future__ import annotations

from dataclasses import dataclass

import bpy
import mathutils


@dataclass(frozen=True, slots=True)
class BoneRef:
    """Reference to a bone within an armature object.

    We store this as the IR node blender_ref for exported bone nodes.
    """

    armature_obj: bpy.types.Object
    bone_name: str

    @property
    def name(self) -> str:
        return self.bone_name

    def pose_bone(self) -> bpy.types.PoseBone | None:
        try:
            return self.armature_obj.pose.bones.get(self.bone_name)
        except Exception:
            return None

    def data_bone(self) -> bpy.types.Bone | None:
        try:
            return self.armature_obj.data.bones.get(self.bone_name)
        except Exception:
            return None

    def world_matrix(self) -> mathutils.Matrix | None:
        """Best-effort bone world matrix in Blender space.

        - Prefer pose bone matrix (captures current pose)
        - Fall back to rest bone matrix_local
        """
        arm_w = getattr(self.armature_obj, "matrix_world", None)
        if arm_w is None:
            return None

        if (pb := self.pose_bone()) is not None:
            # PoseBone.matrix is in armature object space.
            return arm_w @ pb.matrix

        if (b := self.data_bone()) is not None:
            # Bone.matrix_local is in armature space (rest pose).
            return arm_w @ b.matrix_local

        return None
