import unittest
from types import SimpleNamespace

from i3dio.i3d_attributes.mesh import MESH_SCHEMA, I3DNodeShapeAttributes
from i3dio.i3d_attributes.resolve import ResolvedAttribute, resolve_attributes
from i3dio.i3d_attributes.schema import I3DSchema, TrackingDefinition, exported, parse_hex_u32, stored


class SchemaMetadataTest(unittest.TestCase):
    def test_property_group_explicitly_owns_the_original_schema(self):
        self.assertIs(I3DNodeShapeAttributes.i3d_schema, MESH_SCHEMA)
        self.assertNotIn("i3d_schema", I3DNodeShapeAttributes.__annotations__)

    def test_mapping_and_exported_iteration_preserve_declaration_order(self):
        stored_definition = stored(None)
        exported_definition = exported(None, i3d_name="second", i3d_default=0)
        schema = I3DSchema(first=stored_definition, second=exported_definition)

        self.assertEqual(list(schema), ["first", "second"])
        self.assertEqual(len(schema), 2)
        self.assertIs(schema["first"], stored_definition)
        self.assertEqual(list(schema.exported()), [("second", exported_definition)])

    def test_schema_is_immutable(self):
        schema = I3DSchema(value=stored(None))

        with self.assertRaises(TypeError):
            schema["other"] = stored(None)

    def test_schema_rejects_invalid_definitions(self):
        with self.assertRaisesRegex(TypeError, "must be a PropertyDefinition"):
            I3DSchema(invalid=object())

    def test_schema_rejects_unknown_dependencies(self):
        with self.assertRaisesRegex(ValueError, "depends on unknown property 'missing'"):
            I3DSchema(value=exported(None, i3d_name="value", i3d_default=0, dependencies={"missing": True}))

    def test_schema_rejects_empty_export_names_and_targets(self):
        with self.assertRaisesRegex(ValueError, "empty I3D name"):
            I3DSchema(value=exported(None, i3d_name="", i3d_default=0))

        with self.assertRaisesRegex(ValueError, "empty I3D target"):
            I3DSchema(value=exported(None, i3d_name="value", i3d_default=0, target=""))

    def test_install_rejects_different_schema_ownership(self):
        schema = I3DSchema(value=stored(None))
        other_schema = I3DSchema(other=stored(None))

        class DifferentSchema:
            i3d_schema = other_schema

        with self.assertRaisesRegex(TypeError, "already references a different schema"):
            schema.install(DifferentSchema)

    def test_install_rejects_existing_annotations(self):
        schema = I3DSchema(value=stored(None))

        class DuplicateProperty:
            value: object

        with self.assertRaisesRegex(TypeError, "already defines properties: value"):
            schema.install(DuplicateProperty)

    def test_install_adds_schema_rna_annotations(self):
        rna = object()
        schema = I3DSchema(value=stored(rna))

        @schema.install
        class PropertyGroup:
            pass

        self.assertIs(PropertyGroup.i3d_schema, schema)
        self.assertIs(PropertyGroup.__annotations__["value"], rna)


class ResolveAttributesTest(unittest.TestCase):
    def test_material_style_dependency(self):
        schema = I3DSchema(
            refraction_map=stored(None),
            light_absorbance=exported(
                None,
                i3d_name="coeff",
                i3d_default=0.0,
                target="Refractionmap",
                dependencies={"refraction_map": True},
            ),
        )
        values = SimpleNamespace(refraction_map=False, light_absorbance=1.0)

        self.assertEqual(list(resolve_attributes(values, schema)), [])

        values.refraction_map = True
        self.assertEqual(
            list(resolve_attributes(values, schema)),
            [ResolvedAttribute(source="light_absorbance", target="Refractionmap", name="coeff", value=1.0)],
        )

    def test_multiple_dependencies_must_all_match(self):
        schema = I3DSchema(
            enabled=stored(None),
            mode=stored(None),
            result=exported(None, i3d_name="result", i3d_default=0, dependencies={"enabled": True, "mode": "active"}),
        )
        values = SimpleNamespace(enabled=True, mode="inactive", result=5)

        self.assertEqual(list(resolve_attributes(values, schema)), [])

        values.mode = "active"
        self.assertEqual(
            list(resolve_attributes(values, schema)),
            [ResolvedAttribute(source="result", target="Node", name="result", value=5)],
        )

    def test_dependency_uses_effective_tracked_value(self):
        schema = I3DSchema(
            light_type=stored(
                None,
                tracking=TrackingDefinition("type", mapping={"POINT": "point", "SUN": "directional"}),
            ),
            scattering=exported(
                None, i3d_name="scattering", i3d_default=False, dependencies={"light_type": "directional"}
            ),
        )
        values = SimpleNamespace(light_type="point", light_type_tracking=True, scattering=True)
        owner = SimpleNamespace(type="SUN")

        self.assertEqual(
            list(resolve_attributes(values, schema, owner=owner)),
            [ResolvedAttribute(source="scattering", target="Node", name="scattering", value=True)],
        )

        owner.type = "POINT"
        self.assertEqual(list(resolve_attributes(values, schema, owner=owner)), [])

    def test_tracking_switches_between_owner_and_custom_value(self):
        schema = I3DSchema(
            distance=exported(
                None,
                i3d_name="distance",
                i3d_default=1.0,
                tracking=TrackingDefinition("cutoff_distance"),
            )
        )
        values = SimpleNamespace(distance=3.0, distance_tracking=True)
        owner = SimpleNamespace(cutoff_distance=7.0)

        [resolved] = resolve_attributes(values, schema, owner=owner)
        self.assertEqual(resolved.value, 7.0)

        values.distance_tracking = False
        [resolved] = resolve_attributes(values, schema, owner=owner)
        self.assertEqual(resolved.value, 3.0)

    def test_tracking_requires_the_conventional_toggle(self):
        schema = I3DSchema(
            distance=exported(
                None,
                i3d_name="distance",
                i3d_default=1.0,
                tracking=TrackingDefinition("cutoff_distance"),
            )
        )

        with self.assertRaisesRegex(AttributeError, "distance_tracking"):
            list(resolve_attributes(SimpleNamespace(distance=3.0), schema))

    def test_converter_errors_are_reported_and_stored_properties_are_omitted(self):
        schema = I3DSchema(
            mask=exported(None, i3d_name="mask", i3d_default="0", converter=parse_hex_u32),
            ui_only=stored(None),
        )
        errors = []

        resolved = list(
            resolve_attributes(
                SimpleNamespace(mask="invalid", ui_only="value"),
                schema,
                on_error=lambda source, error: errors.append((source, error)),
            )
        )

        self.assertEqual(resolved, [])
        self.assertEqual(errors[0][0], "mask")
        self.assertIsInstance(errors[0][1], ValueError)


if __name__ == "__main__":
    unittest.main(argv=[__file__])
