# i3dio/export_core/serialize/xml_attrs.py
from __future__ import annotations

from collections.abc import Mapping, Sequence

from ... import xml_i3d
from ..ir import EmitAttrs, NodeReference


def write_attributes(elem, attrs: Mapping[str, object]) -> None:
    for k, v in attrs.items():
        xml_i3d.write_attribute(elem, k, v)


def write_node_attributes(
    *,
    elem,
    emit_attrs: EmitAttrs,
    material_ids: Sequence[int] | None = None,
    skin_bind_node_ids: Sequence[int] | None = None,
    reference: NodeReference | None = None,
) -> None:
    write_attributes(elem, emit_attrs.node)

    if material_ids is not None:
        xml_i3d.write_attribute(elem, "materialIds", ",".join(str(int(mid)) for mid in material_ids))

    if skin_bind_node_ids is not None:
        xml_i3d.write_attribute(elem, "skinBindNodeIds", " ".join(str(int(nid)) for nid in skin_bind_node_ids))

    if reference is not None:
        if reference.id is not None:
            xml_i3d.write_attribute(elem, "referenceId", int(reference.id))

        if reference.child_path:
            xml_i3d.write_attribute(elem, "referenceChildPath", str(reference.child_path))

        if reference.runtime_loaded is False:
            xml_i3d.write_attribute(elem, "referenceRuntimeLoaded", False)


def write_child_elements(*, parent_elem, emit_attrs: EmitAttrs) -> None:
    for child_name, child_attrs in emit_attrs.children.items():
        child_elem = xml_i3d.SubElement(parent_elem, child_name)
        write_attributes(child_elem, child_attrs)
