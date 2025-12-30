# i3dio/export_core/shapes/resolve/link.py
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...ctx import ExportContext


def resolve_shape_links(ctx: "ExportContext") -> None:
    for node in ctx.ir.scene_nodes.values():
        ctx.shapes.link_node(node)
