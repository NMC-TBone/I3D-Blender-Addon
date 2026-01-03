# i3dio/export_core/model/shapes.py
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Literal

from ..ir import EmitAttrs

if TYPE_CHECKING:
    from ..shapes import ShapeContributor, ShapeMode

ShapeKind = Literal["IndexedTriangleSet", "NurbsCurve"]


class ShapeVariant(StrEnum):
    """Disambiguator for synthetic shapes that don't map 1:1 to a datablock."""

    NORMAL = "NORMAL"
    MERGE_CHILDREN = "MERGE_CHILDREN"
    MERGE_GROUP = "MERGE_GROUP"


@dataclass(frozen=True, slots=True)
class ShapeKey:
    kind: ShapeKind
    data_ptr: int  # mesh/curve datablock pointer
    object_ptr: int  # object pointer (for modifier-applied shapes)
    apply_modifiers: bool
    # Only used as part of the table key (caching/dedup) so synthetic shapes
    # (which often have data_ptr=0) don't collide with each other.
    variant: ShapeVariant = ShapeVariant.NORMAL
    merge_group_index: int | None = None

    # Optional material slot name signature used for NORMAL shapes when exporting Subset@materialSlotName
    # to ensure e.g. linked duplicates with different slot names get unique ShapeEntries.
    slot_name_signature: tuple[str | None, ...] | None = None


@dataclass(slots=True)
class ShapeEntry:
    id: int
    key: ShapeKey
    name: str
    mode: "ShapeMode"
    contributors: list["ShapeContributor"] = field(default_factory=list)
    attrs: EmitAttrs = field(default_factory=EmitAttrs)

    want_generic_value01: bool = False  # MergeChildren "g"
    want_bind_index: bool = False  # MergeGroup / skinned mesh "bi"

    def enable_generic_value01(self) -> None:
        self.want_generic_value01 = True
        self.attrs.children.setdefault("Vertices", {})["generic"] = True

    def enable_bind_index(self) -> None:
        self.want_bind_index = True
        self.attrs.children.setdefault("Vertices", {})["singleblendweights"] = True
