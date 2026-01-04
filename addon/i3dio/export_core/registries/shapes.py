# i3dio/export_core/registries/shapes.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import bpy

from ..ids import IdKind
from ..ir import NodeKind, SceneNode, to_transform_group
from ..model.its import BuiltITS
from ..model.shapes import ShapeEntry, ShapeKey, ShapeVariant
from ..shapes import ShapeContributor, ShapeMode
from ..shapes.its.build import build_indexed_triangle_set
from .base import IdEntryTable

if TYPE_CHECKING:
    from ..ctx import ExportContext


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

        built = build_indexed_triangle_set(self.ctx, self.get_entry(shape_id))
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
            variant=ShapeVariant.NORMAL,
            slot_name_signature=_slot_name_signature(obj),
        )
        if (sid := self.get_id(key)) is not None:
            return sid
        entry = self._alloc_entry(key=key, name=mesh.name, mode=ShapeMode.NORMAL)
        entry.contributors.append(ShapeContributor(obj=obj, reference_frame=None))
        return entry.id

    def add_merge_shape(
        self,
        *,
        root_obj: bpy.types.Object,
        name: str,
        mode: ShapeMode,
        variant: ShapeVariant,
        merge_group_index: int | None = None,
    ) -> ShapeEntry:
        key = ShapeKey(
            kind="IndexedTriangleSet",
            data_ptr=0,
            object_ptr=root_obj.as_pointer(),
            apply_modifiers=self.ctx.settings.get("apply_modifiers", True),
            variant=variant,
            merge_group_index=merge_group_index,
        )
        return self._alloc_entry(key=key, name=name, mode=mode)

    def add_skinned_mesh_shape(self, obj: bpy.types.Object, *, name: str | None = None) -> ShapeEntry:
        """Create a per-object skinned mesh shape entry.

        We force apply_modifiers=False to keep mesh vertex topology aligned with
        Object vertex groups and weight data.
        """
        mesh = obj.data
        key = ShapeKey(
            kind="IndexedTriangleSet",
            data_ptr=mesh.as_pointer() if hasattr(mesh, "as_pointer") else 0,
            object_ptr=obj.as_pointer(),
            apply_modifiers=False,
            variant=ShapeVariant.SKINNED_MESH,
        )
        entry = self._alloc_entry(key=key, name=name or getattr(mesh, "name", obj.name), mode=ShapeMode.SKINNED_MESH)
        entry.enable_skin_weights()
        entry.contributors.append(ShapeContributor(obj=obj, reference_frame=None))
        return entry

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


def _material_slot_name(mat: bpy.types.Material | None) -> str | None:
    if mat is None or not mat.i3d_attributes.use_material_slot_name:
        return None
    return mat.i3d_attributes.material_slot_name or mat.name


def _slot_name_signature(obj: bpy.types.Object) -> tuple[str | None, ...]:
    # canonical per-slot view; includes None slots
    return tuple(_material_slot_name(ms.material) for ms in obj.material_slots)
