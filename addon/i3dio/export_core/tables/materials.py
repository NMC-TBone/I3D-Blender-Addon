# i3dio/export_core/tables/materials.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import bpy

from ..ids import IdKind
from ..ir import XmlBuckets
from .base import IdEntryTable

if TYPE_CHECKING:
    from ..ctx import ExportContext

DEFAULT_MATERIAL_NAME = "i3d_default_material"


@dataclass(frozen=True, slots=True)
class MaterialKey:
    material_ptr: int  # 0 for None/export side only
    export_name: str  # final Material@name (slot override or datablock name)


@dataclass(slots=True)
class MaterialEntry:
    id: int
    key: MaterialKey
    blender_material: bpy.types.Material | None
    xml: XmlBuckets = field(default_factory=XmlBuckets)
    extra_children: list[tuple[str, dict[str, Any]]] = field(default_factory=list)


@dataclass(slots=True)
class MaterialTable(IdEntryTable[MaterialEntry, MaterialKey]):
    ctx: "ExportContext"
    _by_key: dict[MaterialKey, int] = field(default_factory=dict)
    _entries: dict[int, MaterialEntry] = field(default_factory=dict)
    _default_id: int | None = None

    def _alloc_entry(self, *, key: MaterialKey, blender_material: bpy.types.Material | None) -> int:
        mid = self.ctx.ids.alloc(IdKind.MATERIAL)
        self.register(key=key, entry_id=mid, entry=MaterialEntry(id=mid, key=key, blender_material=blender_material))
        return mid

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
            mid = self._alloc_entry(key=key, blender_material=None)
            if name == DEFAULT_MATERIAL_NAME:
                self._default_id = mid
            return mid

        name = export_name or mat.name
        key = MaterialKey(mat.as_pointer(), name)
        if (mid := self.get_id(key)) is not None:
            return mid

        return self._alloc_entry(key=key, blender_material=mat)
