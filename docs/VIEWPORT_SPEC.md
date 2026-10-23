# Outlaw Forge viewport status and design

This document describes the implemented web viewport and separates current behavior from remaining CAD-parity work. It is a product reference, not a claim that Outlaw Forge is a slicer engine.

## Current viewport behavior

The main web workbench uses React Three Fiber and Three.js. It provides:

- STL, OBJ, GLTF, GLB, and 3MF mesh parsing through `packages/three-tools/src/loaders/geometryLoader.ts`.
- A millimetre build plate, printer-volume display, grid, camera orbit/pan/zoom, perspective and orthographic projection, and named views.
- Modifier-based multi-selection, select-all, escape-to-collapse-selection, model deletion, visibility and display color controls.
- Move, rotate, scale, lay-on-face, orientation, and arrangement workflows backed by project/model operations.
- Smooth camera transitions and framing based on transformed model bounds.
- Per-project browser persistence for camera and model appearance state.
- Solid, wireframe, overhang, cross-section, and layer-line display modes, plus bounds and dimension inspection.

The main web workbench stores model and print coordinates in millimetres with Z-up print semantics. The Three.js viewport uses a Y-up render frame and converts at its scene boundary. Camera controls and visual presentation do not change source mesh coordinates.

The **separate Qt native viewport** is documented in [Native viewport migration](./NATIVE_VIEWPORT_MIGRATION.md). It uses a right-handed Z-up scene and is not packaged into Tauri. Do not conflate its service-backed STL/OBJ slice command with the web viewport's existing API workflow.

## Implemented viewport foundations

| Area | Current behavior | Known boundary |
| --- | --- | --- |
| Model lifecycle | Load supported mesh formats, select one or more project models, hide/show, color, delete, and display transforms | No grouped assembly/part tree or user-facing undo/redo history in the viewport |
| Navigation | Orbit, pan, zoom, perspective/orthographic modes, eased framing, preset views, and orientation gizmo | More keyboard/accessibility and camera edge-case coverage remains |
| Build plate | Printer dimensions, grid spacing controls, build volume presentation, and origin display | Advanced printer keep-out geometry and non-rectangular bed presentation remain limited |
| Mesh display | Solid, wireframe, overhang, cross-section, layer-line, bounds, and dimensions | High-density model performance budgets and richer topology diagnostics need further work |
| Selection and transforms | Modifier multi-select, select-all, delete, transform actions, lay-on-face, and context actions | Group transforms, snapping, and complete undo/redo remain future work |
| Project state | Camera and model appearance persist by project in browser storage | This does not replace project/server persistence for model operations |
| Import and export | STL/OBJ/GLTF/GLB/3MF parsing; STL export and OrcaSlicer-oriented 3MF project export through workbench workflows | 3MF import is flattened to merged geometry; complete material, hierarchy, and project-metadata preservation is not promised |

## Coordinate and precision rules

- Print dimensions and geometry service coordinates are in millimetres.
- Print-space calculations use a right-handed Z-up frame.
- The web renderer applies a deterministic scene-root conversion to its Y-up Three.js frame.
- Model transforms are applied in the scene and sent through explicit API parameters when a geometry operation is committed.
- Source mesh bytes remain immutable; operations return or persist derived project revisions.
- Mesh health, watertightness, build fit, and cost are computed by application code and the geometry service, not by visual approximation or AI inference.

## Web viewport runtime

Versions are declared in `apps/web/package.json` and change as dependencies are upgraded.

| Layer | Current dependency |
| --- | --- |
| Framework | Next.js 16 and React 19 |
| 3D renderer | Three.js 0.160 and React Three Fiber 9 |
| Viewport helpers | `@react-three/drei` 10 |
| Mesh parsers | `three-stdlib` loaders through `packages/three-tools` |

Mesh parsing currently runs in the web workbench runtime. The prior design concept of automatic worker parsing, triangle-count warnings, and LOD proposals should be treated as future work unless implemented and verified in code.

## Remaining parity work

1. Browser-level interaction acceptance for selection, transforms, camera persistence, and display state.
2. Stable scene resource ownership for large projects and loading progress for expensive assets.
3. Precise numeric transform controls, snapping, and undo/redo.
4. Broader topology, normals, and clipping workflows.
5. Measured performance and context-loss behavior for large meshes.
6. Printer-profile-aware exclusions and advanced build volumes.

Each parity improvement should be delivered and verified as a focused vertical slice. The separate Qt application follows its own progression in [the native migration document](./NATIVE_VIEWPORT_MIGRATION.md).
