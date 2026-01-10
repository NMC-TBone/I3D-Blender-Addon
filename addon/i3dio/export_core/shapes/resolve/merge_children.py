# i3dio/export_core/shapes/resolve/merge_children.py
from __future__ import annotations

from typing import TYPE_CHECKING, Iterable

import bpy
import mathutils

from ....utility import sort_blender_objects_by_outliner_ordering
from ...ir import NodeKind, SourceKind, set_kind
from ...model.shapes import ShapeMode
from .. import ShapeContributor

if TYPE_CHECKING:
    from ...ctx import ExportContext

# Maximum index value for `mergeChildren` objects, used to normalize
# generic values (generic_value01) for shaders. This constant is critical for:
# - Calculating normalized indices for motion paths or animations (e.g., vertex animation textures).
# - Controlling visibility of elements via the `hideByIndex` shader parameter.
# NOTE: The value must match the expected range in the shaders (e.g., [0..32767]).
_MAX_G = 32767
# Difference between Merge Group and Merge Children:
# Merge Group collect multiple meshes which are all referenced (and keeps its location) in the scene graph
# Merge Children collects the children meshes of the "root" and "root" mesh is not included in the IndexedTriangleSet.
# Merge Children is used to merge all children meshes of a single object, which are not referenced in the scene graph.


def resolve_merge_children(ctx: "ExportContext") -> None:
    """
    Apply MergeChildren feature for roots collected during traversal.

    Behavior:
    - Root becomes a Scene <Shape> (gets shapeId).
    - Root object's own mesh is NOT included in merged shape geometry.
    - All mesh descendants of each top-level child are merged into one ShapeEntry.
    - Each top-level child subtree gets a distinct 'g' bucket (g_idx / 32767), incremented by interpolation_steps.
    - Descendants have NO IR nodes (traversal stopped), so only geometry is produced.
    - reference_frame:
        apply_transforms=True  -> root frame
        apply_transforms=False -> top-level child frame
    """
    rep = ctx.reporter("merge_children")

    for root_id in ctx.ir.index.merge_children_roots:
        node = ctx.ir.scene_nodes[root_id]
        if not node.emit or node.source_kind is not SourceKind.OBJECT:
            continue
        obj = node.obj

        apply_transforms = bool(obj.i3d_merge_children.apply_transforms)
        steps = int(obj.i3d_merge_children.interpolation_steps)

        # Collect contributors
        contributors = _collect_contributors(obj, apply_transforms=apply_transforms, steps=steps)

        if not contributors:
            rep.warning("[%s] MergeChildren enabled but no child meshes found; exporting as regular Shape", obj.name)
            # Let normal shape logic handle it later (do not create ShapeEntry here).
            continue

        # Create synthetic merged shape entry
        entry = ctx.shapes.add_merge_shape(root_obj=obj, name=obj.name, mode=ShapeMode.MERGE_CHILDREN)
        entry.enable_generic_value01()
        for mesh_obj, ref_frame, g in contributors:
            entry.contributors.append(ShapeContributor(mesh_obj, ref_frame, generic_value01=g))

        # Root becomes a Shape in Scene and points at shapeId
        set_kind(node, NodeKind.SHAPE)
        # set_kind ensures _shape exists, so safe to use property
        node.shape.shape_id = entry.id

        rep.debug("[%s] MergeChildren shapeId=%d contributors=%d", obj.name, entry.id, len(entry.contributors))


def _collect_contributors(
    root_obj: bpy.types.Object, *, apply_transforms: bool, steps: int
) -> list[tuple[bpy.types.Object, mathutils.Matrix, float]]:
    """Returns list of (mesh_obj, reference_frame, generic_value01). Root mesh is excluded."""
    root_world = root_obj.matrix_world.copy()
    out: list[tuple[bpy.types.Object, mathutils.Matrix, float]] = []

    g_idx = 0
    for top_child in sort_blender_objects_by_outliner_ordering(root_obj.children):
        g = min(g_idx, _MAX_G) / _MAX_G
        ref_frame = root_world if apply_transforms else top_child.matrix_world.copy()

        for mesh_obj in _iter_mesh_objects_recursive(top_child):
            out.append((mesh_obj, ref_frame, g))

        g_idx += steps

    return out


def _iter_mesh_objects_recursive(obj: bpy.types.Object) -> Iterable[bpy.types.Object]:
    if obj.type == 'MESH':
        yield obj
    for ch in obj.children:
        yield from _iter_mesh_objects_recursive(ch)
