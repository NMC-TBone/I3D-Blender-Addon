# i3dio/export_core/serialize/emit_materials.py
from __future__ import annotations

from typing import TYPE_CHECKING

from ... import xml_i3d
from .xml_attrs import write_attributes, write_child_elements

if TYPE_CHECKING:
    from ..ctx import ExportContext


def emit_materials(ctx: "ExportContext", materials_elem) -> None:
    for m in ctx.materials.entries():
        mat_elem = xml_i3d.SubElement(materials_elem, "Material", {"name": m.key.export_name, "materialId": str(m.id)})
        write_attributes(elem=mat_elem, attrs=m.attrs.node)
        write_child_elements(parent_elem=mat_elem, emit_attrs=m.attrs)

        for child_name, child_attrs in m.extra_children:
            child_elem = xml_i3d.SubElement(mat_elem, child_name)
            write_attributes(child_elem, child_attrs)
