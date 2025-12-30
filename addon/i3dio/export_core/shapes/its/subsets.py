# i3dio/export_core/shapes/its/subsets.py
from __future__ import annotations

import numpy as np

from .built import BuiltSubset


def build_indices_and_subsets(
    tri_loops: np.ndarray,  # (T,3) int32
    tri_mat_id: np.ndarray,  # (T,) int32
    total_vertices: int,
) -> tuple[np.ndarray, list[BuiltSubset], list[int]]:
    """
    Group triangles by materialId in first-seen order (stable), producing:
      - flat indices array
      - subsets
      - material_ids list (subset order)
    """
    if tri_loops.size == 0:
        return np.empty((0,), dtype=np.int32), [], []

    # materials in order of first appearance
    mats, first_idx = np.unique(tri_mat_id, return_index=True)
    order = mats[np.argsort(first_idx)]

    indices = np.empty((tri_loops.size,), dtype=np.int32)  # = 3*T
    subsets: list[BuiltSubset] = []
    material_ids: list[int] = []

    write = 0
    for mat in order:
        mask = tri_mat_id == mat
        tris = tri_loops[mask]  # (t,3)
        n = tris.size  # 3*t

        indices[write : write + n] = tris.reshape(-1)

        subsets.append(
            BuiltSubset(
                first_index=write,
                num_indices=n,
                first_vertex=0,
                num_vertices=total_vertices,
                material_id=int(mat),
            )
        )
        material_ids.append(int(mat))
        write += n

    # (Optional sanity) write should equal indices.size
    return indices, subsets, material_ids


def append_tris_by_material(
    tris_by_mat: dict[int, list[int]],
    *,
    tri_loops: np.ndarray,  # (T,3) int32
    tri_mat_id: np.ndarray,  # (T,) int32
    vertex_offset: int,
) -> None:
    """
    Append triangle indices into tris_by_mat in first-seen material order.
    Indices are loop indices offset by vertex_offset.
    """
    num_tris = int(tri_loops.shape[0])
    for t in range(num_tris):
        mat_id = int(tri_mat_id[t])
        lst = tris_by_mat.get(mat_id)
        if lst is None:
            lst = []
            tris_by_mat[mat_id] = lst
        a, b, c = tri_loops[t]
        lst.extend((int(a) + vertex_offset, int(b) + vertex_offset, int(c) + vertex_offset))


def finalize_subsets(
    tris_by_mat: dict[int, list[int]],
    *,
    total_vertices: int,
) -> tuple[np.ndarray, list[BuiltSubset], list[int]]:
    """
    Flatten tris_by_mat to one index buffer + subsets + material_ids.
    """
    all_idx: list[int] = []
    subsets: list[BuiltSubset] = []
    material_ids: list[int] = []

    first_index = 0
    for mat_id, idx_stream in tris_by_mat.items():
        num_indices = len(idx_stream)
        all_idx.extend(idx_stream)

        subsets.append(
            BuiltSubset(
                first_index=first_index,
                num_indices=num_indices,
                first_vertex=0,
                num_vertices=total_vertices,
                material_id=int(mat_id),
            )
        )
        material_ids.append(int(mat_id))
        first_index += num_indices

    indices = np.asarray(all_idx, dtype=np.int32)
    return indices, subsets, material_ids
