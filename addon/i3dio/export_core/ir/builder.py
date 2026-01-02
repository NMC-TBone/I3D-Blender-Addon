from dataclasses import dataclass
from typing import TYPE_CHECKING

from ...utility import BlenderObject
from ..ids import IdKind
from .model import NodeKind, SceneNode

if TYPE_CHECKING:
    from ..ctx import ExportContext


@dataclass(slots=True)
class SceneBuilder:
    ctx: "ExportContext"

    def add_scene_node(
        self,
        *,
        kind: NodeKind,
        blender_ref: BlenderObject,
        parent_id: int | None,
    ) -> int:
        """Create a SceneNode in IR and attach it into the tree."""
        node_id = self.ctx.ids.alloc(IdKind.NODE)
        node = SceneNode(
            id=node_id,
            name=getattr(blender_ref, "name", f"Node_{node_id}"),
            kind=kind,
            blender_ref=blender_ref,
            parent_id=parent_id,
            matrix_local_export=None,
        )
        self.ctx.ir.add_node(node)
        return node_id
