# i3dio/export_core/resolve/runner.py
from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING

from .armatures import resolve_armatures
from .kinds import resolve_kind_for_node
from .mappings import collect_i3d_mappings
from .materials import resolve_material_shading
from .matrices import resolve_matrices
from .names import finalize_name_for_node
from .properties import resolve_material_properties, resolve_properties
from .shapes import (
    finalize_shape_material_ids,
    resolve_bounding_volumes,
    resolve_merge_children,
    resolve_merge_groups,
    resolve_shape_links,
    resolve_shape_vertex_requirements,
    resolve_shapes_build,
    resolve_skinned_meshes,
)

if TYPE_CHECKING:
    from ..ctx import ExportContext


def resolve_all(ctx: ExportContext) -> None:
    """
    Apply IR resolve/finalize passes after traversal and before serialization.

    Phases:
    1. Per-node basics (kind, name) - must run before structural transforms
    2. Structural transforms (armatures, merge groups, etc.)
    3. Per-node properties (after structure is stable)
    4. Shape/material finalization
    5. Final passes (matrices, mappings)
    """
    rep = ctx.reporter("resolve")
    rep.debug("Resolving %d scene nodes", len(ctx.ir.scene_nodes))

    # Phase 1: Node basics (kind & name resolution)
    for node in ctx.ir.scene_nodes.values():
        resolve_kind_for_node(ctx, node)
        finalize_name_for_node(ctx, node)

    # Phase 2: Structural transforms
    resolve_armatures(ctx)
    resolve_merge_children(ctx)
    resolve_merge_groups(ctx)
    resolve_skinned_meshes(ctx)
    resolve_shape_links(ctx)
    resolve_bounding_volumes(ctx)

    # Phase 3: Per-node properties (structure is now stable)
    for node in ctx.ir.scene_nodes.values():
        resolve_properties(ctx, node)

    # Phase 4: Shape & material finalization
    valid_shapes = resolve_shapes_build(ctx)
    finalize_shape_material_ids(ctx, valid_shapes)

    for m in ctx.materials.entries():
        resolve_material_properties(ctx, m)
        resolve_material_shading(ctx, m)

    resolve_shape_vertex_requirements(ctx, valid_shapes)

    # Phase 5: Final passes
    resolve_matrices(ctx)
    collect_i3d_mappings(ctx)
    ctx.files.finalize()

    # Debug summary
    kinds = Counter(n.kind for n in ctx.ir.iter_nodes(emitted_only=True))
    rep.debug(
        "Resolve summary: emitted=%d/%d mapped=%d kinds=%s",
        sum(kinds.values()),
        len(ctx.ir.scene_nodes),
        len(ctx.ir.index.mapping_id_by_node_id),
        {k.name: v for k, v in kinds.items()},
    )
