# i3dio/export_core/serialize/emit_i3d_mappings.py
from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

import bpy

from ..ctx import ExportContext
from ..reporting import Reporter


def _iter_tree_preorder(ctx: ExportContext):
    """Yield node ids in root-first preorder."""
    nodes = ctx.ir.scene_nodes
    stack = list(reversed(ctx.ir.roots))  # reverse so first root is processed first
    while stack:
        nid = stack.pop()
        yield nid
        kids = nodes[nid].children
        stack.extend(reversed(kids))


def _build_index_paths(ctx: ExportContext) -> dict[int, str]:
    """
    Build mapping node index strings like:
      root: "0>"
      child: "0>2|1"
    (matches your legacy format)
    """
    nodes = ctx.ir.scene_nodes
    roots = ctx.ir.roots

    paths: dict[int, str] = {}

    # stack items: (nid, path_string)
    stack: list[tuple[int, str]] = []

    for root_i, root_id in enumerate(roots):
        root_path = f"{root_i}>"
        paths[root_id] = root_path
        stack.append((root_id, root_path))

        while stack:
            pid, ppath = stack.pop()
            kids = nodes[pid].children

            # push in reverse so traversal order matches original child order
            for child_i in range(len(kids) - 1, -1, -1):
                cid = kids[child_i]

                # root path ends with ">", so first child becomes "0>0" (no "|")
                if ppath.endswith(">"):
                    cpath = ppath + str(child_i)
                else:
                    cpath = ppath + "|" + str(child_i)

                paths[cid] = cpath
                stack.append((cid, cpath))

    return paths


def _detect_newline(lines: list[str]) -> str:
    return "\r\n" if any(line.endswith("\r\n") for line in lines) else "\n"


def _find_or_insert_block(
    reporter: Reporter,
    lines: list[str],
    *,
    open_tag: str,
    close_tag: str,
    default_indent: str = " " * 4,
) -> tuple[int, int, str] | None:
    """
    Return (open_idx, close_idx, base_indent). Inserts a new empty block if missing.
    base_indent is the indentation of the open tag line.
    """
    open_idx = None
    close_idx = None
    base_indent = default_indent
    last_closing_idx = None

    for i, line in enumerate(lines):
        stripped = line.strip()
        if open_idx is None and stripped.startswith(open_tag):
            open_idx = i
            lt = line.find("<")
            if lt != -1:
                base_indent = line[:lt]
        elif stripped.startswith("</") and stripped.endswith(">"):
            last_closing_idx = i

        if stripped.startswith(close_tag):
            close_idx = i

    if open_idx is None:
        if last_closing_idx is None:
            reporter.warn("Could not locate root closing tag; aborting.")
            return None

        nl = _detect_newline(lines)
        open_idx = last_closing_idx
        lines.insert(open_idx, f"{base_indent}{open_tag}{nl}")
        lines.insert(open_idx + 1, f"{base_indent}{close_tag}{nl}")
        close_idx = open_idx + 1

    if close_idx is None:
        for i in range(open_idx + 1, len(lines)):
            if close_tag in lines[i]:
                close_idx = i
                break
        if close_idx is None:
            reporter.warn(f"{open_tag} found but no closing tag; aborting.")
            return None

    return open_idx, close_idx, base_indent


def _xml_attr(s: str) -> str:
    return xml_escape(s, {'"': "&quot;"})


def emit_i3d_mappings(ctx: ExportContext) -> None:
    reporter = ctx.reporter("i3dMappings")
    file_path_raw = ctx.settings.get("i3d_mapping_file_path", "")
    if not file_path_raw:
        return

    file_path = Path(bpy.path.abspath(file_path_raw))
    if not file_path.exists():
        reporter.warn(f"file not found: {str(file_path)!r}")
        return

    index_paths = _build_index_paths(ctx)

    mapped: list[tuple[str, str]] = []
    for nid in _iter_tree_preorder(ctx):
        node = ctx.ir.scene_nodes[nid]
        if not node.attrs.get("i3d_mapping"):
            continue

        mapping_name = node.attrs.get("i3d_mapping_name") or node.name or ""
        mapped.append((mapping_name, index_paths[nid]))

    if not mapped:
        reporter.info("No nodes with i3d_mapping attribute; skipping.")
        return

    lines = file_path.read_text(encoding="utf-8").splitlines(keepends=True)
    nl = _detect_newline(lines)

    try:
        result = _find_or_insert_block(
            reporter, lines, open_tag="<i3dMappings>", close_tag="</i3dMappings>", default_indent=" " * 4
        )
        if result is None:
            return
        open_i, close_i, base_indent = result
    except Exception:
        reporter.exception("Unexpected error; skipping.")
        return

    entry_indent = base_indent + (" " * 4)  # one level deeper than <i3dMappings>

    # XML-escape ids just in case (names can be arbitrary)
    new_entries = [f'{entry_indent}<i3dMapping id="{_xml_attr(mid)}" node="{path}" />{nl}' for mid, path in mapped]

    # Replace contents between open/close (keep the tags)
    lines[open_i + 1 : close_i] = new_entries
    file_path.write_text("".join(lines), encoding="utf-8")
    reporter.info(f"Wrote {len(new_entries)} entries to {str(file_path)!r}")
