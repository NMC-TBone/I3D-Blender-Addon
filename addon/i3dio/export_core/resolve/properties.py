# i3dio/export_core/resolve/properties.py
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import bpy
import mathutils

from ..ir import EmitTag, NodeKind, SceneNode, XmlBuckets, node_emit_tag

if TYPE_CHECKING:
    from ..ctx import ExportContext
    from ..tables.materials import MaterialEntry

_EPS_FLOAT = 1e-6
_EPS_VEC = 1e-6


@dataclass(frozen=True, slots=True)
class TrackingSpec:
    member_path: str
    value_gate: Any | None
    mapping: dict[Any, Any] | None


@dataclass(frozen=True, slots=True)
class DependsSpec:
    name: str
    value: Any


@dataclass(frozen=True, slots=True)
class PropSpec:
    key: str
    placement: str  # "Node" or child tag
    name: str | None
    default: Any
    field_type: str | None
    override: Any | None
    depends: tuple[DependsSpec, ...]
    tracking: TrackingSpec | None


_SPECS_CACHE: dict[type, tuple[PropSpec, ...]] = {}


class _SkipSentinel:
    __slots__ = ()


_SKIP = _SkipSentinel()


def resolve_properties(ctx: "ExportContext", node: SceneNode) -> None:
    ref = node.blender_ref
    if not isinstance(ref, bpy.types.Object):
        return

    pg_obj = getattr(ref, "i3d_attributes", None)
    if pg_obj is not None:
        _collect_pg(owner=ref, pg=pg_obj, out=node.xml)

    data = getattr(ref, "data", None)
    pg_data = getattr(data, "i3d_attributes", None) if data is not None else None
    if pg_data is not None and node_emit_tag(node) in {EmitTag.SHAPE, EmitTag.LIGHT}:
        _collect_pg(owner=data, pg=pg_data, out=node.xml)
    _resolve_reference_path(ctx, node)

    if node.kind == NodeKind.CAMERA and isinstance(data, bpy.types.Camera):
        _collect_camera_builtin(data, node.xml.node)


def resolve_material_properties(ctx: "ExportContext", entry: "MaterialEntry") -> None:
    mat = entry.blender_material
    if mat is None or not isinstance(mat, bpy.types.Material):
        return

    pg_mat = getattr(mat, "i3d_attributes", None)
    if pg_mat is not None:
        _collect_pg(owner=mat, pg=pg_mat, out=entry.xml)


def _collect_camera_builtin(cam: bpy.types.Camera, out: dict[str, Any]) -> None:
    out.setdefault("fov", cam.lens)
    out.setdefault("nearClip", cam.clip_start)
    out.setdefault("farClip", cam.clip_end)
    if cam.type == "ORTHO":
        out.setdefault("orthographic", True)
        out.setdefault("orthographicHeight", cam.ortho_scale)


def _resolve_reference_path(ctx: "ExportContext", node: SceneNode) -> None:
    # Only TransformGroups should carry reference info
    ref = node.blender_ref
    if node.kind != NodeKind.TRANSFORM_GROUP or not isinstance(ref, bpy.types.Object):
        return
    if not (reference_path := ref.i3d_reference.path):
        return  # no reference set

    if not reference_path.lower().endswith(".i3d"):
        ctx.node_reporter(node, "properties").warning("Reference path does not end with '.i3d': %r", reference_path)
        return
    node.xml.node["referenceId"] = ctx.files.add_reference(reference_path)
    if not ref.i3d_reference.runtime_loaded:
        node.xml.node["referenceRuntimeLoaded"] = False  # default is True, only write when False

    if child_path := ref.i3d_reference.child_path.strip():
        node.xml.node["referenceChildPath"] = child_path


def _compile_specs(pg: Any) -> tuple[PropSpec, ...]:
    cls = type(pg)
    cached = _SPECS_CACHE.get(cls)
    if cached is not None:
        return cached

    i3d_map: dict[str, dict[str, Any]] = getattr(pg, "i3d_map", {})
    ann = getattr(pg, "__annotations__", {})

    specs: list[PropSpec] = []
    for key in ann.keys():
        info = i3d_map.get(key)
        if not info:
            continue

        placement = info.get("placement", "Node")
        if placement is None:
            continue  # UI-only

        depends_info = info.get("depends", []) or []
        depends = tuple(DependsSpec(d["name"], d["value"]) for d in depends_info)

        tracking_info = info.get("tracking")
        tracking = None
        if tracking_info:
            tracking = TrackingSpec(
                member_path=tracking_info["member_path"],
                value_gate=tracking_info.get("value"),
                mapping=tracking_info.get("mapping"),
            )

        specs.append(
            PropSpec(
                key=key,
                placement=placement,
                name=info.get("name"),
                default=info.get("default"),
                field_type=info.get("type"),
                override=info.get("override"),
                depends=depends,
                tracking=tracking,
            )
        )

    out = tuple(specs)
    _SPECS_CACHE[cls] = out
    return out


def _collect_pg(*, owner: Any, pg: Any, out: XmlBuckets) -> None:
    specs = _compile_specs(pg)

    for spec in specs:
        if not _deps_ok(owner=owner, pg=pg, spec=spec):
            continue

        val = _effective_value(owner=owner, pg=pg, spec=spec)
        if val is _SKIP:
            continue

        if _is_default(val, spec.default):
            continue

        i3d_name, value_to_write = _convert_for_export(val, spec)
        if value_to_write is _SKIP:
            continue

        if spec.placement == "Node":
            out.node[i3d_name] = value_to_write
        else:
            out.children.setdefault(spec.placement, {})[i3d_name] = value_to_write


def _deps_ok(*, owner: Any, pg: Any, spec: PropSpec) -> bool:
    for dep in spec.depends:
        dep_val = _effective_value_by_name(owner=owner, pg=pg, prop_name=dep.name)
        if dep_val is _SKIP or dep_val != dep.value:
            return False
    return True


def _effective_value_by_name(*, owner: Any, pg: Any, prop_name: str) -> Any:
    # Uses the exact same semantics as your current effective_value() (including tracking if configured)
    val = getattr(pg, prop_name, _SKIP)
    if val is _SKIP:
        return _SKIP

    i3d_map: dict[str, dict[str, Any]] = getattr(pg, "i3d_map", {})
    info = i3d_map.get(prop_name, {})
    tracking = info.get("tracking")

    tracking_flag_name = f"{prop_name}_tracking"
    tracking_enabled = bool(getattr(pg, tracking_flag_name, False))

    if tracking_enabled and tracking:
        if "value" in tracking and getattr(owner, tracking["member_path"], None) != tracking["value"]:
            return _SKIP

        raw = getattr(owner, tracking["member_path"])
        mapping = tracking.get("mapping")
        return mapping.get(raw, raw) if mapping else raw

    return val


def _effective_value(*, owner: Any, pg: Any, spec: PropSpec) -> Any:
    val = getattr(pg, spec.key)

    tracking_flag_name = f"{spec.key}_tracking"
    tracking_enabled = bool(getattr(pg, tracking_flag_name, False))

    if tracking_enabled and spec.tracking is not None:
        tr = spec.tracking
        raw = getattr(owner, tr.member_path, None)

        if tr.value_gate is not None and raw != tr.value_gate:
            return _SKIP

        return tr.mapping.get(raw, raw) if tr.mapping else raw

    return val


def _convert_for_export(val: Any, spec: PropSpec) -> tuple[str, Any]:
    # Preserve your existing behavior exactly:
    # name=None => "enum-name-is-value" special case
    i3d_name = spec.name
    value_to_write: Any = val

    if i3d_name is None:
        i3d_name = str(val)
        value_to_write = 1

    ft = spec.field_type
    if ft == "HEX":
        s = _hex_to_prefixed_str(val)
        if s is None:
            return i3d_name, _SKIP
        value_to_write = s
    elif ft == "OVERRIDE":
        value_to_write = spec.override
    elif ft == "ANGLE":
        value_to_write = math.degrees(float(val))

    return i3d_name, value_to_write


def _hex_to_prefixed_str(val: object) -> str | None:
    """
    Accepts:
      - "ff", "0xff", "FF", "10004"
      - 255
    Returns:
      - "0xff", "0x10004" (lowercase, no leading zeros)
    """
    if isinstance(val, int):
        n = val
    else:
        s = str(val).strip().lower()
        if not s:
            return None
        if s.startswith("0x"):
            s = s[2:]
        try:
            n = int(s, 16)
        except ValueError:
            return None

    # Bound check
    if not (0 <= n <= 2**32 - 1):
        return None

    return f"0x{n:x}"


def _is_default(val: Any, default: Any) -> bool:
    if isinstance(val, float) and isinstance(default, (float, int)):
        return math.isclose(val, float(default), abs_tol=_EPS_FLOAT)

    if isinstance(val, (tuple, list, mathutils.Color)) or isinstance(val, bpy.types.bpy_prop_array):
        v = tuple(val)
        d = tuple(default) if isinstance(default, (tuple, list)) else default
        if not isinstance(d, (tuple, list)) or len(v) != len(d):
            return False
        return all(math.isclose(float(a), float(b), abs_tol=_EPS_VEC) for a, b in zip(v, d))

    return val == default
