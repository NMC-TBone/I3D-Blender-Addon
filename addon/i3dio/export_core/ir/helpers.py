# i3dio/export_core/ir/helpers.py
from __future__ import annotations

from .model import NodeKind, SceneNode


def clear_shape_binding(node: SceneNode) -> None:
    node.shape.shape_id = None
    node.shape.material_ids = None
    node.shape.skin_bind_node_ids = None


def to_transform_group(node: SceneNode) -> None:
    node.kind = NodeKind.TRANSFORM_GROUP
    clear_shape_binding(node)
