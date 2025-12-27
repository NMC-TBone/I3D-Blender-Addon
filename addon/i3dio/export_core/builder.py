from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from ..utility import BlenderObject
from .ids import IdKind
from .ir import EmitTag, NodeKind, SceneNode

if TYPE_CHECKING:
    from .ctx import ExportContext


@dataclass(slots=True)
class SceneBuilder:
    ctx: "ExportContext"

    def add_scene_node(
        self,
        *,
        kind: NodeKind,
        blender_ref: BlenderObject,
        parent_id: int | None,
        attrs: dict[str, Any] | None = None,
        emit_as: EmitTag | None = None,
    ) -> int:
        """Create a SceneNode in IR and attach it into the tree."""
        ir = self.ctx.ir
        ids = self.ctx.ids

        node_id = ids.alloc(IdKind.NODE)
        node = SceneNode(
            id=node_id,
            name=getattr(blender_ref, "name", f"Node_{node_id}"),
            kind=kind,
            blender_ref=blender_ref,
            parent_id=parent_id,
            matrix_world_bl=None,
            matrix_local_export=None,
            emit_as=emit_as,
            attrs=attrs or {},
        )

        ir.scene_nodes[node_id] = node

        if parent_id is None:
            ir.roots.append(node_id)
        else:
            ir.scene_nodes[parent_id].children.append(node_id)

        return node_id
