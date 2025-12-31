# i3dio/export_core/shapes/its/extract_contrib.py
from __future__ import annotations

from typing import TYPE_CHECKING

import bpy
import numpy as np

from ...blender.evaluated_mesh import evaluated_mesh_for_export, free_evaluated_mesh
from .. import ShapeContributor
from . import ItsContributorStream
from .material_resolve import choose_fallback_material_id, resolve_slots

if TYPE_CHECKING:
    from ...ctx import ExportContext

MAX_UV_LAYERS = 4


def extract_contrib_its(
    ctx: "ExportContext",
    contrib: ShapeContributor,
    want_g: bool,
    want_bi: bool,
) -> ItsContributorStream | None:
    obj = contrib.obj
    if not isinstance(obj, bpy.types.Object) or obj.type != "MESH":
        return None

    ev_obj, mesh = evaluated_mesh_for_export(ctx, obj, reference_frame=contrib.reference_frame)
    warned: set[str] = set()

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

        # ---- polygon -> material index -> resolved materialId ----
        tri_poly = np.empty(num_triangles, dtype=np.int32)
        mesh.loop_triangles.foreach_get("polygon_index", tri_poly)

        poly_mat = np.empty(len(mesh.polygons), dtype=np.int32)
        mesh.polygons.foreach_get("material_index", poly_mat)

        tri_mat_idx = poly_mat[tri_poly]  # (T,)

        if ev_obj.material_slots:
            slot_materials = [s.material for s in ev_obj.material_slots]
        else:
            slot_materials = list(mesh.materials)

        tri_mat_id = np.empty(num_triangles, dtype=np.int32)
        if not slot_materials:
            fallback_id = choose_fallback_material_id(ctx, slot_materials=slot_materials)
            # common for collisions etc: no warning, just default/fallback for all tris
            tri_mat_id.fill(fallback_id if fallback_id is not None else ctx.materials.get_default_id())
        else:
            res = resolve_slots(ctx, slot_materials=slot_materials)

            valid = (tri_mat_idx >= 0) & (tri_mat_idx < len(slot_materials))
            tri_mat_id[valid] = res.slot_ids[tri_mat_idx[valid]]

            if not np.all(valid):
                tri_mat_id[~valid] = res.fallback_id if res.fallback_id is not None else ctx.materials.get_default_id()

            # warn once per object if any invalid
            empty_ref = np.any(valid) and np.any(~res.slot_has_mat[tri_mat_idx[valid]])
            oob_ref = not np.all(valid)
            if (empty_ref or oob_ref) and obj.name not in warned:
                ctx.section("materials").warning(
                    "[%s] Some triangles reference empty/out-of-bounds material slots; using fallback/default material",
                    obj.name,
                )
                warned.add(obj.name)

        # ---- merge-children g ----
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
            tri_mat_id=tri_mat_id,
            generic_value01=generic_value01,
            bind_idx=bind_idx,
        )

    finally:
        free_evaluated_mesh(ev_obj)
