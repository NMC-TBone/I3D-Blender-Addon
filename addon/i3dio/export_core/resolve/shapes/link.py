# i3dio/export_core/resolve/shapes.py
import bpy

from ...ctx import ExportContext
from ...ir import NodeKind, SceneNode


def resolve_shape_link(ctx: ExportContext, node: SceneNode) -> None:
    ref = node.blender_ref
    if node.kind != NodeKind.SHAPE or not isinstance(ref, bpy.types.Object):
        return
    if "shapeId" in node.xml.node or not isinstance(ref.data, bpy.types.Mesh):
        return  # already resolved or not a mesh
    node.xml.node["shapeId"] = ctx.shapes.get_or_add_mesh(ref)
