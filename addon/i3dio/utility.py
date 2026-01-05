"""This module contains various small utility functions, that don't really belong anywhere else"""

from __future__ import annotations

import logging
import math
import os
import re
from pathlib import Path

import bpy
import mathutils
from idprop.types import IDPropertyArray

logger = logging.getLogger(__name__)

BlenderRef = bpy.types.Object | bpy.types.Collection


def _is_number(x: object) -> bool:
    return isinstance(x, (int, float))


def _is_sequence_like(value: object) -> bool:
    return isinstance(
        value, (tuple, list, mathutils.Vector, mathutils.Color, bpy.types.bpy_prop_array, IDPropertyArray)
    )


def isclose_any(a: object, b: object, *, abs_tol: float = 1e-6) -> bool:
    """Type-aware closeness check:
    - numbers: abs-only
    - Vectors/Colors/prop arrays: L2 norm
    - Euler: max-abs per component
    - other sequences: elementwise abs-only
    - fallback: ==
    """
    # Numbers
    if _is_number(a) and _is_number(b):
        return math.isclose(float(a), float(b), rel_tol=0.0, abs_tol=abs_tol)

    # Euler
    if isinstance(a, mathutils.Euler) and isinstance(b, mathutils.Euler):
        return max(abs(a.x - b.x), abs(a.y - b.y), abs(a.z - b.z)) <= abs_tol

    if isinstance(a, mathutils.Vector) and isinstance(b, mathutils.Vector):
        d = a - b
        return d.length_squared <= abs_tol * abs_tol

    # Vector-ish (Vector, Color, bpy_prop_array, tuples/lists that can become Vector)
    if _is_sequence_like(a) and _is_sequence_like(b):
        a_list = list(a)
        b_list = list(b)

        if len(a_list) != len(b_list):
            return False

        # If all numeric, prefer norm-based (same semantics as near_vec/near_zero_vec)
        if all(_is_number(x) for x in a_list) and all(_is_number(y) for y in b_list):
            # L2 norm (works for 2/3/4D too)
            dsq = 0.0
            for x, y in zip(a_list, b_list):
                d = float(x) - float(y)
                dsq += d * d
            return dsq <= abs_tol * abs_tol

        # Otherwise elementwise with abs-only for numeric parts, == for others
        for x, y in zip(a_list, b_list):
            if _is_number(x) and _is_number(y):
                if not math.isclose(float(x), float(y), rel_tol=0.0, abs_tol=abs_tol):
                    return False
            else:
                if x != y:
                    return False
        return True
    return a == b


def ext_user_dir(subpath: str = "", create: bool = True) -> Path:
    """
    Returns the extension's per-user writable directory (or a subdir).
    Creates missing directories when create=True.
    """
    return Path(bpy.utils.extension_path_user(__package__, path=subpath, create=create))


def as_fs_relative_path(filepath: str) -> Path:
    """
    Checks if a filepath is relative to the FS data directory

    Checks the addon settings for the FS installation path and compares that with the supplied filepath, to see if it
    originates from within that directory.

    Args:
        filepath (str): The filepath to check.

    Returns:
        str: The `$data`-replaced filepath if applicable, or a cleaned-up absolute path.
    """
    # Resolve the absolute, normalized path to the FS data directory (if set)
    fs_data_pref = get_fs_data_path()
    target_path = Path(bpy.path.abspath(filepath)).resolve(strict=False)
    if fs_data_pref:
        fs_data_path = Path(bpy.path.abspath(fs_data_pref)).resolve(strict=False)
        try:  # Return $data-prefixed path if inside FS data directory
            relative_to_fs = target_path.relative_to(fs_data_path)
            return Path("$data") / relative_to_fs
        except ValueError:
            pass  # Not inside FS data directory
    return target_path


def as_export_path(filepath: str) -> Path:
    """
    Resolves the export path for a file, for compatibility with Giants Editor and modding workflows.

    Priority:
      - If inside the Farming Simulator (FS) Data directory, returns a '$data/...' path.
      - If under the current .blend file's folder (or subfolders), returns a path relative to the blend file.
      - Otherwise, returns an absolute path.

    Args:
        filepath (str): The path to the file, as used or stored by/in Blender.

    Returns:
        Path: The resolved path, either as a relative path (to the blend file) or an absolute path.
    """
    if filepath.startswith("$data"):
        # Already $data-prefixed (can happen from certain shader textures)
        return Path(filepath)

    # Check if inside FS data directory
    if (fs_path := as_fs_relative_path(filepath)).parts and fs_path.parts[0] == "$data":
        return fs_path

    # Try to make path relative to the .blend file
    blend_dir = Path(bpy.data.filepath).parent.resolve()
    target_path = Path(bpy.path.abspath(filepath)).resolve(strict=False)
    try:
        # NOTE: Path.relative_to (pathlib) does not support paths outside its base location before Python 3.12
        # https://docs.python.org/3.12/library/pathlib.html#pathlib.PurePath.relative_to
        # Blender will remain on Python 3.11 until 2026 https://vfxplatform.com/ so use os.path.relpath until then
        return Path(os.path.relpath(str(target_path), str(blend_dir)))
    except ValueError:
        return target_path  # Happens if on another drive


def sort_blender_objects_by_name(objects: list[BlenderRef]) -> list[BlenderRef]:
    return sorted(objects, key=lambda x: x.name)


"""
Blenders outliner does not follow a stricly lexographical ordering, but rather what is called a "natural" ordering.
This function implements the same ordering as per:
https://github.com/blender/blender/blob/b0e7a6db56caf6669b6fade1622710d70b96483e/source/blender/blenlib/intern/string.c#L727,
with the use of a regex as detailed in this answer on stackoverflow https://stackoverflow.com/a/16090640
"""

_SPLIT_NUM = re.compile(r"(\d+)")


def sort_blender_objects_by_outliner_ordering(objects: list[BlenderRef]) -> list[BlenderRef]:
    return sorted(objects, key=lambda s: [int(t) if t.isdigit() else t.lower() for t in _SPLIT_NUM.split(s.name)])


def get_fs_data_path(as_path: bool = False) -> str | Path:
    """Returns the path to the Farming Simulator data directory."""
    fs_data_path = bpy.context.preferences.addons[__package__].preferences.fs_data_path
    if as_path:
        return Path(fs_data_path)
    return fs_data_path


def strip_sorting_prefix(name: str, sep: str) -> str:
    """Strip leading '<digits><sep>' from name (e.g. '12:Cube' -> 'Cube')."""
    if not name or not sep:
        return name
    head, found, tail = name.partition(sep)  # Split at first occurrence of sep
    if found and head.isdigit() and tail:
        return tail
    return name
