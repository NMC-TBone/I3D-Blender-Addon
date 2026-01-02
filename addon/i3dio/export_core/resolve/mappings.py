# i3dio/export_core/resolve/mappings.py
from __future__ import annotations

from typing import TYPE_CHECKING

from ..ir import SceneNode

if TYPE_CHECKING:
    from ..ctx import ExportContext


def finalize_i3d_mapping_for_node(ctx: "ExportContext", node: SceneNode) -> None:
    """
    Tag nodes that should be included in i3dMappings export.

        Stores:
            node.i3d_mapping = True
            node.i3d_mapping_name = "..." (optional)
    """
    if not node.emit:
        ctx.node_reporter(node, "i3dMappings").debug("Skipping unmapped unemit node")
        return  # e.g. collapsed armatures must not be mapped
    try:
        mapping_pg = node.blender_ref.i3d_mapping
    except AttributeError:
        return
    if not mapping_pg.is_mapped:
        return
    node.i3d_mapping = True
    mapping_name = (mapping_pg.mapping_name or node.name).strip()
    node.i3d_mapping_name = mapping_name
    ctx.node_reporter(node, "i3dMappings").debug("Marked for mapping (name=%r)", mapping_name)
