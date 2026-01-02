# i3dio/export_core/serialize/emit_scene.py
from __future__ import annotations

import math
from typing import TYPE_CHECKING

import mathutils

from ... import xml_i3d
from ...utility import isclose_any
from ..ir import SceneNode, node_emit_tag

if TYPE_CHECKING:
    from ..ctx import ExportContext

_ZERO3 = mathutils.Vector((0.0, 0.0, 0.0))
_ONE3 = mathutils.Vector((1.0, 1.0, 1.0))
_ZERO_EULER_XYZ = mathutils.Euler((0.0, 0.0, 0.0), "XYZ")


def _write_transform(ctx: ExportContext, elem, node: SceneNode) -> None:
    """Writes node.matrix_local_export (already in EXPORT space) into XML attributes."""
    matrix_local_export = node.matrix_local_export
    if matrix_local_export is None:
        return
    # Translation (scaled)
    t = matrix_local_export.to_translation()
    if not isclose_any(t, _ZERO3):
        t_scaled = (t.x * ctx.unit_scale, t.y * ctx.unit_scale, t.z * ctx.unit_scale)
        xml_i3d.write_attribute(elem, "translation", "{0:.6g} {1:.6g} {2:.6g}".format(*t_scaled))

    # Rotation (degrees)
    r = matrix_local_export.to_euler("XYZ")
    if not isclose_any(r, _ZERO_EULER_XYZ):
        r_deg = (math.degrees(r.x), math.degrees(r.y), math.degrees(r.z))
        xml_i3d.write_attribute(elem, "rotation", "{0:.6g} {1:.6g} {2:.6g}".format(*r_deg))

    # Scale
    if matrix_local_export.is_negative:
        ctx.node_reporter(node).warning(
            "Negative scale detected (not supported by GIANTS Engine); scale will be omitted (defaults to 1 1 1)."
        )
        return

    s = matrix_local_export.to_scale()
    if not isclose_any(s, _ONE3):
        xml_i3d.write_attribute(elem, "scale", "{0:.6g} {1:.6g} {2:.6g}".format(*s))


def emit_scene(ctx: ExportContext, scene_elem) -> None:
    def emit_node(node_id: int, parent_elem) -> None:
        node = ctx.ir.scene_nodes[node_id]

        if not node.emit:
            for child_id in node.children:
                emit_node(child_id, parent_elem)
            return

        elem = xml_i3d.SubElement(parent_elem, node_emit_tag(node).value, {"name": node.name, "nodeId": str(node.id)})
        for k, v in node.xml.node.items():
            ctx.node_reporter(node).debug(f"SceneNode attribute: {k}={v}")
            xml_i3d.write_attribute(elem, k, v)

        for child_name, child_attrs in node.xml.children.items():
            child_elem = xml_i3d.SubElement(elem, child_name)
            for k, v in child_attrs.items():
                ctx.node_reporter(node).debug(f"SceneNode child attribute: {child_name} {k}={v}")
                xml_i3d.write_attribute(child_elem, k, v)

        _write_transform(ctx, elem, node)

        for child_id in node.children:
            emit_node(child_id, elem)

    for root_id in ctx.ir.roots:
        emit_node(root_id, scene_elem)
