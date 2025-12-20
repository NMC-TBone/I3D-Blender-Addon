from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .ids import IdAllocator, IdKind
from .ir import ExportIR, NodeKind, SceneNode


@dataclass(slots=True)
class IRBuilder:
    ids: IdAllocator
    ir: ExportIR

    def add_transform_group(self, obj_or_collection: Any, parent_id: int | None) -> int:
        # Dedup by object identity (like your processed_objects)
        if obj_or_collection in self.ir.by_object:
            return self.ir.by_object[obj_or_collection]

        node_id = self.ids.alloc(IdKind.NODE)
        name = obj_or_collection.name
        mw = getattr(obj_or_collection, "matrix_world", None)

        node = SceneNode(
            id=node_id,
            name=name,
            kind=NodeKind.TRANSFORM_GROUP,
            blender_ref=obj_or_collection,
            parent_id=parent_id,
            matrix_world=mw,
        )
        self.ir.nodes[node_id] = node
        self.ir.by_object[obj_or_collection] = node_id

        if parent_id is None:
            self.ir.roots.append(node_id)
        else:
            self.ir.nodes[parent_id].children.append(node_id)

        return node_id
