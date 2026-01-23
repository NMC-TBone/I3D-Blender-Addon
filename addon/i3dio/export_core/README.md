# export_core Overview

This package implements the core of the I3D export pipeline for Blender. It is responsible for traversing the Blender scene, building an intermediate representation (IR), resolving all necessary data (geometry, materials, animations, etc.), and serializing the result to the I3D file format.

## Pipeline Stages

1. **Scene Traversal**
   - The pipeline starts by traversing the Blender scene graph and collecting all relevant objects.
   - See: `traverse.py`

2. **IR Construction**
   - The scene is converted into an intermediate representation (`ir/`), which is a tree of `SceneNode` objects.
   - See: `ir/builder.py`, `ir/model.py`

3. **Resolution Passes**
   - Multiple passes fill in details on the IR:
     - Node kinds (`resolve/common/kinds.py`)
     - Materials (`resolve/common/materials.py`)
     - Shapes and geometry (`resolve/shapes/`)
     - Animations (`resolve/animations/`)
     - File paths, user attributes, etc.
   - Each pass is responsible for a specific aspect and may depend on previous passes.

4. **Resource Management**
   - All deduplicated resources (materials, files, shapes) are managed in `resources/`.
   - Tables like `MaterialTable`, `FileTable`, and `ShapeTable` ensure stable IDs and deduplication.

5. **Geometry Building**
   - Meshes are converted to indexed triangle sets (`geometry/mesh/its.py`).
   - Future: Curves and other geometry types will be supported via a common `BuiltShape` base.

6. **Serialization**
   - The fully resolved IR and resources are serialized to I3D XML and binary data.
   - See: `serialize/`

## Key Concepts

- **NodeKind**: Every node in the IR has a kind (e.g., SHAPE, GROUP, LIGHT). After `resolve/kinds`, no node is left as `UNRESOLVED`.
    - After `resolve/kinds`: no `UNRESOLVED` nodes remain
    - `set_kind()` is the only way kinds change
    - Any `NodeKind.SHAPE` node must have a `_shape` extension (guaranteed by `set_kind()`)
- **ShapeEntry / BuiltShape**: Shapes are deduplicated and built into geometry objects (e.g., `BuiltITS` for meshes).
- **Resource Tables**: All files, materials, and shapes are registered and assigned stable IDs for export.
- **Pass System**: The pipeline is modular, with each pass responsible for a specific aspect of the export.

## Extending the Pipeline

- To add new geometry types (e.g., curves), implement a new `BuiltShape` subclass and add a resolution pass.
- To add new exportable properties, add a new pass in `resolve/` and update the IR and serialization as needed.

## File Structure

- `traverse.py` — Scene traversal
- `ir/` — Intermediate representation (SceneNode, NodeKind, etc.)
- `resolve/` — Resolution passes (materials, shapes, animations, etc.)
- `resources/` — Resource tables (deduplication and ID management)
- `geometry/` — Geometry building (meshes, future: curves)
- `serialize/` — I3D/XML serialization

---