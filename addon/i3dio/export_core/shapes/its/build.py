# i3dio/export_core/shapes/its/build.py
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from . import BuiltITS, ItsContributorStream
from .extract_contrib import extract_contrib_its
from .subsets import build_indices_and_subsets

if TYPE_CHECKING:
    from ...ctx import ExportContext
    from ...tables.shapes import ShapeEntry


def build_indexed_triangle_set(ctx: "ExportContext", entry: ShapeEntry) -> BuiltITS | None:
    """
    Build an IndexedTriangleSet

    Uses loop-domain vertices (no welding), and groups triangle indices into Subsets by material.
    Single builder for:
    - NORMAL (1 contributor)
    - MERGE_CHILDREN_GENERIC (N contributors + g)
    - MERGE_GROUP (N contributors; later adds bind info)
    - SKINNED_MESH (later)
    """
    if not entry.contributors:
        return None  # No contributors

    vattrs = entry.xml.children.get("Vertices", {})
    want_g = vattrs.get("generic", False)
    want_bi = vattrs.get("singleblendweights", False)

    contrib_streams: list[ItsContributorStream] = []
    for contrib in entry.contributors:
        stream = extract_contrib_its(ctx, contrib, want_g=want_g, want_bi=want_bi)
        if stream is not None:
            contrib_streams.append(stream)
    if not contrib_streams:
        return None  # No valid mesh data

    max_uv = min(max((len(s.uvs) for s in contrib_streams), default=0), 4)

    total_loops = sum(s.loop_count for s in contrib_streams)
    total_tris = sum(int(s.tri_loops.shape[0]) for s in contrib_streams)
    if total_loops <= 0 or total_tris <= 0:
        return None  # No geometry

    positions = np.empty((total_loops, 3), dtype=np.float32)
    normals = np.empty((total_loops, 3), dtype=np.float32)
    uvs_out = [np.empty((total_loops, 2), dtype=np.float32) for _ in range(max_uv)]

    g_out = np.empty((total_loops,), dtype=np.float32) if want_g else None
    bi_out = np.empty((total_loops,), dtype=np.int32) if want_bi else None

    tri_loops_all = np.empty((total_tris, 3), dtype=np.int32)
    tri_mat_id_all = np.empty((total_tris,), dtype=np.int32)

    v_offset = 0
    t_offset = 0

    for s in contrib_streams:
        lc = int(s.loop_count)
        tc = int(s.tri_loops.shape[0])

        vs = slice(v_offset, v_offset + lc)
        positions[vs] = s.positions
        normals[vs] = s.normals

        # UVs: repeat last if missing, or zero if none
        if max_uv:
            if s.uvs:
                last = s.uvs[-1]
                for li in range(max_uv):
                    src = s.uvs[li] if li < len(s.uvs) else last
                    uvs_out[li][vs] = src
            else:
                for li in range(max_uv):
                    uvs_out[li][vs] = 0.0

        if want_g and g_out is not None:
            g_out[vs] = 0.0 if s.generic_value01 is None else s.generic_value01

        if want_bi and bi_out is not None:
            bi_out[vs] = 0 if s.bind_idx is None else s.bind_idx

        ts = slice(t_offset, t_offset + tc)
        tri_loops_all[ts] = s.tri_loops + np.int32(v_offset)
        tri_mat_id_all[ts] = s.tri_mat_id

        v_offset += lc
        t_offset += tc

    indices, subsets, material_ids = build_indices_and_subsets(tri_loops_all, tri_mat_id_all, total_loops)
    if indices.size == 0 or (indices.size % 3) != 0:
        return None

    return BuiltITS(
        name=entry.name,
        shape_id=entry.id,
        positions=positions,
        normals=normals,
        indices=indices,
        subsets=subsets,
        material_ids=material_ids,
        uvs=uvs_out,
        g=g_out,
        bi=bi_out,
        xml=entry.xml,
    )
