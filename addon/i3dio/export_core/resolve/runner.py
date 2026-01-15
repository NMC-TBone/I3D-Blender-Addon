# i3dio/export_core/resolve/runner.py
from __future__ import annotations

from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass
from time import perf_counter
from typing import TYPE_CHECKING, Callable

from .armatures import resolve_armatures
from .child_of_constraint import resolve_bone_childof
from .files import resolve_files
from .kinds import resolve_kind_for_node
from .mappings import collect_i3d_mappings
from .materials import resolve_material_entries
from .matrices import resolve_matrices
from .names import finalize_name_for_node
from .properties import resolve_properties
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
    from ..ir import SceneNode
    from ..reporting import Reporter


PassFn = Callable[["ExportContext"], None]
NodePassFn = Callable[["ExportContext", "SceneNode"], None]


def per_node(fn: NodePassFn, *, emitted_only: bool = False) -> PassFn:
    """Adapt a (ctx, node) pass into a (ctx) pass."""

    def run(ctx: ExportContext) -> None:
        for node in ctx.ir.iter_nodes(emitted_only=emitted_only):
            fn(ctx, node)

    run.__name__ = getattr(fn, "__name__", "per_node")
    return run


@dataclass(frozen=True, slots=True)
class ResolvePass:
    name: str
    run: PassFn


@dataclass(frozen=True, slots=True)
class ResolvePhase:
    name: str
    passes: tuple[ResolvePass, ...]


@contextmanager
def _timed(rep: Reporter, label: str):
    t0 = perf_counter()
    try:
        yield
    finally:
        rep.debug("%s: %.2f ms", label, (perf_counter() - t0) * 1000.0)


def resolve_all(ctx: ExportContext) -> None:
    rep = ctx.reporter("resolve")
    rep.debug("Resolving %d scene nodes", len(ctx.ir.scene_nodes))

    for phase in _PHASES:
        rep.debug("Resolve phase: %s", phase.name)
        for p in phase.passes:
            label = f"{phase.name}.{p.name}"
            with _timed(rep, label):
                try:
                    p.run(ctx)
                except Exception:
                    rep.error("Resolve pass failed: %s", label)
                    raise

    _log_summary(ctx, rep)


def _finalize_shapes_and_materials(ctx: ExportContext) -> None:
    # Shape build & materialIds must run before material resolve and shape vertex reqs after material resolve
    valid_shapes = resolve_shapes_build(ctx)
    finalize_shape_material_ids(ctx, valid_shapes)
    resolve_material_entries(ctx)
    resolve_shape_vertex_requirements(ctx, valid_shapes)


_PHASES: tuple[ResolvePhase, ...] = (
    ResolvePhase(
        "basics",
        (
            ResolvePass("kinds", per_node(resolve_kind_for_node)),
            ResolvePass("names", per_node(finalize_name_for_node)),
        ),
    ),
    ResolvePhase(
        "structure",
        (
            ResolvePass("armatures", resolve_armatures),
            ResolvePass("child_of_constraints", resolve_bone_childof),
            ResolvePass("merge_children", resolve_merge_children),
            ResolvePass("merge_groups", resolve_merge_groups),
            ResolvePass("skinned_meshes", resolve_skinned_meshes),
            ResolvePass("shape_links", resolve_shape_links),
            ResolvePass("bounding_volumes", resolve_bounding_volumes),
        ),
    ),
    ResolvePhase(
        "properties",
        (ResolvePass("node_properties", per_node(resolve_properties)),),
    ),
    ResolvePhase(
        "finalize",
        (ResolvePass("build_shapes_then_materials_then_reqs", _finalize_shapes_and_materials),),
    ),
    ResolvePhase(
        "final",
        (
            ResolvePass("matrices", resolve_matrices),
            ResolvePass("mappings", collect_i3d_mappings),
            ResolvePass("files", resolve_files),
        ),
    ),
)


def _log_summary(ctx: ExportContext, rep: Reporter) -> None:
    kinds = Counter(n.kind for n in ctx.ir.iter_nodes(emitted_only=True))
    rep.debug(
        "Resolve summary: emitted=%d/%d mapped=%d kinds=%s",
        sum(kinds.values()),
        len(ctx.ir.scene_nodes),
        len(ctx.ir.index.mapping_id_by_node_id),
        {k.name: v for k, v in kinds.items()},
    )
