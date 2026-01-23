from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING

import bpy

from .... import utility
from ...resources.files import _MODHUB_FOLDER, FileEntry

if TYPE_CHECKING:
    from ...ctx import ExportContext
    from ...reporting import Reporter


def resolve_files(ctx: "ExportContext") -> None:
    """Resolve all registered file paths and copy them if requested."""
    rep = ctx.reporter("files")
    entries = ctx.files.entries()
    rep.info("Finalizing %d registered files", len(entries))
    for entry in entries:
        _resolve_entry(ctx, rep, entry)
    rep.info("File finalization complete")


def _resolve_entry(ctx: "ExportContext", rep: Reporter, entry: FileEntry) -> None:
    """Legacy-equivalent of File._resolve_filepath()."""
    rep.debug("Resolving file %r of kind %r", entry.blender_path, entry.kind)
    entry.resolved_path = utility.as_export_path(entry.blender_path)

    # FS builtin: $data prefix, never copied
    if str(entry.resolved_path).startswith("$data"):
        rep.info("Resolved as FS $data path: %s", entry.resolved_path)
        return

    if ctx.setting("copy_files", False):
        _copy_entry(ctx, rep, entry)
        return

    rep.info("Resolved filepath: %s", entry.resolved_path)
    if entry.resolved_path.is_absolute():
        rep.warning("File %r is outside the blend file folder; using absolute path in I3D.", entry.blender_path)


def _copy_entry(ctx: "ExportContext", rep: Reporter, entry: FileEntry) -> None:
    """
    Legacy-equivalent of File._copy_file().

    Uses settings:
      - file_structure: FLAT | MODHUB | BLENDER
      - overwrite_files: bool
    """
    rep.info("File is not an FS builtin and will be copied")
    dirs = _resolve_copy_directories(ctx, rep, entry)
    if dirs is None:
        return
    resolved_directory, write_directory = dirs

    # Destination relative path that will be written into the I3D <File filename="...">
    file_name, file_extension = _file_name_and_ext(entry.blender_path)
    entry.resolved_path = resolved_directory / f"{file_name}{file_extension}"

    # Ensure we do not overwrite the source file
    source_path = Path(bpy.path.abspath(entry.blender_path))
    if not source_path.exists():
        rep.warning("File %r does not exist, cannot copy", source_path)
        return

    # Legacy had a check comparing resolved_path to source_path, but resolved_path is relative.
    # The meaningful comparison is full destination vs source.
    write_path_full = write_directory / f"{file_name}{file_extension}"

    if write_path_full == source_path:
        rep.debug("Source and destination paths are the same, no need to copy")
        return

    overwrite_files = ctx.setting("overwrite_files", False)
    if overwrite_files or not write_path_full.exists():
        write_directory.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy(source_path, write_directory)
        except shutil.SameFileError:
            pass  # Ignore if source and destination is the same file
        else:
            rep.info("Copied to %r", write_path_full)
    else:
        rep.debug("File already in correct path relative to i3d file and overwrite is turned off")


def _resolve_copy_directories(ctx: "ExportContext", rep: Reporter, entry: FileEntry) -> tuple[Path, Path] | None:
    i3d_folder = ctx.i3d_folder
    resolved_directory = Path()
    write_directory = i3d_folder

    file_structure = ctx.setting("file_structure", "MODHUB")

    match file_structure:
        case "FLAT":
            rep.debug("Will be copied using the 'FLAT' hierarchy structure")
            resolved_directory = Path()
            write_directory = i3d_folder

        case "MODHUB":
            rep.debug("Will be copied using the 'MODHUB' hierarchy structure")
            modhub = _MODHUB_FOLDER.get(entry.kind, "")
            resolved_directory = Path(modhub) if modhub else Path()
            write_directory = i3d_folder / resolved_directory

        case "BLENDER":
            rep.debug("Will be copied using the 'BLENDER' hierarchy structure")

            # --- ported legacy safety limit ---
            blender_relative_distance_limit = 3  # Limits the distance a file can be from the blend file
            blender_path = Path(entry.blender_path)

            # Legacy code counted "..\\" only (Windows). Keep that to avoid behavior change.
            # (If you later want to improve this, do it intentionally with a migration.)
            if entry.blender_path.count("..\\") <= blender_relative_distance_limit:
                # Remove relative notation and get the directory path
                # (legacy: Path(*blender_path.parts[2:]))
                resolved_directory = Path(*blender_path.parts[2:])
                write_directory = i3d_folder / resolved_directory
            else:
                rep.debug(
                    "File exists more than %d folders away from .blend file. "
                    "Defaulting to absolute path and no copying.",
                    blender_relative_distance_limit,
                )
                entry.resolved_path = Path(bpy.path.abspath(entry.blender_path))
                return None

        case _:
            rep.debug("Unknown file_structure=%r; defaulting to 'MODHUB'", file_structure)
            modhub = _MODHUB_FOLDER.get(entry.kind, "")
            resolved_directory = Path(modhub) if modhub else Path()
            write_directory = i3d_folder / resolved_directory

    return resolved_directory, write_directory


def _file_name_and_ext(blender_path: str) -> tuple[str, str]:
    file_name = bpy.path.display_name_from_filepath(blender_path)
    file_extension = blender_path[blender_path.rfind(".") : len(blender_path)] if "." in blender_path else ""
    return file_name, file_extension
