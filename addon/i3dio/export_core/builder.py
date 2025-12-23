from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from mathutils import Matrix

from ..utility import BlenderObject
from .ids import IdKind
from .ir import NodeKind, SceneNode

if TYPE_CHECKING:
    from .ctx import ExportContext


class _AutoDedup:
    __slots__ = ()


AUTO_DEDUP = _AutoDedup()
DedupKey = int | None | _AutoDedup


def _dedup_identity(ref: BlenderObject) -> int:
    """
    Dedup identity key for Blender datablocks.
    Prefer as_pointer() because Blender can create multiple Python wrappers referring to the same underlying datablock.
    """
    try:
        return ref.as_pointer()
    except Exception:
        return id(ref)


@dataclass(slots=True)
class SceneBuilder:
    ctx: "ExportContext"

    def add_scene_node(
        self,
        *,
        kind: NodeKind,
        blender_ref: BlenderObject,
        parent_id: int | None,
        name: str | None = None,
        matrix: Matrix | None = None,
        attrs: dict[str, Any] | None = None,
        dedup_key: DedupKey = AUTO_DEDUP,
        emit_as: str | None = None,
    ) -> int:
        """
        Create a SceneNode in IR and attach it into the tree.

        dedup_key:
            - AUTO_DEDUP: use _dedup_identity(blender_ref)
            - None: no deduplication
            - int: use given key for deduplication
        """
        ir = self.ctx.ir
        ids = self.ctx.ids

        # Resolve dedup key
        key: int | None
        if dedup_key is AUTO_DEDUP:
            key = _dedup_identity(blender_ref)
        else:
            key = dedup_key

        if key is not None:
            existing = ir.dedup_map.get(key)
            if existing is not None:
                return existing

        node_id = ids.alloc(IdKind.NODE)
        node = SceneNode(
            id=node_id,
            name=name or getattr(blender_ref, "name", f"Node_{node_id}"),
            kind=kind,
            blender_ref=blender_ref,
            parent_id=parent_id,
            matrix_world=matrix if matrix is not None else getattr(blender_ref, "matrix_world", None),
            attrs=attrs or {},
        )

        if emit_as:  # store emitter tag override in attrs for now
            node.attrs.setdefault("emit_as", emit_as)

        ir.scene_nodes[node_id] = node

        if key is not None:
            ir.dedup_map[key] = node_id

        if parent_id is None:
            ir.roots.append(node_id)
        else:
            ir.scene_nodes[parent_id].children.append(node_id)

        return node_id
