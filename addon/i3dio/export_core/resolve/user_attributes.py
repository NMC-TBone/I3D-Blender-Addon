from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..ir import SourceKind, UserAttributeEntry

if TYPE_CHECKING:
    from ..ctx import ExportContext


_TYPE_MAP: dict[str, str] = {
    "data_boolean": "boolean",
    "data_integer": "integer",
    "data_float": "float",
    "data_string": "string",
    "data_scriptCallback": "scriptCallback",
}


def _read_value(item: Any, item_type: str) -> Any:
    return getattr(item, item_type, None)


def resolve_user_attributes(ctx: ExportContext) -> None:
    rep = ctx.reporter("user_attributes")
    out = ctx.ir.index.user_attributes_by_node_id
    out.clear()

    total_entries = 0
    total_nodes = 0

    for node in ctx.ir.iter_nodes(emitted_only=True, source_kind=SourceKind.OBJECT):
        obj = node.obj
        pg = getattr(obj, "i3d_user_attributes", None)
        if pg is None:
            continue

        items = getattr(pg, "attribute_list", None)
        if not items:
            continue

        entries: list[UserAttributeEntry] = []
        for item in items:
            name = (getattr(item, "name", "") or "").strip()
            if not name:
                continue

            item_type = getattr(item, "type", "")
            i3d_type = _TYPE_MAP.get(item_type)
            if not i3d_type:
                rep.debug("Skipping unsupported user attribute type %r on %r", item_type, obj.name)
                continue

            value = _read_value(item, item_type)
            entries.append(UserAttributeEntry(name=name, type=i3d_type, value=value))

        if entries:
            out[node.id] = entries
            total_nodes += 1
            total_entries += len(entries)

    rep.debug("Collected user attributes: nodes=%d attrs=%d", total_nodes, total_entries)
