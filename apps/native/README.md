# Outlaw Forge Native Application

The Qt Quick 3D application is a local mesh workbench. It has no geometry API, HTTP client, or service startup requirement. Add multiple STL, OBJ, or limited 3MF files as separate scene models, then inspect, transform, repair, auto-orient, cut, split, simplify, or combine them with solid Boolean operations. These operations and STL export run in the native process. Source files remain unchanged. Save Project and Open Project persist and restore scene instances and the geometry revisions they use in a self-contained `.oforge` project folder.

The viewport uses a right-handed Z-up scene measured in millimetres. It includes a configurable rectangular build plate, lighting, camera controls, Top/Front/Right/Isometric views, an orientation gizmo, instance selection, hide/remove/duplicate, non-destructive transforms, and placement controls. Arrange Build Plate packs visible instances largest-first with a user-selected gap and validates the entire layout before changing transforms. Center Selected recentres one visible instance. Both preserve model orientation and keep hidden instances untouched. Bed dimensions are session settings and are not saved in the project manifest yet. The File, Edit, View, Window, and Settings menus contain the matching native actions.

Geometry tools:

- **Analyze** counts triangles, degenerate faces, boundary edges, and non-manifold edges.
- **Repair** welds vertices within the selected tolerance, removes degenerate triangles, and fills simple planar boundary loops. Branched and non-planar openings are left open and remain visible in the analysis report.
- **Auto Orient** scores deterministic candidate rotations from large face normals and cardinal directions, then bakes the selected orientation and places the mesh on the build plate.
- **Cut and Separate** clips the selected mesh locally against the movable plane. When enabled, both sections become separate scene instances. Cut faces are capped when the contour is closed and can be triangulated; the status reports any remaining open boundaries.
- **Split components** creates one selectable derived scene mesh for each edge-connected triangle component. Components are ordered by triangle count, with source order breaking ties; their placement is preserved under the selected instance transform.
- **Simplify mesh** creates a derived mesh using deterministic vertex clustering and a bounded search budget. It accepts meshes up to 5,000,000 triangles. The requested reduction is a target; the achieved triangle count and reduction are reported because clustering cannot guarantee an exact target or preserve every feature.
- **Boolean operation** is available from Edit when two scene objects exist. Union, Difference, and Intersection use their current positions, rotations, and scales in millimetres. The result replaces the selected object as a new derived geometry and consumes the other input object or selected input objects after success. Unselected scene objects remain untouched. Both inputs must form closed manifold solids, and each input supports up to 5,000,000 triangles. Unsupported or empty results leave the scene unchanged.
- **Export STL** saves the selected mesh revision as a binary STL in millimetres. The current instance translation, rotation, and scale are baked into the exported triangles; negative-scale transforms preserve face winding. The imported source file remains unchanged.
- **Save Project / Open Project** store `project.json` and immutable, content-addressed binary STL snapshots under `meshes/`. The version-1 manifest preserves instance order, geometry references, source-path provenance, visibility, transforms, and selection. A project opens without the original source file. Save As creates a `<name>.oforge` folder; Save updates its manifest. Empty local sessions stay clean. When changes exist, the confirmation names the pending action, explains what will be replaced, and offers save, continue without saving, or cancel. Camera and display state and operation history are not persisted.

## Build

Requirements: CMake 3.21+, a C++20 compiler, and Qt 6.6+ with Quick, Quick 3D, Quick Controls 2, and CorePrivate.

The first CMake configure fetches the pinned Manifold 3.5.1 source archive and verifies its SHA-256. Manifold is built statically into the native executable, so the app has no network requirement at runtime. Its Apache-2.0 license is included in `THIRD_PARTY_LICENSE-Manifold.txt`.

```powershell
cmake -S apps/native -B build/native -DCMAKE_PREFIX_PATH="C:/Qt/6.8.0/msvc2022_64"
cmake --build build/native --config Release
./build/native/outlaw-forge-native.exe
```

On Windows, when `windeployqt` is available, the build copies the Qt runtime and QML modules beside the executable. Otherwise add the selected Qt `bin` directory to `PATH` before launching.

STL binary and ASCII files are supported. OBJ vertex positions and faces are supported, including positive and relative negative indices. The 3MF reader imports the first build item when it references a direct mesh object, applies its affine transform, and converts recognized units to millimetres. Component graphs, extra build items, materials, textures, vertex colors, and slicer project metadata are not imported. The reader uses Qt's private `QZipReader` API and must be rebuilt against the selected Qt installation. Native project folders use schema version 1; unsupported versions and invalid or missing mesh assets are rejected before the live scene is replaced.

The native target is separate from the Tauri workbench. The Tauri app retains its existing API-backed architecture; this local-only statement applies to `apps/native/`.
