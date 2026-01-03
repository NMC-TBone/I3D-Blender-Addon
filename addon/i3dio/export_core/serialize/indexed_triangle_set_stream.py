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

    # Localize lookups (can be a bit faster)
    write_open = xml_i3d.write_open_tag
    write_close = xml_i3d.write_close_tag
    escape_attr = xml_i3d.escape_attr

    # Fast vector formatters for numpy rows (no Python loops)
    def vec3(row) -> str:
        return f"{row[0]:.6g} {row[1]:.6g} {row[2]:.6g}"

    def vec2(row) -> str:
        return f"{row[0]:.6g} {row[1]:.6g}"

    ind_tag = indent
    ind_child = indent + "  "  # 2 spaces deeper (matches your open-tag usage)
    ind_line = indent + "    "  # lines under Vertices/Triangles

    # <IndexedTriangleSet ...>
    its_attrs: dict[str, object] = {"name": built.name, "shapeId": built.shape_id, **built.attrs.node}
    write_open(f, "IndexedTriangleSet", its_attrs, indent=ind_tag)

    # <Vertices ...>
    v_attrs: dict[str, object] = {"count": vcount, "normal": True}
    for li in range(len(uvs)):
        v_attrs[f"uv{li}"] = True
    v_attrs.update(built.attrs.children.get("Vertices", {}))
    write_open(f, "Vertices", v_attrs, indent=ind_child)

    # vertices: chunked writing
    chunk: list[str] = []
    uv_layers = uvs  # local alias
    uv_count = len(uv_layers)

    for i in range(vcount):
        p = positions[i]
        n = normals[i]

        # Build the line with a tiny list (few parts), then join once.
        parts = [f'{ind_line}<v p="{vec3(p)}" n="{vec3(n)}"']
        for li in range(uv_count):
            uv = uv_layers[li][i]
            parts.append(f' t{li}="{vec2(uv)}"')
        if g is not None:
            gi = g[i]
            parts.append(f' g="{gi:.9g}"')
        elif bi is not None:
            parts.append(f' bi="{bi[i]:d}"')

        parts.append(" />\n")
        chunk.append("".join(parts))

        if len(chunk) >= CHUNK_LINES:
            f.write("".join(chunk))
            chunk.clear()

    if chunk:
        f.write("".join(chunk))

    write_close(f, "Vertices", indent=ind_child)

    # <Triangles ...>
    write_open(f, "Triangles", {"count": tri_count}, indent=ind_child)

    # Avoid reshape + row iteration + int() calls
    flat = indices.ravel()
    chunk.clear()
    for j in range(0, flat.size, 3):
        a = flat[j]
        b = flat[j + 1]
        c = flat[j + 2]
        chunk.append(f'{ind_line}<t vi="{a} {b} {c}" />\n')
        if len(chunk) >= CHUNK_LINES:
            f.write("".join(chunk))
            chunk.clear()

    if chunk:
        f.write("".join(chunk))

    write_close(f, "Triangles", indent=ind_child)

    # <Subsets ...>
    write_open(f, "Subsets", {"count": len(built.subsets)}, indent=ind_child)
    for s in built.subsets:
        slot_attr = (
            f' materialSlotName="{escape_attr(s.material_slot_name)}"' if s.material_slot_name is not None else ""
        )
        f.write(
            f'{ind_line}<Subset firstIndex="{s.first_index:d}" '
            f'numVertices="{s.num_vertices:d}" firstVertex="{s.first_vertex:d}" '
            f'numIndices="{s.num_indices:d}"{slot_attr} />\n'
        )
    write_close(f, "Subsets", indent=ind_child)

    write_close(f, "IndexedTriangleSet", indent=ind_tag)
