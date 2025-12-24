# i3dio/export_core/resolve/names.py
from __future__ import annotations

from ..ctx import ExportContext


def strip_sorting_prefix(name: str, sep: str) -> str:
    """Strip leading '<digits><sep>' from name (e.g. '12:Cube' -> 'Cube')."""
    if not name or not sep:
        return name
    head, found, tail = name.partition(sep)  # Split at first occurrence of sep
    if found and head.isdigit() and tail:
        return tail
    return name


def finalize_names(ctx: ExportContext) -> None:
    if not (sep := ctx.settings.get("object_sorting_prefix", ":")):
        return
    for node in ctx.ir.scene_nodes.values():
        if name := node.name:
            node.name = strip_sorting_prefix(name, sep)
