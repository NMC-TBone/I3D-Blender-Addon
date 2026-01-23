# i3dio/export_core/geometry/__init__.py
from .built import BuiltShape, ShapeKind
from .mesh.its import BuiltITS, BuiltSubset, MaterialKeyKind

__all__ = [
    "BuiltShape",
    "ShapeKind",
    "BuiltITS",
    "BuiltSubset",
    "MaterialKeyKind",
]
