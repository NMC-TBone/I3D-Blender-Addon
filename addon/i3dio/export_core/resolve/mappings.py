# i3dio/export_core/resolve/mappings.py
from __future__ import annotations

from ..ctx import ExportContext
from ..ir import NodeKind, SceneNode


def finalize_i3d_mapping_for_node(ctx: ExportContext, node: SceneNode) -> None:
    """
    Tag nodes that should be included in i3dMappings export.

    Stores:
      node.attrs["i3d_mapping"] = True
      node.attrs["i3d_mapping_name"] = "..." (optional)
    """
    ref = node.blender_ref
    try:
        mapping_pg = ref.i3d_mapping
    except AttributeError:
        return
    if not mapping_pg.is_mapped:
        return
    if node.kind == NodeKind.ARMATURE and ref.i3d_attributes.collapse_armature:
        ctx.node_reporter(node, "i3dMappings").debug("Collapsed armature is not mapped")
        return  # collapsed armatures must not be mapped

    node.attrs["i3d_mapping"] = True
    mapping_name = (mapping_pg.mapping_name or node.name).strip()
    node.attrs["i3d_mapping_name"] = mapping_name
    ctx.node_reporter(node, "i3dMappings").debug("Marked for mapping (name=%r)", mapping_name)
