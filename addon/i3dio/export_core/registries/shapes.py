# i3dio/export_core/registries/shapes.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import bpy

from ..ids import IdKind
from ..ir import SceneNode, ShapeSceneExt, to_transform_group
from ..model.its import BuiltITS
from ..model.shapes import ShapeEntry, ShapeKey, ShapeMode
from ..shapes import ShapeContributor
from ..shapes.build_its import build_indexed_triangle_set
from .base import IdEntryTable

if TYPE_CHECKING:
    from ..ctx import ExportContext


@dataclass(slots=True)
class ShapeTable(IdEntryTable[ShapeEntry, ShapeKey]):
    ctx: "ExportContext"
    _by_key: dict[ShapeKey, int] = field(default_factory=dict)
    _entries: dict[int, ShapeEntry] = field(default_factory=dict)
    built_by_id: dict[int, BuiltITS | None] = field(default_factory=dict)

    def _alloc_entry(self, *, key: ShapeKey, name: str) -> ShapeEntry:
        sid = self.ctx.ids.alloc(IdKind.SHAPE)
        entry = ShapeEntry(id=sid, key=key, name=name)
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
        apply_modifiers = self.ctx.setting("apply_modifiers", True)
        mesh = obj.data

        # Modifiers live on the object. If we are applying modifiers, only shapes
        # with enabled modifiers should be keyed per-object; modifier-free linked duplicates can safely share.
        has_enabled_modifiers = any(m.show_viewport for m in obj.modifiers)
        object_ptr = obj.as_pointer() if (apply_modifiers and has_enabled_modifiers) else 0

        key = ShapeKey.for_mesh(
            data_ptr=mesh.as_pointer(),
            object_ptr=object_ptr,
            apply_modifiers=apply_modifiers,
            slot_name_signature=_slot_name_signature(obj),
        )
        if (sid := self.get_id(key)) is not None:
            return sid
        entry = self._alloc_entry(key=key, name=mesh.name)
        entry.contributors.append(ShapeContributor(obj=obj, reference_frame=None))
        return entry.id

    def add_merge_shape(
        self, *, root_obj: bpy.types.Object, name: str, mode: ShapeMode, merge_group_index: int | None = None
    ) -> ShapeEntry:
        key = ShapeKey.for_merge(
            object_ptr=root_obj.as_pointer(),
            apply_modifiers=self.ctx.setting("apply_modifiers", True),
            mode=mode,
            merge_group_index=merge_group_index,
        )
        return self._alloc_entry(key=key, name=name)

    def add_skinned_mesh_shape(self, obj: bpy.types.Object, *, name: str | None = None) -> ShapeEntry:
        """Create a per-object skinned mesh shape entry."""
        mesh = obj.data
        key = ShapeKey.for_skinned(
            data_ptr=mesh.as_pointer() if hasattr(mesh, "as_pointer") else 0,
            object_ptr=obj.as_pointer(),
            apply_modifiers=self.ctx.setting("apply_modifiers", True),
        )
        entry = self._alloc_entry(key=key, name=name or getattr(mesh, "name", obj.name))
        entry.enable_skin_weights()
        entry.contributors.append(ShapeContributor(obj=obj, reference_frame=None))
        return entry

    def link_node(self, node: SceneNode) -> None:
        """Link a SceneNode to a ShapeEntry by setting node.shape_id."""
        # Check if already linked by inspecting shape_id directly
        if node._shape is not None and node._shape.shape_id is not None:
            return  # already linked

        self.ctx.node_reporter(node, "shape").debug("Linking ShapeEntry to SceneNode")
        if node.source_object_type == 'MESH':
            shape_id = self.get_or_add_mesh(node.obj)
            # Ensure _shape extension exists before assigning shape_id
            if node._shape is None:
                node._shape = ShapeSceneExt()
            node._shape.shape_id = shape_id
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
