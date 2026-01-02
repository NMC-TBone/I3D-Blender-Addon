# i3dio/export_core/serialize/indexed_triangle_set_stream.py
from __future__ import annotations

from typing import TYPE_CHECKING

from ... import xml_i3d

if TYPE_CHECKING:
    from ..shapes.its import BuiltITS

CHUNK_LINES = 50_000  # number of lines to buffer before writing to file


def write_its_stream(f, built: BuiltITS, indent: str = "    ") -> None:
    positions = built.positions
    normals = built.normals
    uvs = built.uvs
    g = built.g
    bi = built.bi
    indices = built.indices

    vcount = int(positions.shape[0])
    tri_count = int(indices.shape[0] // 3)

    # <IndexedTriangleSet ...>
    its_attrs: dict[str, object] = {"name": built.name, "shapeId": built.shape_id, **built.attrs.node}
    xml_i3d.write_open_tag(f, "IndexedTriangleSet", its_attrs, indent=indent)

    # <Vertices ...>
    v_attrs: dict[str, object] = {"count": vcount, "normal": True}
    for li in range(len(uvs)):
        v_attrs[f"uv{li}"] = True
    v_attrs.update(built.attrs.children.get("Vertices", {}))
    xml_i3d.write_open_tag(f, "Vertices", v_attrs, indent=indent + "  ")

    # vertices: chunked writing
    chunk: list[str] = []
    for i in range(vcount):
        line = [f'{indent}    <v p="{xml_i3d.fmt_attr_value(positions[i])}" n="{xml_i3d.fmt_attr_value(normals[i])}"']
        for li, layer in enumerate(uvs):
            line.append(f' t{li}="{xml_i3d.fmt_attr_value(layer[i])}"')
        if g is not None:
            line.append(f' g="{float(g[i]):.9g}"')
        elif bi is not None:
            line.append(f' bi="{bi[i]:d}"')
        line.append(" />\n")
        chunk.append("".join(line))
        if len(chunk) >= CHUNK_LINES:
            f.write("".join(chunk))
            chunk.clear()
    if chunk:
        f.write("".join(chunk))
    xml_i3d.write_close_tag(f, "Vertices", indent=indent + "  ")

    # <Triangles ...>
    xml_i3d.write_open_tag(f, "Triangles", {"count": tri_count}, indent=indent + "  ")
    idx3 = indices.reshape(-1, 3)
    chunk.clear()
    for a, b, c in idx3:
        chunk.append(f'{indent}    <t vi="{int(a)} {int(b)} {int(c)}" />\n')
        if len(chunk) >= CHUNK_LINES:
            f.write("".join(chunk))
            chunk.clear()
    if chunk:
        f.write("".join(chunk))
    xml_i3d.write_close_tag(f, "Triangles", indent=indent + "  ")

    # <Subsets ...>
    xml_i3d.write_open_tag(f, "Subsets", {"count": len(built.subsets)}, indent=indent + "  ")
    for s in built.subsets:
        slot_attr = ""
        if s.material_slot_name is not None:
            escaped = xml_i3d.escape_attr(xml_i3d.fmt_attr_value(s.material_slot_name))
            slot_attr = f' materialSlotName="{escaped}"'
        f.write(
            f'{indent}    <Subset firstIndex="{s.first_index:d}" '
            f'numVertices="{s.num_vertices:d}" firstVertex="{s.first_vertex:d}" '
            f'numIndices="{s.num_indices:d}"{slot_attr} />\n'
        )
    xml_i3d.write_close_tag(f, "Subsets", indent=indent + "  ")
    # </IndexedTriangleSet>
    xml_i3d.write_close_tag(f, "IndexedTriangleSet", indent=indent)
