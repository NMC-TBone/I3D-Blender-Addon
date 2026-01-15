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
    rep = ctx.reporter("write_i3d")
    rep.info(f"Writing I3D file to {ctx.filepath!r}")
    root = xml_i3d.i3d_root_element(ctx.name)

    xml_i3d.SubElementA(root, "Asset")  # i3dConverter.exe will overwrite this anyways....
    emit_files(ctx, xml_i3d.SubElementA(root, "Files"))
    emit_materials(ctx, xml_i3d.SubElementA(root, "Materials"))
    xml_i3d.SubElementA(root, "Shapes")

    xml_i3d.SubElementA(root, "Dynamics")

    emit_scene(ctx, xml_i3d.SubElementA(root, "Scene"))
    rep.info("Finished writing scene")

    xml_i3d.SubElementA(root, "Animation")
    xml_i3d.SubElementA(root, "UserAttributes")

    def _shapes_writer(f):
        for built in ctx.shapes.iter_built():
            write_its_stream(f, built, indent="    ")

    rep.info("Finalizing I3D file write")
    xml_i3d.export_to_i3d_file(root=root, file_path=ctx.filepath, shapes_writer=_shapes_writer)
    rep.info("I3D file write complete")
