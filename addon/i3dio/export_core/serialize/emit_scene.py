# i3dio/export_core/serialize/emit_scene.py
from __future__ import annotations

import math

import mathutils

from ... import xml_i3d
from ..ctx import ExportContext
from ..ir import node_emit_tag
from ..resolve.transforms import local_matrix_export


def _is_default_vec3(v: mathutils.Vector, default: tuple[float, float, float], eps: float = 1e-8) -> bool:
    return abs(v.x - default[0]) < eps and abs(v.y - default[1]) < eps and abs(v.z - default[2]) < eps


def _write_transform(ctx: ExportContext, elem, local_export: mathutils.Matrix | None) -> None:
    """
    local_export is expected to already be in EXPORT space.
    """
    if local_export is None:
        return

    m = local_export

    # Translation (scaled)
    t = m.to_translation()
    if not _is_default_vec3(t, (0.0, 0.0, 0.0)):
        t_scaled = (t.x * ctx.unit_scale, t.y * ctx.unit_scale, t.z * ctx.unit_scale)
        xml_i3d.write_attribute(elem, "translation", "{0:.6g} {1:.6g} {2:.6g}".format(*t_scaled))

    # Rotation (degrees)
    r = m.to_euler("XYZ")
    r_deg = (math.degrees(r.x), math.degrees(r.y), math.degrees(r.z))
    if not (abs(r_deg[0]) < 1e-8 and abs(r_deg[1]) < 1e-8 and abs(r_deg[2]) < 1e-8):
        xml_i3d.write_attribute(elem, "rotation", "{0:.6g} {1:.6g} {2:.6g}".format(*r_deg))

    # Scale
    if m.is_negative:
        # optional: ctx.messages.warn(...) later
        return

    s = m.to_scale()
    if not _is_default_vec3(s, (1.0, 1.0, 1.0)):
        xml_i3d.write_attribute(elem, "scale", "{0:.6g} {1:.6g} {2:.6g}".format(s.x, s.y, s.z))


def emit_scene(ctx: ExportContext, scene_elem) -> None:
    def emit_node(node_id: int, parent_elem) -> None:
        node = ctx.ir.scene_nodes[node_id]

        elem = xml_i3d.SubElement(parent_elem, node_emit_tag(node).value, {"name": node.name, "nodeId": str(node.id)})

        parent_node = ctx.ir.scene_nodes[node.parent_id] if node.parent_id is not None else None
        local_m = local_matrix_export(ctx, node, parent_node)
        _write_transform(ctx, elem, local_m)

        for child_id in node.children:
            emit_node(child_id, elem)

    for root_id in ctx.ir.roots:
        emit_node(root_id, scene_elem)
