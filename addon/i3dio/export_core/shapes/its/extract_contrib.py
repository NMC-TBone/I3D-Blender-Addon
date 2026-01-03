# i3dio/export_core/shapes/its/extract_contrib.py
from __future__ import annotations

from typing import TYPE_CHECKING

import bpy
import numpy as np

from ...blender.evaluated_mesh import evaluated_mesh_for_export, free_evaluated_mesh
from .. import ShapeContributor
from . import ItsContributorStream, MaterialKeyKind
from .material_resolve import resolve_slots

if TYPE_CHECKING:
    from ...ctx import ExportContext

MAX_UV_LAYERS = 4


def extract_contrib_its(
    ctx: "ExportContext",
    contrib: ShapeContributor,
    want_g: bool,
    want_bi: bool,
    *,
    material_kind: MaterialKeyKind = MaterialKeyKind.SLOT_INDEX,
) -> ItsContributorStream | None:
    obj = contrib.obj
    if not isinstance(obj, bpy.types.Object) or obj.type != "MESH":
        return None

    ev_obj, mesh = evaluated_mesh_for_export(ctx, obj, reference_frame=contrib.reference_frame)

    try:
        num_loops = len(mesh.loops)
        num_triangles = len(mesh.loop_triangles)
        if num_loops == 0 or num_triangles == 0:
            return None

        # ---- loop -> vertex positions ----
        loop_vert_idx = np.empty(num_loops, dtype=np.int32)
        mesh.loops.foreach_get("vertex_index", loop_vert_idx)

        vert_co = np.empty((len(mesh.vertices), 3), dtype=np.float32)
        mesh.vertices.foreach_get("co", vert_co.ravel())
        positions = vert_co[loop_vert_idx]  # (L,3)

        # ---- loop normals (Blender 4.5+: loop normals are just there) ----
        normals = np.empty((num_loops, 3), dtype=np.float32)
        mesh.loops.foreach_get("normal", normals.ravel())

        # ---- uvs (0..4) ----
        uv_layers = list(mesh.uv_layers)
        if ctx.settings.get("alphabetic_uvs", False):
            uv_layers.sort(key=lambda ul: ul.name.casefold())
        uv_layers = uv_layers[:MAX_UV_LAYERS]

        uvs: list[np.ndarray] = []
        for ul in uv_layers:
            uv = np.empty((num_loops, 2), dtype=np.float32)
            ul.data.foreach_get("uv", uv.ravel())
            uvs.append(uv)

        # ---- triangles as loop indices ----
        tri_loops = np.empty(num_triangles * 3, dtype=np.int32)
        mesh.loop_triangles.foreach_get("loops", tri_loops)
        tri_loops = tri_loops.reshape(num_triangles, 3)

        # ---- polygon -> material key ----
        tri_poly = np.empty(num_triangles, dtype=np.int32)
        mesh.loop_triangles.foreach_get("polygon_index", tri_poly)

        poly_mat = np.empty(len(mesh.polygons), dtype=np.int32)
        mesh.polygons.foreach_get("material_index", poly_mat)

        tri_mat_idx = poly_mat[tri_poly]  # (T,) slot indices from mesh

        slot_materials = [s.material for s in ev_obj.material_slots] if ev_obj.material_slots else list(mesh.materials)

        # Warn once per object if triangles reference empty or out-of-bounds slots.
        valid_slot_idx: np.ndarray | None = None
        if slot_materials:
            rep = ctx.object_reporter(obj, "materials")
            valid_slot_idx = (tri_mat_idx >= 0) & (tri_mat_idx < len(slot_materials))

            bad = np.count_nonzero(~valid_slot_idx)
            if bad:
                rep.warning(
                    "%d triangles reference out-of-bounds material slots; using fallback/default material",
                    bad,
                    code="materials_slot_index_out_of_bounds",
                )

            if np.any(valid_slot_idx):
                # Detect empty slots among the indices that are in range.
                slots_is_none = np.fromiter(
                    (m is None for m in slot_materials), dtype=np.bool_, count=len(slot_materials)
                )
                if np.any(slots_is_none):
                    v_idx = tri_mat_idx[valid_slot_idx]
                    empty_bad = np.count_nonzero(slots_is_none[v_idx])
                    if empty_bad:
                        rep.warning(
                            "%d triangles reference empty material slots; using fallback/default material",
                            empty_bad,
                            code="materials_slot_is_empty",
                        )

        if material_kind == MaterialKeyKind.SLOT_INDEX:
            # NORMAL shapes: keep slot indices; per-node materialIds mapping happens in assemble.
            if not slot_materials:
                # If no materials exist at all, keep a single subset (slot 0).
                tri_mat_key = np.full((num_triangles,), 0, dtype=np.int32)
            else:
                tri_mat_key = tri_mat_idx
        else:
            # Merge shapes: resolve to global material IDs so multiple contributors
            # with different slot layouts merge correctly.
            res = resolve_slots(ctx, slot_materials=slot_materials)
            default_id = ctx.materials.get_default_id()
            fallback_id = res.fallback_id if res.fallback_id is not None else default_id

            tri_mat_key = np.empty((num_triangles,), dtype=np.int32)
            if slot_materials:
                valid = valid_slot_idx
                if valid is None:
                    valid = (tri_mat_idx >= 0) & (tri_mat_idx < len(slot_materials))
                tri_mat_key[valid] = res.slot_ids[tri_mat_idx[valid]]
                tri_mat_key[~valid] = fallback_id
            else:
                tri_mat_key.fill(fallback_id)

        # ---- merge features ----
        generic_value01 = None
        if want_g:
            generic_value01 = np.full((num_loops,), float(contrib.generic_value01 or 0.0), dtype=np.float32)

        bind_idx = None
        if want_bi:
            bind_idx = np.full((num_loops,), int(contrib.bind_index or 0), dtype=np.int32)

        return ItsContributorStream(
            obj_name=obj.name,
            loop_count=num_loops,
            positions=positions,
            normals=normals,
            uvs=uvs,
            tri_loops=tri_loops,
            tri_mat_id=tri_mat_key,
            generic_value01=generic_value01,
            bind_idx=bind_idx,
        )

    finally:
        free_evaluated_mesh(ev_obj)
