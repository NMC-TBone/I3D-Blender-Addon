# i3dio/export_core/ir/builder.py
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import bpy

from ..blender.bones import BoneRef
from ..ids import IdKind
from .model import NodeKind, SceneNode, SourceKind

if TYPE_CHECKING:
    from ..ctx import ExportContext

BlenderRef = bpy.types.Object | bpy.types.Collection | BoneRef


def _blender_ptr(x: object) -> int | None:
    """Return the Blender pointer integer for x, or None if not available."""
    ap = getattr(x, "as_pointer", None)
    if ap is None:
        return None
    try:
        return int(ap())
    except Exception:
        return None


def _source_meta(ref: object) -> tuple[SourceKind, int | None, str | None]:
    if isinstance(ref, bpy.types.Object):
        return (SourceKind.OBJECT, _blender_ptr(ref), ref.type)
    if isinstance(ref, bpy.types.Collection):
        return (SourceKind.COLLECTION, _blender_ptr(ref), None)
    if isinstance(ref, BoneRef):
        return (SourceKind.BONE_REF, None, None)
    return (SourceKind.OTHER, _blender_ptr(ref), None)


@dataclass(slots=True)
class SceneBuilder:
    ctx: ExportContext

    def add_scene_node(self, *, kind: NodeKind, blender_ref: BlenderRef, parent_id: int | None) -> int:
        """Create a SceneNode in IR and attach it into the tree."""
        node_id = self.ctx.ids.alloc(IdKind.NODE)
        source_kind, source_ptr, source_object_type = _source_meta(blender_ref)
        node = SceneNode(
            id=node_id,
            name=getattr(blender_ref, "name", f"Node_{node_id}"),
            source_kind=source_kind,
            source_ptr=source_ptr,
            source_object_type=source_object_type,
            kind=kind,
            blender_ref=blender_ref,
            parent_id=parent_id,
        )
        self.ctx.ir.add_node(node)
        return node_id

    def add_object(self, obj: bpy.types.Object, *, parent_id: int | None) -> int:
        return self.add_scene_node(kind=NodeKind.UNRESOLVED, blender_ref=obj, parent_id=parent_id)

    def add_collection(self, col: bpy.types.Collection, *, parent_id: int | None) -> int:
        return self.add_scene_node(kind=NodeKind.TRANSFORM_GROUP, blender_ref=col, parent_id=parent_id)

    def add_bone(self, bone_ref: BoneRef, *, parent_id: int) -> int:
        return self.add_scene_node(kind=NodeKind.TRANSFORM_GROUP, blender_ref=bone_ref, parent_id=parent_id)
