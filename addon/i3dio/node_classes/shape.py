# i3dio/node_classes/shape.py  (compat shim)
from ..scenegraph.shape_node import ShapeNode
from ..shapes.evaluated import EvaluatedMesh, EvaluatedNurbsCurve
from ..shapes.indexed_triangle_set import IndexedTriangleSet
from ..shapes.nurbs_curve import NurbsCurve

__all__ = [
    "ShapeNode",
    "EvaluatedMesh",
    "EvaluatedNurbsCurve",
    "IndexedTriangleSet",
    "NurbsCurve",
]
