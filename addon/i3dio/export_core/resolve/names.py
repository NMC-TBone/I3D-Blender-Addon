# i3dio/export_core/resolve/names.py
from __future__ import annotations

from ...utility import strip_sorting_prefix
from ..ctx import ExportContext
from ..ir import SceneNode


def finalize_name_for_node(ctx: ExportContext, node: SceneNode) -> None:
    if not (sep := ctx.settings.get("object_sorting_prefix", ":")) or not node.name:
        return
    before = node.name
    after = strip_sorting_prefix(before, sep)
    if before != after:
        ctx.node_reporter(node, "names").debug("New name: %r -> %r (sep=%r)", before, after, sep)
        node.name = after
