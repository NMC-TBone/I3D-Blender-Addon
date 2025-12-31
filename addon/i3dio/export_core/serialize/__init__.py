_needs_reload = "bpy" in locals()

import bpy

from . import emit_files, emit_materials, emit_scene, indexed_triangle_set_stream

if _needs_reload:
    import importlib

    emit_files = importlib.reload(emit_files)
    emit_materials = importlib.reload(emit_materials)
    emit_scene = importlib.reload(emit_scene)
    indexed_triangle_set_stream = importlib.reload(indexed_triangle_set_stream)
    print("i3dio export_core.serialize reloaded")
