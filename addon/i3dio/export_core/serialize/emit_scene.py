# i3dio/export_core/serialize/emit_scene.py
from __future__ import annotations

import math
from typing import TYPE_CHECKING

import mathutils

from ...utility import isclose_any
from ...xml_i3d import SubElementA, write_attribute
from .xml_attrs import write_child_elements, write_node_attributes

if TYPE_CHECKING:
    from ..ctx import ExportContext
    from ..ir import SceneNode

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
        write_attribute(elem, "translation", t_scaled)

    # Rotation (degrees)
    r = matrix_local_export.to_euler("XYZ")
    if not isclose_any(r, _ZERO_EULER_XYZ):
        r_deg = (math.degrees(r.x), math.degrees(r.y), math.degrees(r.z))
        write_attribute(elem, "rotation", r_deg)

    # Scale
    if matrix_local_export.is_negative:
        ctx.node_reporter(node).warning(
            "Negative scale detected (not supported by GIANTS Engine); scale will be omitted (defaults to 1 1 1)."
        )
        return

    s = matrix_local_export.to_scale()
    if not isclose_any(s, _ONE3):
        write_attribute(elem, "scale", (s.x, s.y, s.z))


def emit_scene(ctx: ExportContext, scene_elem) -> None:
    def emit_node(node_id: int, parent_elem) -> None:
        node = ctx.ir.scene_nodes[node_id]

        if not node.emit:
            for child_id in ctx.ir.emitted_child_ids(node_id):
                emit_node(child_id, parent_elem)
            return

        elem = SubElementA(parent_elem, node.kind.value, {"name": node.name, "nodeId": node.id})
        write_node_attributes(elem=elem, node=node)
        write_child_elements(parent_elem=elem, emit_attrs=node.attrs)
        _write_transform(ctx, elem, node)

        for child_id in ctx.ir.emitted_child_ids(node_id):
            emit_node(child_id, elem)

    ctx.reporter("emit_scene").info("Emitting scene with %d root nodes", len(ctx.ir.emitted_child_ids(None)))
    for root_id in ctx.ir.emitted_child_ids(None):
        ctx.node_reporter(ctx.ir.scene_nodes[root_id]).debug("Emitting scene root node")
        emit_node(root_id, scene_elem)
