# i3dio/export_core/serialize/write_i3d.py
from __future__ import annotations

from ... import xml_i3d
from ..ctx import ExportContext
from .emit_scene import emit_scene


def write_i3d(ctx: ExportContext) -> None:
    root = xml_i3d.i3d_root_element(ctx.name)

    xml_i3d.SubElement(root, "Asset")
    xml_i3d.SubElement(root, "Files")
    xml_i3d.SubElement(root, "Materials")
    xml_i3d.SubElement(root, "Shapes")
    xml_i3d.SubElement(root, "Dynamics")

    scene_elem = xml_i3d.SubElement(root, "Scene")

    xml_i3d.SubElement(root, "Animation")
    xml_i3d.SubElement(root, "UserAttributes")

    emit_scene(ctx, scene_elem)

    xml_i3d.export_to_i3d_file(root, ctx.filepath)
