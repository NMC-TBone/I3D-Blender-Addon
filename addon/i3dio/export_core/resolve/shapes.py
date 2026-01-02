from __future__ import annotations

# Front door for shape-related resolve passes.
from ..shapes.resolve.assemble import finalize_shape_material_ids, resolve_shapes_build
from ..shapes.resolve.link import resolve_shape_links
from ..shapes.resolve.merge_children import resolve_merge_children
from ..shapes.resolve.merge_group import resolve_merge_groups

__all__ = [
    "finalize_shape_material_ids",
    "resolve_merge_children",
    "resolve_merge_groups",
    "resolve_shape_links",
    "resolve_shapes_build",
]
