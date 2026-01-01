# i3dio/export_core/tables/shapes.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

import bpy

from ..ids import IdKind
from ..ir import NodeKind, SceneNode, XmlBuckets
from ..ir_node_helpers import to_transform_group
from ..shapes import ShapeContributor, ShapeMode
from ..shapes.its import BuiltITS
from ..shapes.its.build import build_indexed_triangle_set
from .base import IdEntryTable

if TYPE_CHECKING:
    from ..ctx import ExportContext

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
    contributors: list[ShapeContributor] = field(default_factory=list)
    xml: XmlBuckets = field(default_factory=XmlBuckets)


@dataclass(slots=True)
class ShapeTable(IdEntryTable[ShapeEntry, ShapeKey]):
    ctx: "ExportContext"
    _by_key: dict[ShapeKey, int] = field(default_factory=dict)
    _entries: dict[int, ShapeEntry] = field(default_factory=dict)
    built_by_id: dict[int, BuiltITS | None] = field(default_factory=dict)

    def _alloc_entry(self, *, key: ShapeKey, name: str, mode: ShapeMode) -> ShapeEntry:
        sid = self.ctx.ids.alloc(IdKind.SHAPE)
        entry = ShapeEntry(id=sid, key=key, name=name, mode=mode)
        self.register(key=key, entry_id=sid, entry=entry)
        return entry

    def get_built(self, shape_id: int) -> BuiltITS | None:
        """
        Build (or fetch cached) built geometry for shape_id.
        Caches None as well to avoid rebuilding known-invalid shapes.
        """
        if shape_id in self.built_by_id:
            return self.built_by_id[shape_id]

        entry = self.get_entry(shape_id)
        built = build_indexed_triangle_set(self.ctx, entry)
        self.built_by_id[shape_id] = built  # cache success OR failure
        return built

    def get_or_add_mesh(self, obj: bpy.types.Object) -> int:
        apply_modifiers = self.ctx.settings.get("apply_modifiers", True)
        mesh = obj.data

        # Modifiers live on the object. If we are applying modifiers, only shapes
        # with enabled modifiers should be keyed per-object; modifier-free linked duplicates can safely share.
        has_enabled_modifiers = any(m.show_viewport for m in obj.modifiers)
        object_ptr = obj.as_pointer() if (apply_modifiers and has_enabled_modifiers) else 0

        key = ShapeKey(
            kind="IndexedTriangleSet",
            data_ptr=mesh.as_pointer(),
            object_ptr=object_ptr,
            apply_modifiers=apply_modifiers,
            special=None,
        )
        if (sid := self.get_id(key)) is not None:
            return sid
        entry = self._alloc_entry(key=key, name=mesh.name, mode=ShapeMode.NORMAL)
        entry.contributors.append(ShapeContributor(obj=obj, reference_frame=None))
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

    def register_entry(self, entry: ShapeEntry) -> None:
        self._by_key[entry.key] = entry.id
        self._entries[entry.id] = entry

    def link_node(self, node: SceneNode) -> None:
        """Link a SceneNode to a ShapeEntry by setting node.shape_id."""
        ref = node.blender_ref
        if node.kind != NodeKind.SHAPE or not node.emit:
            return
        if node.shape_id is not None:
            return
        if not isinstance(ref, bpy.types.Object):
            node.kind = NodeKind.TRANSFORM_GROUP
            return

        self.ctx.node_reporter(node, "shape").debug("Linking ShapeEntry to SceneNode")

        if isinstance(ref.data, bpy.types.Mesh):
            node.shape_id = self.get_or_add_mesh(ref)
            return

        # future: Curve support
        to_transform_group(node)

    def iter_built(self):
        """Iterate over all built shapes (skipping None)."""
        for sid in sorted(self.built_by_id):
            if (built := self.built_by_id[sid]) is not None:
                yield built
