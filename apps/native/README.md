# Outlaw Forge Native Application

This is the native viewport foundation: a C++/Qt Quick 3D executable with a Z-up millimetre scene, build plate, lighting, camera, STL/OBJ/limited 3MF import, scene selection, independent mesh instances, and non-destructive transforms. Imported sources remain read-only. STL and OBJ imports are also registered with the local geometry service for persistent, service-backed planar slicing, auto-orientation, and repair. The app remains separate from the current Tauri workbench while native workflows mature.

Viewport transforms: select a model, choose Move, Rotate, or Scale in the floating viewport toolbar, then drag the model. Move is measured in millimetres, rotation in degrees, and scale is a percentage in the inspector. Choose All, X, Y, or Z to constrain the operation. `G`, `R`, and `S` switch modes; `X`, `Y`, and `Z` choose an axis. Hold `Ctrl` while dragging to scale or `Alt` to rotate temporarily. Z is the vertical axis.

Other viewport shortcuts: `Ctrl+1` top, `Ctrl+2` front, `Ctrl+3` right, `Ctrl+4` isometric, `Ctrl+F` frame selected instance, `Ctrl+D` duplicate selected instance, `Ctrl+H` toggle visibility, and `Delete` remove selected instance.

## Build prerequisites

- CMake 3.21 or newer
- A C++20 compiler
- Qt 6.6 or newer with Quick, Quick 3D, Quick Controls 2, and Network

Configure and build from the repository root:

```powershell
cmake -S apps/native -B build/native -DCMAKE_PREFIX_PATH="C:/Qt/6.8.0/msvc2022_64"
cmake --build build/native --config Release
./build/native/outlaw-forge-native.exe
```

On Windows, when `windeployqt` is available in the selected Qt installation, the build automatically copies the Qt DLLs, QML modules, platform plugins, and compiler runtime beside the executable. This lets the executable start directly without adding the Qt `bin` folder to `PATH`. If deployment is unavailable, add the selected Qt `bin` directory to `PATH` before launching.

## Migration boundary

STL binary and ASCII files are supported. OBJ import reads vertex positions and faces, triangulates polygon faces, and handles positive or relative negative vertex indices. 3MF import reads the first build item when it references a direct mesh object, applies its affine transform, and converts the model's declared units to millimetres. 3MF component graphs, additional build items, materials, textures, vertex colors, and slicer project metadata are not imported. The current 3MF reader uses Qt's private `QZipReader` API, so it must be rebuilt against the selected Qt installation.

The existing FastAPI service remains authoritative at first. Native work proceeds in stages: scene and camera; mesh import and selection; non-destructive transforms; display and inspection; then deterministic geometry operations. Each geometry operation accepts an immutable source revision and explicit parameters, returns a derived revision plus provenance, and avoids writing to the original upload. A thin native C++ command client now handles the first migrated operation while reusing existing backend contracts.

Planar slicing is the first service-backed geometry command. Set `OUTLAW_FORGE_API_URL` to the FastAPI origin when it is not `http://127.0.0.1:8000`. Importing STL or OBJ creates a project source and working model in the service while preserving the locally displayed source. Slice results are persisted as derived working models and downloaded to the native app's local data folder before they replace or join scene entries. The original source is not overwritten. The viewport reports the service's watertight result separately for each half; capped slicing is requested, but an open result is reported as open. If the service is unavailable or a result cannot be downloaded, the source stays in the scene and any persisted result IDs are shown for recovery. 3MF remains viewable, but service-backed slicing currently supports STL and OBJ only. Other geometry operations remain local and have not yet moved behind the service command boundary.

Auto-orient is available from the top toolbar for a selected, registered STL or OBJ. It calls the existing project auto-orient endpoint, then loads the baked result from the model's project-scoped file route into app-local `derived-geometry/`. The API creates a new working-file artifact and operation-history entry while keeping the same working-model ID; the imported source stays untouched. All current scene instances sharing that model ID switch to the returned geometry, while each instance keeps its position, rotation, scale, and visibility. The optimal rotation is already baked into the returned mesh and is not applied again by the viewport. The status area shows the reported rotation and overhang-area reduction, plus the service message; mesh analysis reflects the returned geometry. If the operation persisted but its file download failed, select an instance of that model and use **Retry Orient Download**. That control repeats only the GET request. 3MF and unregistered models cannot use auto-orient. The command does not guarantee watertightness or printability.

Repair uses the existing project repair endpoint for registered STL and OBJ models. It sends hole filling, normal fixing, degenerate-face removal, vertex welding, and the selected tolerance in millimetres (service range 0.00001 to 1.0 mm). The service writes a derived working artifact and operation record while retaining the working-model ID and leaving the original upload unchanged. The native app downloads the result to app-local `derived-repairs/`, parses it before changing the scene, then switches every scene instance sharing that model ID to the new geometry while preserving each instance's transforms, visibility, and selection. The report displays holes filled, degenerate faces removed, vertices welded, normals fixed, triangle counts, and measured watertightness before and after; repair success does not guarantee a watertight or printable result. If the operation persisted but the mesh GET failed, use **Retry Repair Download** on a matching selected instance; this retries only the GET. Unregistered models and 3MF continue to use the existing local repair implementation and tolerance range.

See [Native Viewport and Geometry Migration](../../docs/NATIVE_VIEWPORT_MIGRATION.md) for the staged cutover plan and operation boundary.
