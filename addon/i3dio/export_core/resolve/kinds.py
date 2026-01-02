# i3dio/export_core/resolve/kinds.py
from __future__ import annotations

from typing import TYPE_CHECKING

import bpy

from ..ir import NodeKind, SceneNode

if TYPE_CHECKING:
    from ..ctx import ExportContext

_OBJECT_TYPE_TO_KIND: dict[str, NodeKind] = {
    "CAMERA": NodeKind.CAMERA,
    "LIGHT": NodeKind.LIGHT,
    "MESH": NodeKind.SHAPE,
    "CURVE": NodeKind.SHAPE,
    "ARMATURE": NodeKind.ARMATURE,
    "EMPTY": NodeKind.TRANSFORM_GROUP,
}


def _allowed_object_type(ctx: ExportContext, obj_type: str) -> bool:
    if not (allowed := ctx.settings.get("object_types_to_export")):
        return True  # If setting is missing/empty, allow all types
    return obj_type in allowed


def resolve_kind_for_node(ctx: ExportContext, node: SceneNode) -> None:
    """
    Resolve SceneNode.kind after traversal.

    Traversal creates UNRESOLVED nodes to keep hierarchy simple and predictable.
    This pass upgrades nodes based on Blender ref type and exporter settings:

    - If an object type is excluded via object_types_to_export: keep node as TRANSFORM_GROUP
      (preserves hierarchy; matches old exporter intent).
    - CURVE is treated as SHAPE (legacy behavior).
    - Collections always resolve to TRANSFORM_GROUP.
    """

    # Resolve basic kinds from blender_ref + settings
    if node.kind is not NodeKind.UNRESOLVED:
        return  # already resolved

    ref = node.blender_ref
    if not isinstance(ref, bpy.types.Object):
        # Collections and other non-object refs become
        node.kind = NodeKind.TRANSFORM_GROUP
        return

    obj_type = ref.type
    # If user excluded this object type -> keep hierarchy as TG
    if not _allowed_object_type(ctx, obj_type):
        node.kind = NodeKind.TRANSFORM_GROUP
        ctx.node_reporter(node, "kinds").debug(
            "Object type %r excluded by settings -> keeping as TRANSFORM_GROUP", obj_type
        )
        return

    kind = _OBJECT_TYPE_TO_KIND.get(obj_type, NodeKind.TRANSFORM_GROUP)
    node.kind = kind

    if obj_type not in _OBJECT_TYPE_TO_KIND:
        ctx.node_reporter(node, "kinds").debug("Unknown object type %r -> TRANSFORM_GROUP", obj_type)
