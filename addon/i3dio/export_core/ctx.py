from __future__ import annotations

import logging
from dataclasses import dataclass, field

import bpy
import mathutils

from .. import debugging
from .ids import IdAllocator
from .ir import ExportIR
from .messages import ExportMessages


@dataclass(slots=True)
class ExportContext:
    name: str
    filepath: str
    depsgraph: bpy.types.Depsgraph
    conversion_matrix: mathutils.Matrix
    settings: dict

    messages: ExportMessages = field(default_factory=ExportMessages)

    ids: IdAllocator = field(default_factory=IdAllocator)
    ir: ExportIR = field(default_factory=ExportIR)

    # freeze unit scale at export time (don’t read bpy.context repeatedly later)
    unit_scale: float = 1.0

    @classmethod
    def create(
        cls,
        *,
        filepath: str,
        depsgraph,
        conversion_matrix,
        unit_scale: float,
        settings: dict,
    ) -> "ExportContext":
        return cls(
            name=bpy.path.display_name_from_filepath(filepath),
            filepath=filepath,
            depsgraph=depsgraph,
            conversion_matrix=conversion_matrix,
            settings=settings,
            unit_scale=unit_scale,
        )

    def logger(self, name: str) -> logging.Logger:
        """Get everything under i3dio.<name> for consistent filtering"""
        return debugging.get_logger(name)

    def obj_logger(self, obj_name: str, name: str = "export") -> logging.Logger:
        return debugging.ObjectNameAdapter(self.logger(name), {"object_name": obj_name})
