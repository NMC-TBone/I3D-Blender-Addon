from __future__ import annotations

import bpy
from bpy_extras.node_shader_utils import PrincipledBSDFWrapper


def material_requires_tangents(mat: bpy.types.Material | None) -> bool:
    if mat is None:
        return False
    if mat.i3d_attributes.shader_name == "vehicleShader":
        return True
    if PrincipledBSDFWrapper(mat, is_readonly=True).normalmap_texture is not None:
        return True
    return False
