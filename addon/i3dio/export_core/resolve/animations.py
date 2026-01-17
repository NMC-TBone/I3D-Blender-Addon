from __future__ import annotations

import contextlib
from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

import bpy
from bpy_extras import anim_utils

from ..ir import AnimationSetIR, ClipIR, KeyframeSample, KeyframesTrack, SourceKind
from .animation_reduce_keyframes import reduce_keyframe_samples_in_place
from .animation_sampling import compute_local_matrices_for_current_frame

if TYPE_CHECKING:
    from ..ctx import ExportContext


def _scene_fps(scene: bpy.types.Scene) -> float:
    # Blender's effective FPS is fps / fps_base
    fps = float(scene.render.fps)
    fps_base = float(scene.render.fps_base)
    return fps / fps_base if fps_base else fps


@contextlib.contextmanager
def _restore_frame(scene: bpy.types.Scene):
    """Context manager to restore the scene frame after sampling."""
    try:
        original_frame = int(scene.frame_current)
    except Exception:
        original_frame = None

    try:
        yield
    finally:
        if original_frame is not None:
            try:
                scene.frame_set(original_frame)
            except Exception:
                pass


@contextlib.contextmanager
def _temporary_unhide_objects(objs: set[bpy.types.Object]):
    """Temporarily unhides objects so frame changes update evaluation (important for baking)."""
    original_hide_state = {obj: bool(obj.hide_viewport) for obj in objs}
    try:
        for obj in objs:
            obj.hide_viewport = False
        yield
    finally:
        for obj, state in original_hide_state.items():
            try:
                obj.hide_viewport = state
            except Exception:
                pass


@dataclass(frozen=True, slots=True)
class _NodeSlot:
    node_id: int
    slot: object


def _get_slot_for_object(action: bpy.types.Action, obj: bpy.types.Object):
    """Best-effort slot lookup for obj under action.

    Prefer the slot Blender assigned on the animation_data (most reliable),
    then fall back to anim_utils helpers if present, then to heuristics.
    """
    ad = obj.animation_data
    if ad is not None and ad.action_slot is not None:
        return ad.action_slot

    if action.slots:
        # Heuristic: if there's only one slot, it's usually the correct one.
        if len(action.slots) == 1:
            return action.slots[0]

        # Try matching by slot name (often equals ID name)
        obj_name = obj.name
        for s in action.slots:
            if s.name == obj_name:
                return s

    return None


def _iter_action_to_node_slots(ctx: "ExportContext") -> dict[bpy.types.Action, list[_NodeSlot]]:
    """Return mapping action -> node slots for exported object nodes.

    Uses each exported object's animation_data.action assignment, but preserves per-object slots.
    This enables a single Action to drive multiple objects via multiple slots.
    """
    out: dict[bpy.types.Action, list[_NodeSlot]] = defaultdict(list)

    # Include non-emitted object nodes (e.g. collapsed armature objects) because
    # their bones can still be emitted and should receive animation.
    for node in ctx.ir.iter_nodes(emitted_only=False, source_kind=SourceKind.OBJECT):
        obj = node.obj
        ad = obj.animation_data
        if ad is None or ad.action is None:
            continue
        action = ad.action

        slot = _get_slot_for_object(action, obj)
        if slot is None:
            ctx.node_reporter(node, "animations").warning(
                "Object has action %r but no action slot could be resolved; skipping", action.name
            )
            continue

        out[action].append(_NodeSlot(node_id=node.id, slot=slot))

    return out


def _bone_names_in_channelbag(channelbag) -> set[str]:
    """Extract bone names referenced by pose bone FCurves in a channelbag."""
    out: set[str] = set()
    for fc in channelbag.fcurves:
        dp = fc.data_path or ""
        # Typical pattern: pose.bones["BoneName"].location / rotation / etc.
        key = 'pose.bones["'
        if key not in dp:
            continue
        try:
            rest = dp.split(key, 1)[1]
            bone_name = rest.split('"]', 1)[0]
        except Exception:
            continue
        if bone_name:
            out.add(bone_name)
    return out


def resolve_animations(ctx: "ExportContext") -> None:
    """Collect and bake animations into ctx.ir.animations.

    Current scope (intentionally conservative):
    - Uses each exported object's active action (obj.animation_data.action).
    - Bakes per-frame matrices (frame_range) into keyframes.
    - For armatures: exports keyframes for bones (not the armature object node itself).

    Future: action-slot/channelbag based linking can replace the discovery step without changing the serializer.
    """

    rep = ctx.reporter("animations")

    if not ctx.has_feature("ANIMATIONS"):
        rep.debug("Feature ANIMATIONS disabled; skipping")
        return

    scene = ctx.scene
    fps = _scene_fps(scene)

    action_to_node_slots = _iter_action_to_node_slots(ctx)
    if not action_to_node_slots:
        rep.debug("No exported objects with active actions; skipping")
        return

    affected_objects: set[bpy.types.Object] = {
        ctx.ir.scene_nodes[ns.node_id].obj for node_slots in action_to_node_slots.values() for ns in node_slots
    }

    with _restore_frame(scene), _temporary_unhide_objects(affected_objects):
        for action, node_slots in action_to_node_slots.items():
            if not len(action.layers):
                rep.debug("Action %r has no layers; skipping", action.name)
                continue
            start_frame, end_frame = map(int, action.frame_range)
            if end_frame < start_frame:
                continue

            duration_ms = ((end_frame - start_frame) / fps) * 1000.0 if fps else 0.0
            anim_set = AnimationSetIR(name=action.name)

            for layer in action.layers:
                clip_name = layer.name if layer is not None else action.name

                # Build target tracks for this (action, layer)
                target_node_ids: set[int] = set()

                for ns in node_slots:
                    node = ctx.ir.scene_nodes.get(ns.node_id)
                    if node is None:
                        continue

                    if (channelbag := anim_utils.action_get_channelbag_for_slot(action, ns.slot)) is None:
                        continue
                    if not channelbag.fcurves:
                        continue

                    # Armatures export bones (like the legacy exporter), objects export themselves.
                    if node.source_object_type == "ARMATURE":
                        bone_map = ctx.ir.index.bone_nodes_by_armature_ptr.get(node.source_ptr, {})
                        for bone_name in _bone_names_in_channelbag(channelbag):
                            if (bone_nid := bone_map.get(bone_name)) is not None:
                                target_node_ids.add(int(bone_nid))
                    else:
                        target_node_ids.add(int(node.id))

                if not target_node_ids:
                    continue

                tracks_by_node_id: dict[int, KeyframesTrack] = {
                    nid: KeyframesTrack(node_id=nid) for nid in ctx.ir.node_order if nid in target_node_ids
                }
                if not tracks_by_node_id:
                    continue

                clip = ClipIR(name=clip_name, duration_ms=duration_ms)
                rep.debug(
                    "Baking action %r clip %r (%d-%d) for %d nodes",
                    action.name,
                    clip_name,
                    start_frame,
                    end_frame,
                    len(tracks_by_node_id),
                )

                for frame in range(start_frame, end_frame + 1):
                    scene.frame_set(frame)
                    matrices = compute_local_matrices_for_current_frame(ctx)
                    time_ms = ((frame - start_frame) / fps) * 1000.0 if fps else 0.0

                    for nid, track in tracks_by_node_id.items():
                        m = matrices.get(nid)
                        if m is None:
                            continue
                        track.samples.append(KeyframeSample(time_ms=time_ms, matrix_local_export=m.copy()))

                removed_by_node_id: dict[int, int] = defaultdict(int)
                for nid, track in tracks_by_node_id.items():
                    before = len(track.samples)
                    reduce_keyframe_samples_in_place(ctx, track.samples)
                    after = len(track.samples)
                    if after != before:
                        removed_by_node_id[nid] += before - after

                if removed_by_node_id:
                    total_removed = sum(removed_by_node_id.values())
                    total_before = sum(
                        len(t.samples) + removed_by_node_id.get(t.node_id, 0) for t in tracks_by_node_id.values()
                    )
                    total_after = sum(len(t.samples) for t in tracks_by_node_id.values())
                    rep.debug(
                        "Reduced clip %r: removed %d samples (before %d, after %d)",
                        clip_name,
                        total_removed,
                        total_before,
                        total_after,
                    )

                clip.tracks.extend(tracks_by_node_id.values())
                anim_set.clips.append(clip)

            if anim_set.clips:
                ctx.ir.animations.sets.append(anim_set)

    rep.info("Resolved %d animation sets", len(ctx.ir.animations.sets))
