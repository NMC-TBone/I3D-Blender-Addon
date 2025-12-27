_needs_reload = "bpy" in locals()

import bpy

from . import kinds, mappings, names, runner

if _needs_reload:
    import importlib

    kinds = importlib.reload(kinds)
    names = importlib.reload(names)
    mappings = importlib.reload(mappings)
    runner = importlib.reload(runner)
    print("i3dio export_core.resolve reloaded")

# Re-export the public entrypoint
resolve_all = runner.resolve_all
