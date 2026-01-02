# i3dio/export_core/resolve/runner.py
from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING

from .kinds import resolve_kind_for_node
from .mappings import finalize_i3d_mapping_for_node
from .materials import resolve_material_shading
from .matrices import resolve_matrices
from .names import finalize_name_for_node
from .properties import resolve_material_properties, resolve_properties
from .shapes import (
    finalize_shape_material_ids,
    resolve_merge_children,
    resolve_merge_groups,
    resolve_shape_links,
    resolve_shapes_build,
)

if TYPE_CHECKING:
    from ..ctx import ExportContext


def resolve_all(ctx: "ExportContext") -> None:
    """
    Apply IR resolve/finalize passes after traversal and before serialization.

    Node-local passes are run in a single loop for readability and to avoid
    sprinkling loops throughout the resolver modules.
    """
    rep = ctx.section("resolve")
    rep.debug("Resolving %d scene nodes", len(ctx.ir.scene_nodes))

    for node in ctx.ir.scene_nodes.values():
        resolve_kind_for_node(ctx, node)
        finalize_name_for_node(ctx, node)

    resolve_merge_children(ctx)
    resolve_merge_groups(ctx)
    resolve_shape_links(ctx)

    for node in ctx.ir.scene_nodes.values():
        resolve_properties(ctx, node)
        finalize_i3d_mapping_for_node(ctx, node)

    # resolve/fixups (future)
    # resolve_constraints(ctx)
    # resolve_armatures(ctx)

    resolve_shapes_build(ctx)
    finalize_shape_material_ids(ctx)

    for m in ctx.materials.entries():
        resolve_material_properties(ctx, m)
        resolve_material_shading(ctx, m)
    resolve_matrices(ctx)

    kinds = Counter(n.kind for n in ctx.ir.scene_nodes.values())
    emitted = sum(1 for n in ctx.ir.scene_nodes.values() if n.emit)
    mapped = sum(1 for n in ctx.ir.scene_nodes.values() if n.i3d_mapping)

    rep.debug(
        "Resolve summary: emitted=%d/%d mapped=%d kinds=%s",
        emitted,
        len(ctx.ir.scene_nodes),
        mapped,
        {k.name: v for k, v in kinds.items()},
    )
    ctx.files.finalize()
