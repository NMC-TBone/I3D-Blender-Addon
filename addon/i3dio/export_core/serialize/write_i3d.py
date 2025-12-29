# i3dio/export_core/serialize/write_i3d.py
from __future__ import annotations

from ... import xml_i3d
from ..ctx import ExportContext
from .emit_files import emit_files
from .emit_materials import emit_materials
from .emit_scene import emit_scene
from .shapes.emit_shapes import emit_shapes


def write_i3d(ctx: ExportContext) -> None:
    root = xml_i3d.i3d_root_element(ctx.name)

    xml_i3d.SubElement(root, "Asset")
    files_elem = xml_i3d.SubElement(root, "Files")
    emit_files(ctx, files_elem)
    mat_elem = xml_i3d.SubElement(root, "Materials")
    emit_materials(ctx, mat_elem)
    shapes_elem = xml_i3d.SubElement(root, "Shapes")
    emit_shapes(ctx, shapes_elem)

    xml_i3d.SubElement(root, "Dynamics")

    scene_elem = xml_i3d.SubElement(root, "Scene")
    emit_scene(ctx, scene_elem)

    xml_i3d.SubElement(root, "Animation")
    xml_i3d.SubElement(root, "UserAttributes")

    xml_i3d.export_to_i3d_file(root, ctx.filepath)
