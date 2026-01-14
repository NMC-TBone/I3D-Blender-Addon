# i3dio/export_core/shapes/material_resolve.py
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import bpy
import numpy as np

if TYPE_CHECKING:
    from ..ctx import ExportContext


@dataclass(slots=True)
class SlotResolve:
    slot_ids: np.ndarray  # (S,) int32
    slot_has_mat: np.ndarray  # (S,) bool
    fallback_id: int | None


def resolve_slots(ctx: "ExportContext", slot_materials: list[bpy.types.Material | None]) -> SlotResolve:
    fallback_id = choose_fallback_material_id(ctx, slot_materials=slot_materials)
    default_id = ctx.materials.get_default_id()

    slot_ids = np.empty(len(slot_materials), dtype=np.int32)
    slot_has_mat = np.zeros(len(slot_materials), dtype=bool)

    for i, mat in enumerate(slot_materials):
        if mat is not None:
            slot_has_mat[i] = True
            slot_ids[i] = ctx.materials.get_or_add(mat)
        else:
            slot_ids[i] = fallback_id if fallback_id is not None else default_id

    return SlotResolve(slot_ids=slot_ids, slot_has_mat=slot_has_mat, fallback_id=fallback_id)


def choose_fallback_material_id(ctx: "ExportContext", *, slot_materials: list[bpy.types.Material | None]) -> int | None:
    """Return:
    - int: fallback material id (only when exactly one valid material exists)
    - None: means 'use default only if needed'
    """
    valid = [m for m in slot_materials if m is not None]
    if not valid:
        return ctx.materials.get_default_id()
    if len(valid) == 1:
        return ctx.materials.get_or_add(valid[0])
    return None
