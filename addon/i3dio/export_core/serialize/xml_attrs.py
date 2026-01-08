# i3dio/export_core/serialize/xml_attrs.py
from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from ... import xml_i3d
from ..ir import EmitAttrs

if TYPE_CHECKING:
    from ..ir import SceneNode


def write_attributes(elem, attrs: Mapping[str, object]) -> None:
    for k, v in attrs.items():
        xml_i3d.write_attribute(elem, k, v)


def write_node_attributes(*, elem, node: "SceneNode") -> None:
    """Write all node attributes including shapeId, materialIds, skinBindNodeIds, and reference data."""
    write_attributes(elem, node.attrs.node)

    # Shape attributes
    if (shape := node._shape) is not None:
        xml_i3d.write_attribute(elem, "shapeId", int(shape.shape_id))

        if shape.material_ids:
            xml_i3d.write_attribute(elem, "materialIds", ",".join(str(int(mid)) for mid in shape.material_ids))

        if shape.skin_bind_node_ids:
            xml_i3d.write_attribute(
                elem, "skinBindNodeIds", " ".join(str(int(nid)) for nid in shape.skin_bind_node_ids)
            )

    # Reference attributes
    if (ref := node._ref) is not None:
        xml_i3d.write_attribute(elem, "referenceId", int(ref.reference_id))

        if ref.child_path:
            xml_i3d.write_attribute(elem, "referenceChildPath", str(ref.child_path))

        if ref.runtime_loaded is False:
            xml_i3d.write_attribute(elem, "referenceRuntimeLoaded", False)


def write_child_elements(*, parent_elem, emit_attrs: EmitAttrs) -> None:
    for child_name, child_attrs in emit_attrs.children.items():
        child_elem = xml_i3d.SubElement(parent_elem, child_name)
        write_attributes(child_elem, child_attrs)
