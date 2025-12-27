# i3dio/export_core/resolve/runner.py
from __future__ import annotations

from collections import Counter

from ..ctx import ExportContext
from .kinds import resolve_kind_for_node
from .mappings import finalize_i3d_mapping_for_node
from .matrices import resolve_matrices
from .names import finalize_name_for_node
from .properties import resolve_properties


def resolve_all(ctx: ExportContext) -> None:
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
        if not node.emit:
            continue  # skip non-emitted nodes for other passes
        resolve_properties(ctx, node)
        finalize_i3d_mapping_for_node(ctx, node)

    # resolve/fixups (future)
    # resolve_constraints(ctx)
    # resolve_armatures(ctx)
    # resolve_instances(ctx)

    resolve_matrices(ctx)

    kinds = Counter(n.kind for n in ctx.ir.scene_nodes.values())
    emitted = sum(1 for n in ctx.ir.scene_nodes.values() if n.emit)
    mapped = sum(1 for n in ctx.ir.scene_nodes.values() if n.attrs.get("i3d_mapping"))

    rep.debug(
        "Resolve summary: emitted=%d/%d mapped=%d kinds=%s",
        emitted,
        len(ctx.ir.scene_nodes),
        mapped,
        {k.name: v for k, v in kinds.items()},
    )
