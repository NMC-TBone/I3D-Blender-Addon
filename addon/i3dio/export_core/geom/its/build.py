# i3dio/export_core/geom/its/build.py
from __future__ import annotations

from collections import OrderedDict
from dataclasses import replace

import bpy
import numpy as np

from ...ctx import ExportContext
from ...data.shapes.table import ShapeEntry  # your table entry type (contributors etc)
from ...ir import XmlBuckets
from ..mesh.evaluated_mesh import evaluated_mesh_for_export, free_evaluated_mesh
from .built import BuiltITS, BuiltSubset
from .material_resolve import choose_fallback_material_id, safe_material_id_for_triangle


def _slot_materials_from_evaluated(ev_obj: bpy.types.Object, mesh: bpy.types.Mesh) -> list[bpy.types.Material | None]:
    # Prefer object slots (respects per-object overrides / Link:Object use-cases)
    slots = ev_obj.material_slots
    if slots and len(slots) > 0:
        return [s.material for s in slots]
    # Fallback: mesh materials list
    return list(mesh.materials)


def build_indexed_triangle_set_normal(ctx: ExportContext, entry: ShapeEntry) -> BuiltITS:
    """
    Build an IndexedTriangleSet for a NORMAL (single contributor) mesh.

    Uses loop-domain vertices (no welding), and groups triangle indices into Subsets by material.
    """
    assert entry.contributors, "NORMAL shape entry must have at least one contributor"
    contrib = entry.contributors[0]
    obj = contrib.obj
    assert isinstance(obj, bpy.types.Object) and obj.type == "MESH"
    assert isinstance(obj.data, bpy.types.Mesh)

    # Start with xml buckets coming from ShapeEntry (ITS attrs live in entry.xml.node,
    # Vertices attrs live in entry.xml.children['Vertices']).
    built = BuiltITS(name=entry.name, shape_id=entry.id, xml=entry.xml)

    warned: set[str] = set()

    ev_obj, mesh = evaluated_mesh_for_export(ctx, obj, reference_frame=contrib.reference_frame)
    try:
        num_loops = len(mesh.loops)
        num_tris = len(mesh.loop_triangles)
        if num_loops == 0 or num_tris == 0:
            return built  # empty mesh => empty ITS

        # ---- vertex stream: loops ----
        loop_vert_idx = np.empty(num_loops, dtype=np.int32)
        mesh.loops.foreach_get("vertex_index", loop_vert_idx)

        positions = np.empty((len(mesh.vertices), 3), dtype=np.float32)
        mesh.vertices.foreach_get("co", positions.ravel())
        loop_positions = positions[loop_vert_idx]  # (num_loops, 3)

        normals = np.empty((num_loops, 3), dtype=np.float32)
        mesh.loops.foreach_get("normal", normals.ravel())

        uv0 = None
        if mesh.uv_layers:
            uv_layer = mesh.uv_layers.active or mesh.uv_layers[0]
            uv0 = np.empty((num_loops, 2), dtype=np.float32)
            uv_layer.data.foreach_get("uv", uv0.ravel())

        # ---- triangles: loop indices (reference Vertices directly) ----
        tri_loops = np.empty(num_tris * 3, dtype=np.int32)
        mesh.loop_triangles.foreach_get("loops", tri_loops)
        tri_loops = tri_loops.reshape(num_tris, 3)

        # ---- per-triangle material index ----
        tri_poly = np.empty(num_tris, dtype=np.int32)
        mesh.loop_triangles.foreach_get("polygon_index", tri_poly)

        poly_mat = np.empty(len(mesh.polygons), dtype=np.int32)
        mesh.polygons.foreach_get("material_index", poly_mat)

        tri_mat_idx = poly_mat[tri_poly]  # (num_tris,)

        # Slot-material mapping + fallback rule
        slot_materials = _slot_materials_from_evaluated(ev_obj, mesh)
        fallback_id = choose_fallback_material_id(ctx, slot_materials=slot_materials)

        # ---- group triangles by material_id in first-seen order ----
        tris_by_mat: "OrderedDict[int, list[int]]" = OrderedDict()

        for t in range(num_tris):
            mat_id = safe_material_id_for_triangle(
                ctx,
                obj_name=obj.name,
                slot_materials=slot_materials,
                mat_idx=int(tri_mat_idx[t]),
                fallback_id=fallback_id,
                warned=warned,
            )

            lst = tris_by_mat.get(mat_id)
            if lst is None:
                lst = []
                tris_by_mat[mat_id] = lst
            # append the 3 indices
            tri = tri_loops[t]
            lst.extend((int(tri[0]), int(tri[1]), int(tri[2])))

        # ---- fill BuiltITS buffers ----
        built.positions = [tuple(map(float, p)) for p in loop_positions]
        built.normals = [tuple(map(float, n)) for n in normals]
        if uv0 is not None:
            built.uv0 = [tuple(map(float, uv)) for uv in uv0]

        # indices concatenated by subset order
        built.indices = []
        built.subsets = []
        built.material_ids = []

        first_index = 0
        total_vertices = num_loops
        for mat_id, idx_stream in tris_by_mat.items():
            num_indices = len(idx_stream)
            built.indices.extend(idx_stream)
            built.subsets.append(
                BuiltSubset(
                    first_index=first_index,
                    num_indices=num_indices,
                    first_vertex=0,
                    num_vertices=total_vertices,
                    material_id=mat_id,
                )
            )
            built.material_ids.append(mat_id)
            first_index += num_indices

        return built

    finally:
        free_evaluated_mesh(ev_obj)
