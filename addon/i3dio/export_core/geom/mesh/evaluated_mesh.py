# i3dio/export_core/shapes/evaluated_mesh.py
from __future__ import annotations

import bpy
import mathutils

from ...ctx import ExportContext


def evaluated_mesh_for_export(
    ctx: ExportContext,
    obj: bpy.types.Object,
    *,
    reference_frame: mathutils.Matrix | None = None,
) -> tuple[bpy.types.Object, bpy.types.Mesh]:
    """
    Create a temporary mesh for export:
    - optionally evaluated (modifiers)
    - optionally moved into a reference_frame
    - converted to export axis space
    - scaled by ctx.unit_scale (to match node translation scaling)
    """
    apply_modifiers = ctx.settings.get("apply_modifiers", True)

    if apply_modifiers:
        ev_obj = obj.evaluated_get(ctx.depsgraph)
    else:
        ev_obj = obj

    mesh = ev_obj.to_mesh(preserve_all_data_layers=False, depsgraph=ctx.depsgraph)

    # Optional "reference frame" placement (used later for merge features)
    if reference_frame is not None:
        mesh.transform(reference_frame.inverted() @ ev_obj.matrix_world)

    # Convert to export space, and scale consistently with node translation scaling.
    conv = mathutils.Matrix.Scale(ctx.unit_scale, 4) @ ctx.conversion_matrix
    mesh.transform(conv)
    if conv.is_negative:
        mesh.flip_normals()

    mesh.calc_loop_triangles()
    return ev_obj, mesh


def free_evaluated_mesh(ev_obj: bpy.types.Object) -> None:
    try:
        ev_obj.to_mesh_clear()
    except Exception:
        pass
