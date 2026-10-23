# Outlaw Forge Native Application

The Qt Quick 3D application is a local mesh workbench. It has no geometry API, HTTP client, or service startup requirement. Mesh import, inspection, repair, auto-orient, planar cutting, connected-component splitting, deterministic vertex-clustering simplification, and STL export run in the native process. STL, OBJ, and limited 3MF files are read from disk; source files remain unchanged. Save Project and Open Project persist and restore scene instances and the geometry revisions they use in a self-contained `.oforge` project folder.

The viewport uses a right-handed Z-up scene measured in millimetres. It includes a build plate, lighting, camera controls, Top/Front/Right/Isometric views, an orientation gizmo, instance selection, hide/remove/duplicate, non-destructive transforms, and placement controls. The File, Edit, View, Window, and Settings menus contain the matching native actions.

Geometry tools:

- **Analyze** counts triangles, degenerate faces, boundary edges, and non-manifold edges.
- **Repair** welds vertices within the selected tolerance, removes degenerate triangles, and fills simple planar boundary loops. Branched and non-planar openings are left open and remain visible in the analysis report.
- **Auto Orient** scores deterministic candidate rotations from large face normals and cardinal directions, then bakes the selected orientation and places the mesh on the build plate.
- **Cut and Separate** clips the selected mesh locally against the movable plane. When enabled, both sections become separate scene instances. Cut faces are capped when the contour is closed and can be triangulated; the status reports any remaining open boundaries.
- **Split components** creates one selectable derived scene mesh for each edge-connected triangle component. Components are ordered by triangle count, with source order breaking ties; their placement is preserved under the selected instance transform.
- **Simplify mesh** creates a derived mesh using deterministic vertex clustering and a bounded search budget. It currently accepts meshes up to 1,000,000 triangles. The requested reduction is a target; the achieved triangle count and reduction are reported because clustering cannot guarantee an exact target or preserve every feature.
- **Export STL** saves the selected mesh revision as a binary STL in millimetres. The current instance translation, rotation, and scale are baked into the exported triangles; negative-scale transforms preserve face winding. The imported source file remains unchanged.
- **Save Project / Open Project** store `project.json` and immutable, content-addressed binary STL snapshots under `meshes/`. The version-1 manifest preserves instance order, geometry references, source-path provenance, visibility, transforms, and selection. A project opens without the original source file. Save As creates a `<name>.oforge` folder; Save updates its manifest. Dirty scenes prompt before project open, replacement import, or close. Camera and display state and operation history are not persisted.

## Build

Requirements: CMake 3.21+, a C++20 compiler, and Qt 6.6+ with Quick, Quick 3D, Quick Controls 2, and CorePrivate.

```powershell
cmake -S apps/native -B build/native -DCMAKE_PREFIX_PATH="C:/Qt/6.8.0/msvc2022_64"
cmake --build build/native --config Release
./build/native/outlaw-forge-native.exe
```

On Windows, when `windeployqt` is available, the build copies the Qt runtime and QML modules beside the executable. Otherwise add the selected Qt `bin` directory to `PATH` before launching.

STL binary and ASCII files are supported. OBJ vertex positions and faces are supported, including positive and relative negative indices. The 3MF reader imports the first build item when it references a direct mesh object, applies its affine transform, and converts recognized units to millimetres. Component graphs, extra build items, materials, textures, vertex colors, and slicer project metadata are not imported. The reader uses Qt's private `QZipReader` API and must be rebuilt against the selected Qt installation. Native project folders use schema version 1; unsupported versions and invalid or missing mesh assets are rejected before the live scene is replaced.

The native target is separate from the Tauri workbench. The Tauri app retains its existing API-backed architecture; this local-only statement applies to `apps/native/`.
