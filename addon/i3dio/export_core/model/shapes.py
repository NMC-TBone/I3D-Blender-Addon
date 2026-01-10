# i3dio/export_core/model/shapes.py
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Iterable

import bpy
import mathutils

from ..ir import EmitAttrs


class ShapeMode(Enum):
    """How the shape is built and keyed for deduplication."""

    NORMAL = auto()  # Single mesh, keyed by datablock
    MERGE_GROUP = auto()  # Multiple meshes merged, keyed by root object
    MERGE_CHILDREN = auto()  # Children merged with generic values
    SKINNED_MESH = auto()  # Armature-driven, keyed per object


@dataclass(slots=True)
class ShapeContributor:
    obj: bpy.types.Object
    reference_frame: mathutils.Matrix | None  # Blender-space frame

    generic_value01: float | None = None  # MergeChildren normalized [0..1]
    bind_index: int | None = None  # MergeGroup 0..N-1
    skin_vgroup_to_bind_index: dict[int, int] | None = None  # Skinned mesh vgroup -> bind index


@dataclass(frozen=True, slots=True)
class ShapeKey:
    """Deduplication key for shapes. Use factory methods for construction."""

    data_ptr: int
    object_ptr: int
    apply_modifiers: bool
    mode: ShapeMode = ShapeMode.NORMAL
    merge_group_index: int | None = None
    slot_name_signature: tuple[str | None, ...] | None = None

    @classmethod
    def for_mesh(
        cls,
        *,
        data_ptr: int,
        object_ptr: int,
        apply_modifiers: bool,
        slot_name_signature: tuple[str | None, ...] | None = None,
    ) -> "ShapeKey":
        """Key for a normal mesh shape."""
        return cls(
            data_ptr=data_ptr,
            object_ptr=object_ptr,
            apply_modifiers=apply_modifiers,
            mode=ShapeMode.NORMAL,
            slot_name_signature=slot_name_signature,
        )

    @classmethod
    def for_merge(
        cls,
        *,
        object_ptr: int,
        apply_modifiers: bool,
        mode: ShapeMode,
        merge_group_index: int | None = None,
    ) -> "ShapeKey":
        """Key for a merged shape (MERGE_GROUP or MERGE_CHILDREN)."""
        return cls(
            data_ptr=0,
            object_ptr=object_ptr,
            apply_modifiers=apply_modifiers,
            mode=mode,
            merge_group_index=merge_group_index,
        )

    @classmethod
    def for_skinned(cls, *, data_ptr: int, object_ptr: int, apply_modifiers: bool) -> "ShapeKey":
        """Key for a skinned mesh shape."""
        return cls(
            data_ptr=data_ptr,
            object_ptr=object_ptr,
            apply_modifiers=apply_modifiers,
            mode=ShapeMode.SKINNED_MESH,
        )


@dataclass(slots=True)
class ShapeEntry:
    id: int
    key: ShapeKey
    name: str
    contributors: list[ShapeContributor] = field(default_factory=list)
    attrs: EmitAttrs = field(default_factory=EmitAttrs)

    @property
    def mode(self) -> ShapeMode:
        return self.key.mode

    @property
    def want_generic_value01(self) -> bool:
        return self.attrs.children.get("Vertices", {}).get("generic", False)

    @property
    def want_bind_index(self) -> bool:
        return self.attrs.children.get("Vertices", {}).get("singleblendweights", False)

    @property
    def want_skin_weights(self) -> bool:
        return self.attrs.children.get("Vertices", {}).get("blendweights", False)

    def enable_tangent(self) -> None:
        self.attrs.node.setdefault("tangent", True)

    def enable_generic_value01(self) -> None:
        self.attrs.children.setdefault("Vertices", {})["generic"] = True

    def enable_generic_value01_if_detected(self, streams: Iterable[object]) -> None:
        if self.want_generic_value01:
            return
        if any(getattr(s, "generic", None) is not None for s in streams):
            self.enable_generic_value01()

    def enable_bind_index(self) -> None:
        self.attrs.children.setdefault("Vertices", {})["singleblendweights"] = True

    def enable_skin_weights(self) -> None:
        self.attrs.children.setdefault("Vertices", {})["blendweights"] = True
