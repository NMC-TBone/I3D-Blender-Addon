# export_core/serialize_i3d.py
from __future__ import annotations

import math

import bpy
import mathutils

from .. import xml_i3d
from .ctx import ExportContext
from .ir import NodeKind, SceneNode


def _is_default_vec3(v: mathutils.Vector, default: tuple[float, float, float], eps: float = 1e-8) -> bool:
    return abs(v.x - default[0]) < eps and abs(v.y - default[1]) < eps and abs(v.z - default[2]) < eps


def _compute_local_matrix(ctx: ExportContext, node: SceneNode, parent: SceneNode | None) -> mathutils.Matrix | None:
    ref = node.blender_ref
    if not isinstance(ref, bpy.types.Object):
        # collections (or unknown) -> no transform written
        return None

    if parent is None:
        return ref.matrix_world.copy()

    parent_ref = parent.blender_ref
    if isinstance(parent_ref, bpy.types.Object) and ref.parent is parent_ref:
        return ref.matrix_local.copy()

    # exporter-parent differs from blender-parent -> compute relative world
    parent_world = parent_ref.matrix_world if isinstance(parent_ref, bpy.types.Object) else mathutils.Matrix.Identity(4)
    return parent_world.inverted_safe() @ ref.matrix_world.copy()


def _write_transform(ctx: ExportContext, elem, local_m: mathutils.Matrix | None) -> None:
    if local_m is None:
        return

    # Convert to i3d basis
    m = ctx.conversion_matrix @ local_m

    # Translation (scaled by scene unit scale, like your current code)
    t = m.to_translation()
    if not _is_default_vec3(t, (0.0, 0.0, 0.0)):
        t_scaled = (t.x * ctx.unit_scale, t.y * ctx.unit_scale, t.z * ctx.unit_scale)
        xml_i3d.write_attribute(elem, "translation", "{0:.6g} {1:.6g} {2:.6g}".format(*t_scaled))

    # Rotation in degrees
    r = m.to_euler("XYZ")
    r_deg = (math.degrees(r.x), math.degrees(r.y), math.degrees(r.z))
    if not (abs(r_deg[0]) < 1e-8 and abs(r_deg[1]) < 1e-8 and abs(r_deg[2]) < 1e-8):
        xml_i3d.write_attribute(elem, "rotation", "{0:.6g} {1:.6g} {2:.6g}".format(*r_deg))

    # Scale (skip negative like old code)
    if m.is_negative:
        # you can log if you want; serializer shouldn’t crash
        return
    s = m.to_scale()
    if not _is_default_vec3(s, (1.0, 1.0, 1.0)):
        xml_i3d.write_attribute(elem, "scale", "{0:.6g} {1:.6g} {2:.6g}".format(s.x, s.y, s.z))


def write_i3d(ctx: ExportContext, filepath: str) -> None:
    # Build root structure (mirrors your old I3D __init__)
    root = xml_i3d.i3d_root_element(ctx.name)
    xml_i3d.SubElement(root, "Asset")
    xml_i3d.SubElement(root, "Files")
    xml_i3d.SubElement(root, "Materials")
    xml_i3d.SubElement(root, "Shapes")
    xml_i3d.SubElement(root, "Dynamics")
    scene_elem = xml_i3d.SubElement(root, "Scene")
    xml_i3d.SubElement(root, "Animation")
    xml_i3d.SubElement(root, "UserAttributes")

    def emit_node(node_id: int, parent_elem):
        node = ctx.ir.nodes[node_id]
        if node.kind != NodeKind.TRANSFORM_GROUP:
            return

        attrs = {"name": node.name, "nodeId": str(node.id)}
        elem = xml_i3d.SubElement(parent_elem, "TransformGroup", attrs)

        parent_node = ctx.ir.nodes[node.parent_id] if node.parent_id is not None else None
        local_m = _compute_local_matrix(ctx, node, parent_node)
        _write_transform(ctx, elem, local_m)

        for child_id in node.children:
            emit_node(child_id, elem)

    for root_id in ctx.ir.roots:
        emit_node(root_id, scene_elem)

    # Finally write to file using whatever writer you already have in xml_i3d
    xml_i3d.export_to_i3d_file(root, filepath)  # adjust to your actual function name
