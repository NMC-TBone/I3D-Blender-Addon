# i3dio/export_core/shapes/build/material_resolve.py
from __future__ import annotations

import bpy

from ...ctx import ExportContext


def choose_fallback_material_id(ctx: ExportContext, *, slot_materials: list[bpy.types.Material | None]) -> int | None:
    """Return:
    - int: fallback material id (only when exactly one valid material exists)
    - None: means 'use default only if needed'
    """
    valid = [m for m in slot_materials if m is not None]
    if len(valid) == 1:
        return ctx.materials.get_or_add(valid[0])
    return None


def safe_material_id_for_triangle(
    ctx: ExportContext,
    *,
    obj_name: str,
    slot_materials: list[bpy.types.Material | None],
    mat_idx: int,
    fallback_id: int,
    warned: set[str],
) -> int:
    if 0 <= mat_idx < len(slot_materials):
        mat = slot_materials[mat_idx]
        if mat is not None:
            return ctx.materials.get_or_add(mat)

    # empty / out-of-bounds
    if obj_name not in warned:
        ctx.section("materials").warning(
            "[%s] Triangle references empty/out-of-bounds material slot %d; using fallback/default material",
            obj_name,
            mat_idx,
        )
        warned.add(obj_name)

    return fallback_id if fallback_id is not None else ctx.materials.get_default_id()
