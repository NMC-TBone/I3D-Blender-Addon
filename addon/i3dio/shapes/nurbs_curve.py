from typing import ClassVar

from .. import xml_i3d
from ..i3d import I3D
from ..node_classes.node import Node
from ..shapes.evaluated import EvaluatedNurbsCurve


class ControlVertex:
    def __init__(self, position):
        self._position = position
        self._str = ""
        self._make_hash_string()

    def _make_hash_string(self):
        self._str = f"{self._position}"

    def __str__(self):
        return self._str

    def __hash__(self):
        return hash(self._str)

    def __eq__(self, other):
        return f"{self!s}" == f"{other!s}"

    def position_for_xml(self):
        return "{0:.6g} {1:.6g} {2:.6g}".format(*self._position)


class NurbsCurve(Node):
    ELEMENT_TAG: ClassVar[str] = "NurbsCurve"
    NAME_FIELD_NAME: ClassVar[str] = "name"
    ID_FIELD_NAME: ClassVar[str] = "shapeId"

    def __init__(self, id_: int, i3d: I3D, evaluated_curve_data: EvaluatedNurbsCurve, shape_name: str | None = None):
        self.id: int = id_
        self.i3d: I3D = i3d
        self.evaluated_curve_data: EvaluatedNurbsCurve = evaluated_curve_data
        self.control_vertex: dict[ControlVertex, int] = {}
        self.spline_type = None
        self.spline_form = None
        if shape_name is None:
            self.shape_name = self.evaluated_curve_data.name
        else:
            self.shape_name = shape_name
        super().__init__(id_, i3d, None)

    @property
    def name(self):
        return self.shape_name

    @property
    def element(self):
        return self.xml_elements["node"]

    @element.setter
    def element(self, value):
        self.xml_elements["node"] = value

    def process_spline(self, spline):
        if spline.type == "BEZIER":
            points = spline.bezier_points
            self.spline_type = "cubic"
        elif spline.type == "NURBS":
            points = spline.points
            self.spline_type = "cubic"
        elif spline.type == "POLY":
            points = spline.points
            self.spline_type = "linear"
        else:
            self.logger.warning(f"{spline.type} is not supported! Export of this curve is aborted.")
            return

        for loop_index, point in enumerate(points):
            ctrl_vertex = ControlVertex(point.co.xyz)
            self.control_vertex[ctrl_vertex] = loop_index

        self.spline_form = "closed" if spline.use_cyclic_u else "open"

    def populate_from_evaluated_nurbscurve(self):
        spline = self.evaluated_curve_data.curve_data.splines[0]
        self.process_spline(spline)

    def write_control_vertices(self):
        for control_vertex in list(self.control_vertex.keys()):
            vertex_attributes = {"c": control_vertex.position_for_xml()}

            xml_i3d.SubElement(self.element, "cv", vertex_attributes)

    def populate_xml_element(self):
        if len(self.evaluated_curve_data.curve_data.splines) == 0:
            self.logger.warning("has no splines! Export of this curve is aborted.")
            return

        self.populate_from_evaluated_nurbscurve()
        if self.spline_type:
            self._write_attribute("type", self.spline_type, "node")
        if self.spline_form:
            self._write_attribute("form", self.spline_form, "node")
        self.logger.debug(f"Has '{len(self.control_vertex)}' control vertices")
        self.write_control_vertices()
