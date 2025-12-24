# i3dio/export_core/resolve/mappings.py
from __future__ import annotations

from ..ctx import ExportContext
from ..ir import NodeKind


def finalize_i3d_mappings(ctx: ExportContext) -> None:
    """
    Tag nodes that should be included in i3dMappings export.

    Stores:
      node.attrs["i3d_mapping"] = True
      node.attrs["i3d_mapping_name"] = "..." (optional)
    """
    for node in ctx.ir.scene_nodes.values():
        if not node.emit:
            continue  # never map nodes that don't exist in the exported Scene

        ref = node.blender_ref

        # Default: only things that actually have the propertygroup can opt in.
        mapping_pg = getattr(ref, "i3d_mapping", None)
        if mapping_pg is None:
            continue

        if not getattr(mapping_pg, "is_mapped", False):
            continue

        # Future rule: collapsed armature objects must not be mapped
        if node.kind == NodeKind.ARMATURE:
            attrs_pg = getattr(ref, "i3d_attributes", None)
            if attrs_pg and getattr(attrs_pg, "collapse_armature", False):
                continue

        node.attrs["i3d_mapping"] = True
        mapping_name = getattr(mapping_pg, "mapping_name", "") or ""
        if mapping_name:
            node.attrs["i3d_mapping_name"] = mapping_name
