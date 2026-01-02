from __future__ import annotations

from .model import NodeKind, SceneNode


def clear_shape_binding(node: SceneNode) -> None:
    node.shape_id = None
    node.material_ids = None


def to_transform_group(node: SceneNode) -> None:
    node.kind = NodeKind.TRANSFORM_GROUP
    clear_shape_binding(node)
