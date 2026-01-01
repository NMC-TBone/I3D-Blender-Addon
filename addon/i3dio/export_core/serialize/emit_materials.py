# i3dio/export_core/serialize/emit_materials.py
from __future__ import annotations

from typing import TYPE_CHECKING

from ... import xml_i3d

if TYPE_CHECKING:
    from ..ctx import ExportContext


def emit_materials(ctx: "ExportContext", materials_elem) -> None:
    for m in ctx.materials.entries():
        mat_elem = xml_i3d.SubElement(materials_elem, "Material", {"name": m.key.export_name, "materialId": str(m.id)})
        for k, v in m.xml.node.items():
            xml_i3d.write_attribute(mat_elem, k, v)

        for child_name, child_attrs in m.xml.children.items():
            child_elem = xml_i3d.SubElement(mat_elem, child_name)
            for k, v in child_attrs.items():
                xml_i3d.write_attribute(child_elem, k, v)
