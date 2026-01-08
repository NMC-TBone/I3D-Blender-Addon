# i3dio/export_core/resolve/kinds.py
from __future__ import annotations

from typing import TYPE_CHECKING

from ..ir import NodeKind, SourceKind, set_kind, to_transform_group

if TYPE_CHECKING:
    from ..ctx import ExportContext
    from ..ir import SceneNode

_OBJECT_TYPE_TO_KIND: dict[str, NodeKind] = {
    "CAMERA": NodeKind.CAMERA,
    "LIGHT": NodeKind.LIGHT,
    "MESH": NodeKind.SHAPE,
    "CURVE": NodeKind.SHAPE,
    "EMPTY": NodeKind.TRANSFORM_GROUP,
    # ARMATURE intentionally not here -> TG
}


def _allowed_object_type(ctx: ExportContext, obj_type: str) -> bool:
    if not (allowed := ctx.setting("object_types_to_export", ())):
        return True  # If setting is missing/empty, allow all types
    return obj_type in allowed


def resolve_kind_for_node(ctx: ExportContext, node: SceneNode) -> None:
    """
    Resolve a traversed OBJECT node's kind.
    Traversal produces "UNRESOLVED" nodes so the hierarchy is built first and specialized later.
    """
    if node.kind is not NodeKind.UNRESOLVED or node.source_kind is not SourceKind.OBJECT:
        return  # already resolved or not an OBJECT

    obj_type = node.source_object_type or 'EMPTY'
    if not _allowed_object_type(ctx, obj_type):
        to_transform_group(node)
        return  # Object type excluded by settings, keep as TG to preserve hierarchy.

    set_kind(node, _OBJECT_TYPE_TO_KIND.get(obj_type, NodeKind.TRANSFORM_GROUP))

    if ctx.is_dev:
        assert node.kind is not NodeKind.UNRESOLVED, "Failed to resolve kind for node %r" % (node,)
