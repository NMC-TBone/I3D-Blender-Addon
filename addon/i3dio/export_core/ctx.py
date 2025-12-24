from __future__ import annotations

import logging
from dataclasses import dataclass, field

import bpy
import mathutils

from .. import debugging
from .builder import SceneBuilder
from .ids import IdAllocator
from .ir import ExportIR
from .messages import ExportMessages
from .reporting import Reporter


@dataclass(slots=True)
class ExportContext:
    name: str
    filepath: str
    depsgraph: bpy.types.Depsgraph
    conversion_matrix: mathutils.Matrix
    conversion_matrix_inv: mathutils.Matrix = field(init=False)
    settings: dict

    messages: ExportMessages = field(default_factory=ExportMessages)
    ids: IdAllocator = field(default_factory=IdAllocator)
    ir: ExportIR = field(default_factory=ExportIR)

    builder: SceneBuilder = field(init=False)
    unit_scale: float = 1.0

    @classmethod
    def create(
        cls,
        *,
        filepath: str,
        depsgraph,
        conversion_matrix: mathutils.Matrix,
        unit_scale: float,
        settings: dict,
    ) -> "ExportContext":
        ctx = cls(
            name=bpy.path.display_name_from_filepath(filepath),
            filepath=filepath,
            depsgraph=depsgraph,
            conversion_matrix=conversion_matrix,
            settings=settings,
            unit_scale=unit_scale,
        )
        ctx.conversion_matrix_inv = conversion_matrix.inverted_safe()
        ctx.builder = SceneBuilder(ctx)
        return ctx

    @property
    def log(self) -> logging.Logger:
        return debugging.get_logger("export")

    def logger(self, name: str = "export") -> logging.Logger:
        return debugging.get_logger(name)

    def reporter(self, prefix: str | None = None, *, operator=None, name: str = "export") -> Reporter:
        base = self.logger(name)
        if prefix:
            base = debugging.PrefixAdapter(base, {"prefix": (prefix if prefix.endswith(": ") else prefix + ": ")})
        return Reporter(self, base, operator=operator)

    def obj_logger(self, obj_name: str, name: str = "export") -> logging.Logger:
        return debugging.ObjectNameAdapter(self.logger(name), {"object_name": obj_name})

    def prefixed_log(self, prefix: str, name: str = "export") -> logging.LoggerAdapter:
        # ensure the prefix format is consistent
        p = prefix if prefix.endswith(": ") else prefix + ": "
        return debugging.PrefixAdapter(self.logger(name), {"prefix": p})

    def to_export(self, m: mathutils.Matrix) -> mathutils.Matrix:
        """Convert a matrix from Blender space to export (i3d) space."""
        return self.conversion_matrix @ m @ self.conversion_matrix_inv

    def to_export_forward(self, m: mathutils.Matrix) -> mathutils.Matrix:
        """Convert a direction/forward matrix from Blender space to export (i3d) space."""
        return self.conversion_matrix @ m
