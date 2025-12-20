# i3dio/node_classes/__init__.py

_needs_reload = "bpy" in locals()

import bpy

# If you keep a compat shim shape.py (recommended), import it too.
from . import animation, file, material, merge_children, merge_group, node, shape, skinned_mesh

if _needs_reload:
    import importlib
    file = importlib.reload(file)
    material = importlib.reload(material)
    node = importlib.reload(node)
    shape = importlib.reload(shape)
    merge_group = importlib.reload(merge_group)
    merge_children = importlib.reload(merge_children)
    skinned_mesh = importlib.reload(skinned_mesh)
    animation = importlib.reload(animation)
    print("i3dio Add-on Reloaded")
