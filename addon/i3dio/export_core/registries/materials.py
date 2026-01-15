# i3dio/export_core/registries/materials.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import bpy

from ..ids import IdKind
from ..model.materials import MaterialEntry, MaterialKey
from .base import IdEntryTable

if TYPE_CHECKING:
    from ..ctx import ExportContext

DEFAULT_MATERIAL_NAME = "i3d_default_material"


@dataclass(slots=True)
class MaterialTable(IdEntryTable[MaterialEntry, MaterialKey]):
    ctx: "ExportContext"
    _by_key: dict[MaterialKey, int] = field(default_factory=dict)
    _entries: dict[int, MaterialEntry] = field(default_factory=dict)
    _default_id: int | None = None

    def _alloc_entry(self, *, key: MaterialKey, blender_material: bpy.types.Material | None) -> MaterialEntry:
        mid = self.ctx.ids.alloc(IdKind.MATERIAL)
        entry = MaterialEntry(id=mid, key=key, blender_material=blender_material)
        self.register(key=key, entry_id=mid, entry=entry)
        return entry

    def get_default_id(self) -> int:
        if self._default_id is None:
            self._default_id = self.get_or_add(None, export_name=DEFAULT_MATERIAL_NAME)
        return self._default_id

    def get_or_add(self, mat: bpy.types.Material | None, *, export_name: str | None = None) -> int:
        """
        Get or add a material entry by Blender material and optional export name override.
        If mat is None, a default material entry is used/created.
        """
        if mat is None:
            name = export_name or DEFAULT_MATERIAL_NAME
            key = MaterialKey(0, name)

            if (mid := self.get_id(key)) is not None:
                if name == DEFAULT_MATERIAL_NAME:
                    self._default_id = mid
                return mid
            entry = self._alloc_entry(key=key, blender_material=None)
            if name == DEFAULT_MATERIAL_NAME:
                self._default_id = entry.id
            return entry.id

        name = export_name or mat.name
        key = MaterialKey(mat.as_pointer(), name)
        if (mid := self.get_id(key)) is not None:
            return mid

        return self._alloc_entry(key=key, blender_material=mat).id
