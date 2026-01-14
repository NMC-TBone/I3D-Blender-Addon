from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import bpy

from ..ir import EmitAttrs


@dataclass(frozen=True, slots=True)
class MaterialKey:
    material_ptr: int  # 0 for None/export side only
    export_name: str  # final Material@name (slot override or datablock name)


@dataclass(slots=True)
class MaterialEntry:
    id: int
    key: MaterialKey
    blender_material: bpy.types.Material | None
    attrs: EmitAttrs = field(default_factory=EmitAttrs)
    extra_children: list[tuple[str, dict[str, Any]]] = field(default_factory=list)

    def requires_tangents(self) -> bool:
        """Return True if tangent export is required for this material."""
        if (mat := self.blender_material) is None:
            return False
        req_attrs = mat.i3d_attributes.required_vertex_attributes
        return "Normalmap" in self.attrs.children or any(req.name == "tangent" for req in req_attrs)

    def requires_vcol(self) -> bool:
        """Return True if this material requires vertex colors."""
        if (mat := self.blender_material) is None:
            return False
        return any("color" in attr.name.lower() for attr in mat.i3d_attributes.required_vertex_attributes)

    def get_slot_name(self) -> str | None:
        """Return the optional materialSlotName (or None if disabled)."""
        if (mat := self.blender_material) is None:
            return None
        if mat.i3d_attributes.use_material_slot_name:
            return mat.i3d_attributes.material_slot_name or mat.name
        return None
