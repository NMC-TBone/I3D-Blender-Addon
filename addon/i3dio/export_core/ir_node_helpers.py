from __future__ import annotations

from typing import Iterable

from .ir import NodeKind, SceneNode


def clear_material_ids(node: SceneNode) -> None:
    node.xml.node.pop("materialIds", None)


def set_material_ids(node: SceneNode, material_ids: Iterable[int]) -> None:
    node.xml.node["materialIds"] = ",".join(str(int(mid)) for mid in material_ids)


def clear_shape_binding(node: SceneNode) -> None:
    node.xml.node.pop("shapeId", None)
    clear_material_ids(node)


def to_transform_group(node: SceneNode) -> None:
    node.kind = NodeKind.TRANSFORM_GROUP
    clear_shape_binding(node)
