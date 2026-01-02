# i3dio/export_core/serialize/indexed_triangle_set_stream.py
from __future__ import annotations

from typing import TYPE_CHECKING

from ... import xml_i3d

if TYPE_CHECKING:
    from ..shapes.its import BuiltITS

CHUNK_LINES = 50_000  # number of lines to buffer before writing to file


def _fmt3(v) -> str:
    return f"{float(v[0]):.6g} {float(v[1]):.6g} {float(v[2]):.6g}"


def _fmt2(v) -> str:
    return f"{float(v[0]):.6g} {float(v[1]):.6g}"


def _open_tag(f, indent: str, tag: str, attrs: dict[str, object]) -> None:
    if attrs:
        parts = [f'{k}="{xml_i3d.escape_attr(xml_i3d.fmt_attr_value(v))}"' for k, v in attrs.items()]
        f.write(f"{indent}<{tag} " + " ".join(parts) + ">\n")
    else:
        f.write(f"{indent}<{tag}>\n")


def _close_tag(f, indent: str, tag: str) -> None:
    f.write(f"{indent}</{tag}>\n")


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
    its_attrs: dict[str, object] = {"name": built.name, "shapeId": built.shape_id}
    its_attrs.update(built.xml.node)
    _open_tag(f, indent, "IndexedTriangleSet", its_attrs)

    # <Vertices ...>
    v_attrs: dict[str, object] = {"count": vcount, "normal": True}
    for li in range(len(uvs)):
        v_attrs[f"uv{li}"] = True
    v_attrs.update(built.xml.children.get("Vertices", {}))
    _open_tag(f, indent + "  ", "Vertices", v_attrs)

    # vertices: chunked writing
    chunk: list[str] = []
    for i in range(vcount):
        line = [f'{indent}    <v p="{_fmt3(positions[i])}" n="{_fmt3(normals[i])}"']
        for li, layer in enumerate(uvs):
            line.append(f' t{li}="{_fmt2(layer[i])}"')
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
    _close_tag(f, indent + "  ", "Vertices")

    # <Triangles ...>
    _open_tag(f, indent + "  ", "Triangles", {"count": tri_count})
    idx3 = indices.reshape(-1, 3)
    chunk.clear()
    for a, b, c in idx3:
        chunk.append(f'{indent}    <t vi="{int(a)} {int(b)} {int(c)}" />\n')
        if len(chunk) >= CHUNK_LINES:
            f.write("".join(chunk))
            chunk.clear()
    if chunk:
        f.write("".join(chunk))
    _close_tag(f, indent + "  ", "Triangles")

    # <Subsets ...>
    _open_tag(f, indent + "  ", "Subsets", {"count": len(built.subsets)})
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
    _close_tag(f, indent + "  ", "Subsets")
    # </IndexedTriangleSet>
    _close_tag(f, indent, "IndexedTriangleSet")
