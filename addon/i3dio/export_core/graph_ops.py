from __future__ import annotations

from .ctx import ExportContext


def _remove_once(lst: list[int], value: int) -> None:
    try:
        lst.remove(value)
    except ValueError:
        pass


def detach(ctx: ExportContext, node_id: int) -> None:
    """
    Detach a node from its current parent/root list.
    Keeps node_id valid in ctx.ir.nodes; does not delete it.
    """
    n = ctx.ir.scene_nodes[node_id]

    if n.parent_id is None:
        _remove_once(ctx.ir.roots, node_id)
    else:
        parent = ctx.ir.scene_nodes.get(n.parent_id)
        if parent is not None:
            _remove_once(parent.children, node_id)

    n.parent_id = None


def attach(ctx: ExportContext, node_id: int, parent_id: int | None) -> None:
    """
    Attach a node under parent_id (or to roots if parent_id is None).
    Does not detach first.
    """
    n = ctx.ir.scene_nodes[node_id]
    n.parent_id = parent_id

    if parent_id is None:
        ctx.ir.roots.append(node_id)
    else:
        ctx.ir.scene_nodes[parent_id].children.append(node_id)


def reparent(ctx: ExportContext, node_id: int, new_parent_id: int | None) -> None:
    """
    Reparent node_id to new_parent_id, updating both roots and children lists safely.
    """
    detach(ctx, node_id)
    attach(ctx, node_id, new_parent_id)
