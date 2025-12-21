from dataclasses import dataclass
from typing import Any

from .ctx import ExportContext
from .ids import IdKind
from .ir import NodeKind, SceneNode


@dataclass(slots=True)
class IRBuilder:
    ctx: ExportContext

    def add_transform_group(self, obj_or_collection: Any, parent_id: int | None) -> int:
        ir = self.ctx.ir

        if obj_or_collection in ir.by_object:
            return ir.by_object[obj_or_collection]

        node_id = self.ctx.ids.alloc(IdKind.NODE)

        node = SceneNode(
            id=node_id,
            name=obj_or_collection.name,
            kind=NodeKind.TRANSFORM_GROUP,
            blender_ref=obj_or_collection,
            parent_id=parent_id,
            matrix_world=getattr(obj_or_collection, "matrix_world", None),
        )

        ir.nodes[node_id] = node
        ir.by_object[obj_or_collection] = node_id

        if parent_id is None:
            ir.roots.append(node_id)
        else:
            ir.nodes[parent_id].children.append(node_id)

        return node_id
