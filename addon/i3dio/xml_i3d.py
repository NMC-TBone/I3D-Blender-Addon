"""
xml_i3d.py

Helpers for reading/writing GIANTS I3D XML with consistent formatting:
- float precision: .6g
- bool: true/false
- vectors: "x y z" with .6g
- optional pretty indentation (skippable subtrees)
- optional "stream Shapes" writer to avoid huge ElementTree node counts
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from typing import Any

import bpy
import mathutils
from idprop.types import IDPropertyArray

logger = logging.getLogger(__name__)

# Public constants / types
XML_Element = ET.Element
FILE_EXT = ".i3d"
MERGE_GROUP_PREFIX = "MergedMesh_"
SKINNED_MESH_PREFIX = "SkinnedMesh_"
I3D_MAX = 3.40282e38


# Parse / Element constructors
def parse(*argv, **kwargs) -> ET.ElementTree | None:
    try:
        return ET.parse(*argv, **kwargs, parser=ET.XMLParser())
    except (ET.ParseError, FileNotFoundError) as e:
        logger.error("Error while parsing xml file: %s", e)
        return None


def SubElement(*args, **kwargs) -> ET.Element:  # noqa: N802
    return ET.SubElement(*args, **kwargs)


def Element(*args, **kwargs) -> ET.Element:  # noqa: N802
    return ET.Element(*args, **kwargs)


def ElementTree(*args, **kwargs) -> ET.ElementTree:  # noqa: N802
    return ET.ElementTree(*args, **kwargs)


# Root
def i3d_root_element(name: str) -> XML_Element:
    root_attributes = {"version": "1.6"}
    namespaced_attributes = {
        "xsi:noNamespaceSchemaLocation": "http://i3d.giants.ch/schema/i3d-1.6.xsd",
        "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
    }
    return Element("i3D", attrib={"name": name, **root_attributes, **namespaced_attributes})


# Attribute formatting / writing
def _fmt_vector(values: tuple[float, ...]) -> str:
    return " ".join(f"{float(x):.6g}" for x in values)


def fmt_attr_value(value: Any) -> str:
    """
    Format a value as it should appear inside an XML attribute.

    This function is the single formatting source of truth for:
    - ElementTree attribute writes (write_attribute)
    - Streaming writers (export_to_i3d_file_streaming_shapes, write_its_stream, etc.)
    """
    if isinstance(value, bool):  # order matters (bool is int subclass)
        return str(value).lower()
    if isinstance(value, int):
        return f"{value:d}"
    if isinstance(value, float):
        return f"{value:.6g}"
    if isinstance(value, str):
        return value

    # Vector-ish
    if isinstance(value, (list, tuple, bpy.types.bpy_prop_array, mathutils.Color, mathutils.Vector, IDPropertyArray)):
        return _fmt_vector(tuple(value))

    # Fallback
    return str(value)


def escape_attr(text: str) -> str:
    """Escape attribute value using the i3d-compatible escape function."""
    return ET._escape_attrib(text)


def write_attribute(element: XML_Element, attribute: str, value: Any) -> None:
    element.set(attribute, fmt_attr_value(value))


def write_int(element: XML_Element, attribute: str, value: int) -> None:
    element.set(attribute, f"{value:d}")


def write_float(element: XML_Element, attribute: str, value: float) -> None:
    element.set(attribute, f"{value:.6g}")


def write_bool(element: XML_Element, attribute: str, value: bool) -> None:
    element.set(attribute, str(value).lower())


def write_string(element: XML_Element, attribute: str, value: str) -> None:
    element.set(attribute, value)


def write_vector(element: XML_Element, attribute: str, values: tuple) -> None:
    element.set(attribute, _fmt_vector(tuple(values)))


# Pretty indentation
def add_indentations(element: XML_Element, level: int = 0, *, skip_tags: set[str] | None = None) -> None:
    """
    Pretty-print indentation similar to the classic effbot recipe, but with the ability
    to skip entire subtrees (e.g. skip_tags={"Shapes"}).
    """
    skip = skip_tags or set()
    if element.tag in skip:
        return

    indent = "\n" + level * "  "
    if len(element):
        if not element.text or not element.text.strip():
            element.text = indent + "  "
        if not element.tail or not element.tail.strip():
            element.tail = indent

        for child in element:
            add_indentations(child, level + 1, skip_tags=skip)

        if not element.tail or not element.tail.strip():
            element.tail = indent
    else:
        if level and (not element.tail or not element.tail.strip()):
            element.tail = indent


def write_tree_to_file(
    tree: ET.ElementTree,
    file_path: str,
    *argv,
    pretty: bool = True,
    skip_indent_tags: set[str] | None = None,
    **kwargs,
) -> None:
    if pretty:
        add_indentations(tree.getroot(), skip_tags=skip_indent_tags)
    tree.write(file_path, *argv, **kwargs)


def _xml_write_open_tag(f, tag: str, attrib: dict[str, Any], indent: str = "") -> None:
    if attrib:
        parts = [f'{k}="{escape_attr(fmt_attr_value(v))}"' for k, v in attrib.items()]
        f.write(f"{indent}<{tag} " + " ".join(parts) + ">\n")
    else:
        f.write(f"{indent}<{tag}>\n")


def export_to_i3d_file(
    *,
    root: ET.Element,
    file_path: str,
    shapes_writer=None,  # optional callable(f)
    encoding: str = "iso-8859-1",
    xml_declaration: bool = True,
    pretty: bool = True,
    skip_indent_tags: set[str] | None = None,
) -> None:
    """
    Write an i3d where all sections are ElementTree-serialized, except <Shapes> content,
    which is produced by `shapes_writer(f)`.

    If `pretty` is True, indentation is applied to the ElementTree beforehand, but you can
    skip indenting certain tags (typically {"Shapes"}) using skip_indent_tags.
    """
    if shapes_writer is None:
        settings = {"xml_declaration": xml_declaration, "encoding": encoding, "method": "xml"}
        write_tree_to_file(ElementTree(root), file_path, pretty=pretty, skip_indent_tags=skip_indent_tags, **settings)
        return
    if pretty:
        add_indentations(root, skip_tags=skip_indent_tags)

    with open(file_path, "w", encoding=encoding, newline="\n") as f:
        if xml_declaration:
            f.write(f'<?xml version="1.0" encoding="{encoding}"?>\n')

        # <i3D ...>
        _xml_write_open_tag(f, root.tag, root.attrib, indent="")

        # Children in order; stream Shapes
        for child in list(root):
            if child.tag == "Shapes":
                f.write("  <Shapes>\n")
                shapes_writer(f)
                f.write("  </Shapes>\n")
                continue

            xml = ET.tostring(child, encoding="unicode", method="xml")
            # Prefix with two spaces so direct children align under root
            for line in xml.splitlines(True):
                f.write(("  " + line) if line.strip() else line)

        f.write(f"</{root.tag}>\n")


# Attribute escaping monkeypatch (i3d-specific)
def _escape_attrib_i3d(text):
    """
    Escape attribute values. Same behavior as your previous implementation, kept here
    to ensure > is not escaped (required for i3d format).
    """
    try:
        if "&" in text:
            text = text.replace("&", "&amp;")
        if "<" in text:
            text = text.replace("<", "&lt;")
        if ">" in text:
            # Needed for the i3d format: do not escape >
            pass
        if '"' in text:
            text = text.replace('"', "&quot;")

        # Normalize newlines per XML rules
        if "\r\n" in text:
            text = text.replace("\r\n", "\n")
        if "\r" in text:
            text = text.replace("\r", "\n")

        # Escape control whitespace
        if "\n" in text:
            text = text.replace("\n", "&#10;")
        if "\t" in text:
            text = text.replace("\t", "&#09;")
        return text
    except (TypeError, AttributeError):
        ET._raise_serialization_error(text)


# Assign the escape attribute function to replace the default implementation
ET._escape_attrib = _escape_attrib_i3d
