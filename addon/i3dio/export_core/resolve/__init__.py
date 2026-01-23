_needs_reload = "bpy" in locals()

import bpy

from . import runner
from .common import kinds, mappings, materials, names, user_attributes

if _needs_reload:
    import importlib

    kinds = importlib.reload(kinds)
    names = importlib.reload(names)
    mappings = importlib.reload(mappings)
    materials = importlib.reload(materials)
    runner = importlib.reload(runner)
    user_attributes = importlib.reload(user_attributes)
    if getattr(bpy.app, "debug", False) or getattr(bpy.app, "debug_python", False):
        print("i3dio export_core.resolve reloaded")

# Re-export the public entrypoint
resolve_all = runner.resolve_all
