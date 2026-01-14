from __future__ import annotations

# Front door for shape-related resolve passes.
from ..shapes.resolve.assemble import finalize_shape_material_ids, resolve_shapes_build
from ..shapes.resolve.bounding_volume import resolve_bounding_volumes
from ..shapes.resolve.link import resolve_shape_links
from ..shapes.resolve.merge_children import resolve_merge_children
from ..shapes.resolve.merge_group import resolve_merge_groups
from ..shapes.resolve.skinned_mesh import resolve_skinned_meshes
from ..shapes.resolve.vertex_requirements import resolve_shape_vertex_requirements

__all__ = [
    "finalize_shape_material_ids",
    "resolve_bounding_volumes",
    "resolve_merge_children",
    "resolve_merge_groups",
    "resolve_skinned_meshes",
    "resolve_shape_links",
    "resolve_shapes_build",
    "resolve_shape_vertex_requirements",
]
