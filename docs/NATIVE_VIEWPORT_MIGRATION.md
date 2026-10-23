# Native Viewport

## Scope

`apps/native/` is a separate Qt Quick 3D application for local mesh preparation. It performs mesh loading, analysis, repair, auto-orientation, planar cuts, connected-component splitting, deterministic vertex-clustering simplification, and STL export inside the native process. It does not start, call, or require the FastAPI service. Imported file paths are read-only inputs; geometry commands create in-memory mesh objects, and STL export writes a separate derived file. Project save/reopen and durable operation history remain future work.

The Tauri workbench remains the main integrated desktop workflow and continues to use its existing FastAPI geometry sidecar. This document describes the independent Qt target only.

## Implemented workflow

The Qt viewport provides a Z-up millimetre build plate; STL, OBJ, and limited 3MF import; scene selection; per-instance transforms; placement; camera presets and navigation; bounds, wireframe, sampled normals, measurement, and mesh-health inspection.

Geometry commands operate on the selected in-memory `MeshGeometry`:

1. **Repair** welds vertices by the selected tolerance, removes degenerate triangles, and fills closed planar boundary loops. Open, branched, non-planar, or otherwise unsupported boundaries are not guessed at. The UI reports before/after topology so a repair is never described as watertight unless analysis confirms it.
2. **Auto-orient** deterministically scores a bounded set of candidate orientations from the largest mesh-face normals and the cardinal directions. It bakes the winning orientation and translates the mesh to center XY and set minimum Z to zero.
3. **Planar cut** maps the world-space cut plane into mesh coordinates, clips one or both sides, and triangulates closed cut contours. Separate mode creates two independent scene entries. The result reports whether the cut contour was capped and whether each output remains watertight after accounting for defects already present in the source mesh.
4. **Split components** groups triangles by shared undirected edges and creates separate selectable in-memory geometry for each group. Vertex-only contact does not merge components; output order is stable and placement is preserved under existing transforms.
5. **Simplify** uses deterministic vertex clustering with a bounded candidate search to create a derived mesh for inputs up to 1,000,000 triangles. It reports requested and actual reduction; it does not promise feature preservation or an exact triangle target.

Source files remain unchanged on disk. The current UI keeps derived results in memory and can export the selected geometry as binary STL with instance transforms baked in. It does not write persistent working revisions or maintain durable operation history. This experimental target has no FastAPI, HTTP, cloud, or printer-service dependency. The separate Tauri workbench continues to use its existing FastAPI geometry sidecar.

## Native build and checks

The target requires Qt 6.6+, CMake 3.21+, and a C++20 compiler. Build from the repository root:

```powershell
cmake -S apps/native -B build/native -DCMAKE_PREFIX_PATH="C:/Qt/6.8.0/msvc2022_64"
cmake --build build/native --config Release
ctest --test-dir build/native --output-on-failure
```

Geometry, cut-plane mapping, and UI lifecycle checks should be extended with each local workflow change. Test the actual Windows executable after rebuilding because Qt deployment modules are platform-specific.

## Current limits

- The 3MF reader supports a direct mesh object for the first build item. It does not import component graphs, additional build items, materials, textures, vertex colors, or slicer project metadata. It uses Qt's private `QZipReader` API.
- Repair fills simple planar boundary loops only. It does not invent geometry for non-planar holes or resolve arbitrary non-manifold intersections.
- Auto-orient uses a deterministic local heuristic; it is not a guarantee of minimal supports or printability.
- Cut caps are generated only for valid closed contours. Pre-existing open source surfaces can leave the resulting sections open; the mesh analysis reports those boundaries.
- Scene state and all derived geometry are in memory. Versioned project save/reopen and durable operation provenance remain future work; binary STL export is implemented.
- The Qt application is not packaged into the Tauri app. Tauri keeps its API-backed sidecar architecture.
