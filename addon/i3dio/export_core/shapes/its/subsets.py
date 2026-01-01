# i3dio/export_core/shapes/its/subsets.py
from __future__ import annotations

import numpy as np

from . import BuiltSubset


def build_indices_and_subsets(
    tri_loops: np.ndarray,  # (T,3) int32
    tri_mat_id: np.ndarray,  # (T,) int32 (material keys)
    total_vertices: int,
) -> tuple[np.ndarray, list[BuiltSubset], list[int]]:
    """
    Group triangles by material key in first-seen order (stable), producing:
      - flat indices array
      - subsets
      - material_ids list (subset order; material keys)
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
