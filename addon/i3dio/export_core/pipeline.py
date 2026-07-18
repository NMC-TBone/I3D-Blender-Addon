from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import bpy

from . import traverse
from .resolve.runner import resolve_all

if TYPE_CHECKING:
    import logging

    from .ctx import ExportContext


def run_export(ctx: ExportContext, *, context: bpy.types.Context) -> list[bpy.types.Object]:
    """Run the export pipeline and return the user-selected/source scope objects."""
    return _PipelineRun(ctx, context).run()


def build_ir(ctx: ExportContext, *, context: bpy.types.Context) -> list[bpy.types.Object]:
    """Build the scene IR for the current export selection mode."""
    return _PipelineRun(ctx, context).build_ir()


@dataclass(slots=True)
class _PipelineRun:
    ctx: ExportContext
    context: bpy.types.Context
    logger: logging.LoggerAdapter = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.logger = self.ctx.ctx_logger(prefix="pipeline")

    def run(self) -> list[bpy.types.Object]:
        self.logger.debug("Traversal start")
        scope_objects = self.build_ir()
        self.logger.debug(
            "Traversal done: nodes=%d roots=%d", len(self.ctx.ir.scene_nodes), sum(1 for _ in self.ctx.ir.iter_roots())
        )

        self.logger.debug("Resolve start")
        resolve_all(self.ctx)
        self.logger.debug("Resolve done")

        return scope_objects

    def build_ir(self) -> list[bpy.types.Object]:
        """Build the IR for the current export selection mode."""
        if self.ctx.ir.scene_nodes:
            raise RuntimeError("ExportContext is single-use; create a new context for each pipeline run")
        if (source_collection := self._collection_export_override()) is not None:
            return self._build_collection_scope(source_collection, label=f"collection {source_collection.name!r}")

        match selection_mode := self.ctx.operator.selection:
            case "ALL":
                return self._build_collection_scope(self.context.scene.collection, label="entire scene")
            case "ACTIVE_COLLECTION":
                collection = self.context.view_layer.active_layer_collection.collection
                return self._build_collection_scope(collection, label=f"active collection {collection.name!r}")
            case "ACTIVE_OBJECT":
                if (active_object := self.context.active_object) is None:
                    raise RuntimeError("No active object for export")

                return self._build_object_scope([active_object], label=f"active object {active_object.name!r}")
            case "SELECTED_OBJECTS":
                if not (selected_objects := list(self.context.selected_objects)):
                    raise RuntimeError("No objects selected for export")

                return self._build_object_scope(selected_objects, label=f"{len(selected_objects)} selected objects")
            case _:
                raise RuntimeError(f"Unknown export selection mode: {selection_mode!r}")

    def _collection_export_override(self) -> bpy.types.Collection | None:
        if not (collection_name := self.ctx.operator.collection):
            return None
        if (collection := bpy.data.collections.get(collection_name)) is None:
            raise RuntimeError(f"Collection {collection_name!r} was not found")

        return collection

    def _build_collection_scope(self, collection: bpy.types.Collection, *, label: str) -> list[bpy.types.Object]:
        self.logger.info("Exporting %s", label)
        traverse.add_collection_tree(self.ctx, collection, parent_id=None, emit_self=False)
        return list(collection.all_objects)

    def _build_object_scope(self, objects: list[bpy.types.Object], *, label: str) -> list[bpy.types.Object]:
        self.logger.info("Exporting %s", label)
        if self.ctx.setting("selection_traverse_children", False):
            traverse.build_object_roots(self.ctx, objects)
            return _objects_with_children(objects)

        traverse.build_selected_roots(self.ctx, objects)
        return objects


def _objects_with_children(objects: list[bpy.types.Object]) -> list[bpy.types.Object]:
    """Return roots plus recursive children, keeping each object once."""
    result: list[bpy.types.Object] = []
    seen: set[bpy.types.Object] = set()
    stack = list(reversed(objects))

    while stack:
        obj = stack.pop()
        if obj in seen:
            continue

        seen.add(obj)
        result.append(obj)
        stack.extend(reversed(obj.children))

    return result
