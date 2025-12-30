# i3dio/export_core/serialize/emit_materials.py
from __future__ import annotations

from typing import TYPE_CHECKING

from ... import xml_i3d

if TYPE_CHECKING:
    from ..ctx import ExportContext


def emit_materials(ctx: "ExportContext", materials_elem) -> None:
    for m in ctx.materials.entries():
        xml_i3d.SubElement(materials_elem, "Material", {"name": m.key.export_name, "materialId": str(m.id)})
