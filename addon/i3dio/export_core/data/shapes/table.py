# i3dio/export_core/shapes/table.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

import bpy

from ...geom.its.built import BuiltITS
from ...ids import IdKind
from ...ir import XmlBuckets
from .types import MeshContribution, ShapeMode

if TYPE_CHECKING:
    from ...ctx import ExportContext

ShapeKind = Literal["IndexedTriangleSet", "NurbsCurve"]


@dataclass(frozen=True, slots=True)
class ShapeKey:
    kind: ShapeKind
    data_ptr: int  # mesh/curve datablock pointer
    object_ptr: int  # object pointer (for modifier-applied shapes)
    apply_modifiers: bool
    special: str | None = None  # None for "normal" meshes


@dataclass(slots=True)
class ShapeEntry:
    id: int
    key: ShapeKey
    name: str
    mode: ShapeMode
    contributors: list[MeshContribution] = field(default_factory=list)
    xml: XmlBuckets = field(default_factory=XmlBuckets)


@dataclass(slots=True)
class ShapeTable:
    ctx: "ExportContext"
    _by_key: dict[ShapeKey, int] = field(default_factory=dict)
    _entries: dict[int, ShapeEntry] = field(default_factory=dict)
    built_its: dict[int, BuiltITS] = field(default_factory=dict)

    def _alloc_entry(self, *, key: ShapeKey, name: str, mode: ShapeMode) -> ShapeEntry:
        sid = self.ctx.ids.alloc(IdKind.SHAPE)
        entry = ShapeEntry(id=sid, key=key, name=name, mode=mode)
        self._by_key[key] = sid
        self._entries[sid] = entry
        return entry

    def get_or_add_mesh(self, obj: bpy.types.Object) -> int:
        apply_modifiers = self.ctx.settings.get("apply_modifiers", True)
        mesh = obj.data
        assert isinstance(mesh, bpy.types.Mesh), "Expected a Mesh data-block"

        key = ShapeKey(
            kind="IndexedTriangleSet",
            data_ptr=mesh.as_pointer(),
            object_ptr=obj.as_pointer() if apply_modifiers else 0,
            apply_modifiers=apply_modifiers,
            special=None,
        )
        if (sid := self._by_key.get(key)) is not None:
            return sid
        entry = self._alloc_entry(key=key, name=mesh.name, mode=ShapeMode.NORMAL)
        entry.contributors.append(MeshContribution(obj=obj, reference_frame=None, id_value=0.0))
        return entry.id

    def add_merge_children(self, root_obj: bpy.types.Object) -> ShapeEntry:
        apply_modifiers = self.ctx.settings.get("apply_modifiers", True)
        key = ShapeKey(
            kind="IndexedTriangleSet",
            data_ptr=0,
            object_ptr=root_obj.as_pointer(),
            apply_modifiers=apply_modifiers,
            special="MERGE_CHILDREN",
        )
        entry = self._alloc_entry(key=key, name=root_obj.name, mode=ShapeMode.MERGE_CHILDREN_GENERIC)
        entry.xml.children.setdefault("Vertices", {})["generic"] = True
        return entry

    def add_merge_group(self, *, root_obj: bpy.types.Object, mg_index: int) -> ShapeEntry:
        apply_modifiers = self.ctx.settings.get("apply_modifiers", True)
        key = ShapeKey(
            kind="IndexedTriangleSet",
            data_ptr=0,
            object_ptr=root_obj.as_pointer(),
            apply_modifiers=apply_modifiers,
            special=f"MERGE_GROUP:{mg_index}",
        )
        entry = self._alloc_entry(key=key, name=f"mergeGroup_{mg_index}", mode=ShapeMode.MERGE_GROUP)
        entry.xml.children.setdefault("Vertices", {})["singleblendweights"] = True
        return entry

    def get_entry(self, shape_id: int) -> ShapeEntry:
        return self._entries[shape_id]

    def entries(self) -> list[ShapeEntry]:
        return [self._entries[k] for k in sorted(self._entries)]

    def add_entry(self, entry: ShapeEntry) -> None:
        self._by_key[entry.key] = entry.id
        self._entries[entry.id] = entry
