from __future__ import annotations

from typing import TYPE_CHECKING

from ...ir import NodeKind, SourceKind, set_kind

if TYPE_CHECKING:
    from ...ctx import ExportContext


def resolve_font_shapes(ctx: ExportContext) -> None:
    """Resolve FONT objects to mesh-exported Shape nodes.

    Blender FONT objects are exported as evaluated meshes (IndexedTriangleSet).
    We keep the original object type, but override export type to MESH so the
    mesh pipeline can handle them consistently.
    """
    for node in ctx.ir.iter_nodes(source_kind=SourceKind.OBJECT, emitted_only=True):
        if node.source_object_type != "FONT":
            continue

        rep = ctx.node_reporter(node, "font_shapes")
        set_kind(node, NodeKind.SHAPE)
        node.source_object_type_override = "MESH"
        rep.debug("Font object exported as mesh (override to MESH).")
