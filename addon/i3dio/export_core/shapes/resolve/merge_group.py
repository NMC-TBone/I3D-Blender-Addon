# i3dio/export_core/shapes/resolve/merge_group.py
from __future__ import annotations

from typing import TYPE_CHECKING

import bpy

from ...ir import NodeKind
from ...tables.shapes import ShapeContributor

if TYPE_CHECKING:
    from ...ctx import ExportContext


def resolve_merge_groups(ctx: ExportContext) -> None:
    rep = ctx.section("merge_group")

    groups = ctx.ir.index.merge_group_nodes_by_index
    if not groups:
        rep.debug("No MergeGroups to process")
        return

    scene_groups = ctx.scene.i3dio_merge_groups
    # find node_id for a specific Blender object
    by_obj_ptr = {
        n.blender_ref.as_pointer(): nid
        for nid, n in ctx.ir.scene_nodes.items()
        if isinstance(n.blender_ref, bpy.types.Object)
    }

    for mg_index, node_ids in groups.items():
        if not (0 <= mg_index < len(scene_groups)):
            rep.warning("MergeGroup index %d out of range (have %d groups); skipping", mg_index, len(scene_groups))
            continue

        mg = scene_groups[mg_index]
        root_obj: bpy.types.Object | None = mg.root
        if not root_obj:
            rep.warning("MergeGroup %d has no root object; skipping", mg_index)
            continue
        if root_obj.type != "MESH":
            rep.warning(
                "MergeGroup %d root %r must be a Mesh object (got %s); skipping", mg_index, root_obj.name, root_obj.type
            )
            continue

        root_node_id = by_obj_ptr.get(root_obj.as_pointer())
        if root_node_id is None:
            rep.warning("MergeGroup %d root %r is not part of the export; skipping", mg_index, root_obj.name)
            continue

        # bind order: root first, then the rest in traversal order (dedup just in case)
        ordered = list(dict.fromkeys([root_node_id, *node_ids]))

        # Create the merged ShapeEntry
        entry = ctx.shapes.add_merge_group(root_obj=root_obj, mg_index=mg_index)
        root_frame = root_obj.matrix_world.copy()

        # Contributors + bind list (bind index == position in ordered list)
        for bind_index, nid in enumerate(ordered):
            ref = ctx.ir.scene_nodes[nid].blender_ref
            if isinstance(ref, bpy.types.Object) and ref.type == "MESH":
                entry.contributors.append(ShapeContributor(obj=ref, reference_frame=root_frame, bind_index=bind_index))

        bind_node_ids = [ctx.ir.scene_nodes[nid].id for nid in ordered]
        # Mutate IR nodes
        root_node = ctx.ir.scene_nodes[root_node_id]
        root_node.kind = NodeKind.SHAPE
        root_node.shape_id = entry.id
        root_node.xml.node["skinBindNodeIds"] = " ".join(str(i) for i in bind_node_ids)

        for nid in ordered[1:]:
            # Member nodes become TransformGroups
            n = ctx.ir.scene_nodes[nid]
            n.kind = NodeKind.TRANSFORM_GROUP
            ctx.node_reporter(n, "merge_group").debug("Converted to TransformGroup (part of MergeGroup %d)", mg_index)

        rep.debug(
            "[%s] MergeGroup %d shapeId=%d binds=%d contrib_meshes=%d",
            root_obj.name,
            mg_index,
            entry.id,
            len(bind_node_ids),
            len(entry.contributors),
        )
