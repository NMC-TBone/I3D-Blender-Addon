import bpy

from ..ctx import ExportContext
from ..ir import NodeKind


def _classify_object(ctx: ExportContext, obj: bpy.types.Object) -> NodeKind:
    match obj.type:
        case "CAMERA":
            return NodeKind.CAMERA
        case "LIGHT":
            return NodeKind.LIGHT
        case "MESH":
            return NodeKind.SHAPE
        case "ARMATURE":
            return NodeKind.ARMATURE
    return NodeKind.TRANSFORM_GROUP
