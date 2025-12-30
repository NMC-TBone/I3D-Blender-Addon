# i3dio/export_core/serialize/emit_files.py
from __future__ import annotations

from typing import TYPE_CHECKING

from ... import xml_i3d

if TYPE_CHECKING:
    from ..ctx import ExportContext


def emit_files(ctx: "ExportContext", files_elem) -> None:
    """
    Write <Files> entries from ctx.files.

    Expects ctx.files.finalize() to have run so each entry has resolved_path.
    """
    for e in ctx.files.entries():
        if e.resolved_path is None:
            continue

        # filename is the resolved (export) path
        # IMPORTANT: Path -> posix for I3D
        xml_i3d.SubElement(
            files_elem,
            "File",
            {
                "fileId": str(e.id),
                "filename": e.resolved_path.as_posix(),
            },
        )
