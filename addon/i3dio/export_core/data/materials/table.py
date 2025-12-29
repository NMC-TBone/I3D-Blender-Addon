# i3dio/export_core/materials/table.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import bpy

from ...ids import IdKind
from ...ir import XmlBuckets

if TYPE_CHECKING:
    from ...ctx import ExportContext

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


@dataclass(slots=True)
class MaterialTable:
    ctx: "ExportContext"
    _by_key: dict[MaterialKey, int] = field(default_factory=dict)
    _entries: dict[int, MaterialEntry] = field(default_factory=dict)
    _default_id: int | None = None

    def get_default_id(self) -> int:
        if self._default_id is not None:
            return self._default_id

        key = MaterialKey(0, DEFAULT_MATERIAL_NAME)
        if (mid := self._by_key.get(key)) is not None:
            self._default_id = mid
            return mid

        mid = self.ctx.ids.alloc(IdKind.MATERIAL)
        self._by_key[key] = mid
        self._entries[mid] = MaterialEntry(id=mid, key=key, blender_material=None)
        self._default_id = mid
        return mid

    def get_or_add(self, mat: bpy.types.Material | None, *, export_name: str | None = None) -> int:
        if mat is None:
            return self.get_default_id()
        name = export_name or mat.name
        key = MaterialKey(mat.as_pointer(), name)

        if (mid := self._by_key.get(key)) is not None:
            return mid

        mid = self.ctx.ids.alloc(IdKind.MATERIAL)
        self._by_key[key] = mid
        self._entries[mid] = MaterialEntry(id=mid, key=key, blender_material=mat)
        return mid

    def entries(self) -> list[MaterialEntry]:
        return [self._entries[k] for k in sorted(self._entries)]
