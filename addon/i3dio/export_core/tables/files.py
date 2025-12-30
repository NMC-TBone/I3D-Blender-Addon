# i3dio/export_core/tables/files.py
from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import bpy

from ... import utility
from ..ids import IdKind
from .base import IdEntryTable

if TYPE_CHECKING:
    from ..ctx import ExportContext
    from ..reporting import Reporter


FileKind = Literal["image", "shader", "reference", "generic"]


_MODHUB_FOLDER: dict[FileKind, str] = {
    "image": "textures",
    "shader": "shaders",
    "reference": "assets",
    "generic": "",
}


@dataclass(slots=True)
class FileEntry:
    id: int
    kind: FileKind
    blender_path: str  # as stored in Blender (relative, //, or absolute)
    resolved_path: Path | None = None  # export-side path ($data..., relative to i3d folder, or absolute)


@dataclass(slots=True)
class FileTable(IdEntryTable[FileEntry, tuple[FileKind, str]]):
    """
    Modern replacement for the old Node-based File/Image/Shader/Reference system.

    Responsibilities (mirrors legacy behavior):
      - de-duplicate file registrations and provide stable file IDs
      - finalize() resolves each file path for export and optionally copies it
    """

    ctx: "ExportContext"
    _by_key: dict[tuple[FileKind, str], int] = field(default_factory=dict)
    _entries: dict[int, FileEntry] = field(default_factory=dict)

    def _alloc_entry(self, *, key: tuple[FileKind, str], kind: FileKind, blender_path: str) -> int:
        fid = self.ctx.ids.alloc(IdKind.FILE)
        self.register(key=key, entry_id=fid, entry=FileEntry(id=fid, kind=kind, blender_path=blender_path))
        return fid

    def add(self, *, kind: FileKind, blender_path: str) -> int:
        key = (kind, blender_path)
        if (fid := self.get_id(key)) is not None:
            return fid
        return self._alloc_entry(key=key, kind=kind, blender_path=blender_path)

    def add_reference(self, blender_path: str) -> int:
        return self.add(kind="reference", blender_path=blender_path)

    def add_image(self, blender_path: str) -> int:
        return self.add(kind="image", blender_path=blender_path)

    def add_shader(self, blender_path: str) -> int:
        return self.add(kind="shader", blender_path=blender_path)

    # finalize / resolve / copy

    def finalize(self) -> None:
        """
        Resolve all registered file paths and copy them if requested.

        This is the new equivalent of each File node resolving itself during
        construction in the old Node hierarchy.
        """
        rep = self.ctx.section("files")
        rep.info("Finalizing %d registered files", len(self._entries))
        for e in self._entries.values():
            self._resolve_entry(rep, e)
        rep.info("File finalization complete")

    def _resolve_entry(self, rep: Reporter, e: FileEntry) -> None:
        """Legacy-equivalent of File._resolve_filepath()"""
        rep.debug("Resolving file %r of kind %r", e.blender_path, e.kind)
        e.resolved_path = utility.as_export_path(e.blender_path)

        # FS builtin: $data prefix, never copied
        if str(e.resolved_path).startswith("$data"):
            rep.info("Resolved as FS $data path: %s", e.resolved_path)
            return

        if self.ctx.settings.get("copy_files", False):
            self._copy_entry(rep, e)
            return

        rep.info("Resolved filepath: %s", e.resolved_path)
        if e.resolved_path.is_absolute():
            rep.warning("File %r is outside the blend file folder; using absolute path in I3D.", e.blender_path)

    def _copy_entry(self, rep: Reporter, e: FileEntry) -> None:
        """
        Legacy-equivalent of File._copy_file()

        Uses settings:
          - file_structure: FLAT | MODHUB | BLENDER
          - overwrite_files: bool
        """
        i3d_folder = Path(self.ctx.paths["i3d_folder"])
        write_directory = i3d_folder
        resolved_directory = Path()

        rep.info("File is not an FS builtin and will be copied")

        file_structure = self.ctx.settings.get("file_structure", "MODHUB")

        match file_structure:
            case "FLAT":
                rep.debug("Will be copied using the 'FLAT' hierarchy structure")
                resolved_directory = Path()
                write_directory = i3d_folder

            case "MODHUB":
                rep.debug("Will be copied using the 'MODHUB' hierarchy structure")
                modhub = _MODHUB_FOLDER.get(e.kind, "")
                resolved_directory = Path(modhub) if modhub else Path()
                write_directory = i3d_folder / resolved_directory

            case "BLENDER":
                rep.debug("Will be copied using the 'BLENDER' hierarchy structure")

                # --- ported legacy safety limit ---
                blender_relative_distance_limit = 3  # Limits the distance a file can be from the blend file
                blender_path = Path(e.blender_path)

                # Legacy code counted "..\\" only (Windows). Keep that to avoid behavior change.
                # (If you later want to improve this, do it intentionally with a migration.)
                if e.blender_path.count("..\\") <= blender_relative_distance_limit:
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
                    e.resolved_path = Path(bpy.path.abspath(e.blender_path))
                    return

            case _:
                rep.debug("Unknown file_structure=%r; defaulting to 'MODHUB'", file_structure)
                modhub = _MODHUB_FOLDER.get(e.kind, "")
                resolved_directory = Path(modhub) if modhub else Path()
                write_directory = i3d_folder / resolved_directory

        # Destination relative path that will be written into the I3D <File filename="...">
        file_name = bpy.path.display_name_from_filepath(e.blender_path)
        file_extension = (
            e.blender_path[e.blender_path.rfind(".") : len(e.blender_path)] if "." in e.blender_path else ""
        )
        e.resolved_path = resolved_directory / f"{file_name}{file_extension}"

        # Ensure we do not overwrite the source file
        source_path = Path(bpy.path.abspath(e.blender_path))
        if not source_path.exists():
            rep.warning("File %r does not exist, cannot copy", source_path)
            return

        # Legacy had a check comparing resolved_path to source_path, but resolved_path is relative.
        # The meaningful comparison is full destination vs source.
        write_path_full = write_directory / f"{file_name}{file_extension}"

        if write_path_full == source_path:
            rep.debug("Source and destination paths are the same, no need to copy")
            return

        overwrite_files = self.ctx.settings.get("overwrite_files", False)
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
