# i3dio/export_core/serialize/write_i3d.py
from __future__ import annotations

from typing import TYPE_CHECKING

from ... import xml_i3d
from .emit_files import emit_files
from .emit_materials import emit_materials
from .emit_scene import emit_scene
from .indexed_triangle_set_stream import write_its_stream

if TYPE_CHECKING:
    from ..ctx import ExportContext


def write_i3d(ctx: ExportContext) -> None:
    ctx.reporter().info(f"Writing I3D file to '{ctx.filepath}'")
    root = xml_i3d.i3d_root_element(ctx.name)

    xml_i3d.SubElement(root, "Asset")
    files_elem = xml_i3d.SubElement(root, "Files")
    emit_files(ctx, files_elem)
    mat_elem = xml_i3d.SubElement(root, "Materials")
    emit_materials(ctx, mat_elem)
    xml_i3d.SubElement(root, "Shapes")

    xml_i3d.SubElement(root, "Dynamics")

    scene_elem = xml_i3d.SubElement(root, "Scene")
    emit_scene(ctx, scene_elem)
    ctx.reporter().info("Finished writing scene")

    xml_i3d.SubElement(root, "Animation")
    xml_i3d.SubElement(root, "UserAttributes")

    def _shapes_writer(f):
        for built in ctx.shapes.iter_built():
            write_its_stream(f, built, indent="    ")

    ctx.reporter().info("Finalizing I3D file write")
    xml_i3d.export_to_i3d_file(
        root=root,
        file_path=ctx.filepath,
        shapes_writer=_shapes_writer,
        encoding="iso-8859-1",
        xml_declaration=True,
        pretty=ctx.is_dev,
        skip_indent_tags={"Shapes"},
    )
    ctx.reporter().info("I3D file write complete")
