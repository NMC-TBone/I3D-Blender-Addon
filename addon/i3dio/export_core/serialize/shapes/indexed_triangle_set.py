# i3dio/export_core/serialize/shapes/indexed_triangle_set.py
from __future__ import annotations

from typing import TYPE_CHECKING

from .... import xml_i3d
from ...ctx import ExportContext

if TYPE_CHECKING:
    from ...geom.its.built import BuiltITS


def emit_indexed_triangle_set(ctx: ExportContext, shapes_elem, built: "BuiltITS") -> None:
    assert len(built.indices) % 3 == 0
    assert built.uv0 is None or len(built.uv0) == len(built.positions)
    assert built.normals is None or len(built.normals) == len(built.positions)
    assert built.g is None or len(built.g) == len(built.positions)
    # Base ITS attributes
    its_attrs: dict[str, object] = {"name": built.name, "shapeId": built.shape_id}
    # Extra ITS attrs from buckets (if any)
    its_attrs.update(built.xml.node)

    its_elem = xml_i3d.SubElement(shapes_elem, "IndexedTriangleSet", {})
    for k, v in its_attrs.items():
        xml_i3d.write_attribute(its_elem, k, v)

    normals = built.normals
    uv0 = built.uv0
    g = built.g

    # ---- Vertices ----
    v_attrs: dict[str, object] = {"count": len(built.positions)}
    if normals is not None:
        v_attrs["normal"] = True
    if uv0 is not None:
        v_attrs["uv0"] = True
    v_attrs.update(built.xml.children.get("Vertices", {}))

    verts_elem = xml_i3d.SubElement(its_elem, "Vertices", {})
    for k, v in v_attrs.items():
        xml_i3d.write_attribute(verts_elem, k, v)

    for i, p in enumerate(built.positions):
        v = xml_i3d.SubElement(verts_elem, "v", {})
        xml_i3d.write_attribute(v, "p", p)
        if normals is not None:
            xml_i3d.write_attribute(v, "n", normals[i])
        if uv0 is not None:
            xml_i3d.write_attribute(v, "t0", uv0[i])
        if g is not None:
            # Merge children attribute 'g' into per-vertex 'g' attribute
            xml_i3d.write_attribute(v, "g", float(g[i]))

    # ---- Triangles ----
    tri_count = len(built.indices) // 3
    tris_elem = xml_i3d.SubElement(its_elem, "Triangles", {})
    xml_i3d.write_attribute(tris_elem, "count", tri_count)

    idx = built.indices
    for t in range(tri_count):
        a, b, c = idx[t * 3 + 0], idx[t * 3 + 1], idx[t * 3 + 2]
        te = xml_i3d.SubElement(tris_elem, "t", {})
        xml_i3d.write_attribute(te, "vi", (a, b, c))

    # ---- Subsets ----
    subsets_elem = xml_i3d.SubElement(its_elem, "Subsets", {})
    xml_i3d.write_attribute(subsets_elem, "count", len(built.subsets))

    for s in built.subsets:
        se = xml_i3d.SubElement(subsets_elem, "Subset", {})
        xml_i3d.write_attribute(se, "firstIndex", s.first_index)
        xml_i3d.write_attribute(se, "numVertices", s.num_vertices)
        xml_i3d.write_attribute(se, "firstVertex", s.first_vertex)
        xml_i3d.write_attribute(se, "numIndices", s.num_indices)
