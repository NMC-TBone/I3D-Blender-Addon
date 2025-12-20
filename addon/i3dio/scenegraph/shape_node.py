from typing import ClassVar

import bpy
import mathutils

from ..i3d import I3D
from ..node_classes.node import SceneGraphNode
from ..shapes.evaluated import EvaluatedMesh, EvaluatedNurbsCurve
from ..shapes.indexed_triangle_set import IndexedTriangleSet


class ShapeNode(SceneGraphNode):
    ELEMENT_TAG: ClassVar[str] = 'Shape'

    def __init__(self, id_: int, shape_object: bpy.types.Object | None, i3d: I3D, parent: SceneGraphNode | None = None):
        self.shape_id: int | None = None
        super().__init__(id_=id_, blender_object=shape_object, i3d=i3d, parent=parent)

        self._create_shape()  # Create shape immediately upon initialization

    def _create_shape(self) -> None:
        """Creates the associated shape data (IndexTriangleSet or NurbsCurve) and stores its ID."""
        self.logger.debug(f"Creating shape data for object {self.blender_object.name!r}")
        if self.blender_object.type == 'CURVE':
            # Create and add the NurbsCurve data object to the i3d file
            self.shape_id = self.i3d.add_curve(EvaluatedNurbsCurve(self.i3d, self.blender_object))
            # Keep reference to the NurbsCurve element
            self.xml_elements['NurbsCurve'] = self.i3d.shapes[self.shape_id].element
        else:
            # Create and add the EvaluatedMesh data object to the i3d file
            self.shape_id = self.i3d.add_shape(EvaluatedMesh(self.i3d, self.blender_object, node=self))
            # Keep reference to the IndexedTriangleSet element
            self.xml_elements['IndexedTriangleSet'] = self.i3d.shapes[self.shape_id].element

    @property
    def _transform_for_conversion(self) -> mathutils.Matrix:
        return self.i3d.to_i3d(self._get_object_matrix())

    def is_instance(self) -> bool:
        """Return True if this shape node is an instance (not the source/original) of a processed mesh."""
        shape: IndexedTriangleSet = self.i3d.shapes.get(self.shape_id)
        if not shape:
            return False
        return shape.evaluated_mesh.source_object is not self.blender_object

    def populate_xml_element(self) -> None:
        if self.blender_object.type == 'MESH' and self.is_instance():
            # For mesh instances: Remap material IDs using slot indices to match subset order from original mesh
            shape: IndexedTriangleSet = self.i3d.shapes[self.shape_id]
            self.logger.debug(f"Instance detected: Original={shape.evaluated_mesh.source_object.name}, "
                              f"Instance={self.blender_object.name}, shape_id={self.shape_id}")
            blender_slots = [slot.material for slot in self.blender_object.material_slots]
            material_ids = [
                self.i3d.add_material(
                    blender_slots[slot_idx] if 0 <= slot_idx < len(blender_slots) and blender_slots[slot_idx]
                    else self.i3d.get_default_material().blender_material
                )
                for slot_idx in shape.subset_slot_indices
            ]
            self.logger.debug(f"writing {len(material_ids)} material IDs for instanced shape")
            self._write_attribute('materialIds', ' '.join(map(str, material_ids)))

        self._write_attribute('shapeId', self.shape_id)
        super().populate_xml_element()
