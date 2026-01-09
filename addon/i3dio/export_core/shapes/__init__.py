# Re-export from canonical location for backwards compatibility
from ..model.shapes import ShapeContributor, ShapeMode

# Re-export ITS building utilities
from .build_its import build_indexed_triangle_set

__all__ = [
    "ShapeContributor",
    "ShapeMode",
    "build_indexed_triangle_set",
]
