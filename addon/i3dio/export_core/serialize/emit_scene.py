# i3dio/export_core/serialize/emit_scene.py
from __future__ import annotations

import math
from typing import TYPE_CHECKING

import mathutils

from ... import xml_i3d
from ...utility import near_one3, near_zero_euler, near_zero_vec
from ..ir import node_emit_tag

if TYPE_CHECKING:
    from ..ctx import ExportContext


def _write_transform(ctx: ExportContext, elem, local_export: mathutils.Matrix | None) -> None:
    """local_export is expected to already be in EXPORT space."""
    if local_export is None:
        return

    m = local_export

    # Translation (scaled)
    t = m.to_translation()
    if not near_zero_vec(t):
        t_scaled = (t.x * ctx.unit_scale, t.y * ctx.unit_scale, t.z * ctx.unit_scale)
        xml_i3d.write_attribute(elem, "translation", "{0:.6g} {1:.6g} {2:.6g}".format(*t_scaled))

    # Rotation (degrees)
    r = m.to_euler("XYZ")
    if not near_zero_euler(r):
        r_deg = (math.degrees(r.x), math.degrees(r.y), math.degrees(r.z))
        xml_i3d.write_attribute(elem, "rotation", "{0:.6g} {1:.6g} {2:.6g}".format(*r_deg))

    # Scale
    if m.is_negative:
        # optional: ctx.messages.warning(...) later
        return

    s = m.to_scale()
    if not near_one3(s):
        xml_i3d.write_attribute(elem, "scale", "{0:.6g} {1:.6g} {2:.6g}".format(s.x, s.y, s.z))


def emit_scene(ctx: ExportContext, scene_elem) -> None:
    def emit_node(node_id: int, parent_elem) -> None:
        node = ctx.ir.scene_nodes[node_id]

        elem = xml_i3d.SubElement(parent_elem, node_emit_tag(node).value, {"name": node.name, "nodeId": str(node.id)})
        for k, v in node.xml.node.items():
            xml_i3d.write_attribute(elem, k, v)

        _write_transform(ctx, elem, node.matrix_local_export)

        for child_id in node.children:
            emit_node(child_id, elem)

    for root_id in ctx.ir.roots:
        emit_node(root_id, scene_elem)
