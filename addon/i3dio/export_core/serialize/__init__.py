_needs_reload = "bpy" in locals()

import bpy

from . import emit_animation, emit_files, emit_materials, emit_scene, emit_user_attributes, indexed_triangle_set_stream

if _needs_reload:
    import importlib

    emit_files = importlib.reload(emit_files)
    emit_animation = importlib.reload(emit_animation)
    emit_materials = importlib.reload(emit_materials)
    emit_scene = importlib.reload(emit_scene)
    emit_user_attributes = importlib.reload(emit_user_attributes)
    indexed_triangle_set_stream = importlib.reload(indexed_triangle_set_stream)
    if getattr(bpy.app, "debug", False) or getattr(bpy.app, "debug_python", False):
        print("i3dio export_core.serialize reloaded")
