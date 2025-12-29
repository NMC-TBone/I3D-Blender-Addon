# i3dio/export_core/geom/its/built.py
from __future__ import annotations

from dataclasses import dataclass, field

from ...ir import XmlBuckets


@dataclass(slots=True)
class BuiltSubset:
    first_index: int
    num_indices: int
    first_vertex: int
    num_vertices: int
    material_id: int


@dataclass(slots=True)
class BuiltITS:
    name: str
    shape_id: int

    positions: list[tuple[float, float, float]] = field(default_factory=list)
    normals: list[tuple[float, float, float]] = field(default_factory=list)
    uv0: list[tuple[float, float]] | None = None
    g: list[float] | None = None

    indices: list[int] = field(default_factory=list)  # flattened vi stream
    subsets: list[BuiltSubset] = field(default_factory=list)
    material_ids: list[int] = field(default_factory=list)  # in subset order

    xml: XmlBuckets = field(default_factory=XmlBuckets)
