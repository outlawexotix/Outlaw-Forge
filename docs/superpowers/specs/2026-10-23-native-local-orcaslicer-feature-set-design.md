# Local Qt OrcaSlicer-Inspired Mesh Preparation

## Status

Approved for implementation. Target branch: `codex/native-file-edit-view`.

## Intent

Extend the experimental Qt application as an offline mesh-preparation workbench. Use OrcaSlicer as a feature reference while keeping geometry operations in the native process and independent from FastAPI, HTTP, cloud services, or printer connectivity.

## Current boundary

The selected worktree contains local STL/OBJ/limited 3MF loading, scene transforms, measurement, local repair, local auto-orient, and local plane cutting. Geometry is held in memory. Project save/reopen and mesh export are not implemented. This branch also contains pre-existing unrelated edits under `apps/api/`; preserve them.

## Goals

- Fix cut-and-separate closure reporting and produce capped output when the cut contour is supported.
- Split disconnected mesh components into separately selectable scene items.
- Provide local mesh union, difference, and intersection.
- Simplify a mesh with a user-controlled reduction target and a reviewable derived result.
- Arrange selected or all scene items within a configurable rectangular build plate, with a requested spacing and optional quarter-turn rotations.
- Save and reopen a local project that preserves mesh geometry and per-instance transforms, visibility, and selection identity.
- Export derived geometry to STL without modifying imported source files.
- Keep all operations deterministic, measured in millimetres, and local to the Qt application.

## Non-goals

- G-code generation, slicing profiles, infill/wall/speed/support controls, calibration workflows, printer connection, or cloud features.
- Reproducing OrcaSlicer's painting, variable-layer-height, or parametric design tools in this phase.
- Changing the Tauri workbench or FastAPI service.
- Claiming every invalid input can be repaired into a watertight printable solid.

## Approaches considered

1. **Native local geometry operations (recommended):** retain the existing `MeshGeometry` boundary and add operations as local deterministic functions. This matches the user's local-only direction and keeps the Qt app focused on mesh preparation.
2. **Invoke OrcaSlicer as a local slicing process:** could add slicing and G-code features, but changes packaging and licensing obligations and expands the application into a full slicer.
3. **Add Orca-style controls without matching geometry operations:** rejected because the controls would not produce trustworthy results.

## Implementation sequence

1. Lock down plane-cut outputs and closure reporting, then add a local STL export path so results can be retained. The STL export path is implemented with transform baking; real-model closure still requires in-app reproduction of the reported cut.
2. Add disconnected-component splitting and deterministic mesh simplification.
3. Add mesh booleans after confirming a suitable offline geometry kernel meets Windows build, deterministic-output, and license constraints.
4. Add bed-aware 2D arrangement with configurable bed dimensions and spacing.
5. Add versioned local project save/reopen that preserves the scene and derived geometry.

Each step is a separate reviewable slice. Keep imported geometry immutable; write each successful operation into a derived geometry object. If an operation cannot establish valid topology, preserve the current scene and report the measured boundary/non-manifold state.

## Acceptance criteria

- The Qt target has no HTTP client or service-startup requirement.
- Each operation works from imported local files with networking unavailable.
- Failed, cancelled, or unsupported operations leave the current scene and source files unchanged.
- Cut output reports topology metrics for each side; it never labels an open result closed.
- Split, boolean, simplify, and arrange results remain selectable and keep correct millimetre dimensions.
- Saved projects reopen with the same geometry and instance transforms; STL exports can be re-imported with matching dimensions and triangle geometry within the format's numeric precision.
- Existing Tauri/API behavior remains outside this change.

## Open implementation constraint

The current native code stores triangle soup. Boolean robustness and project container format need a short feasibility check before their implementation slice; this design does not pre-approve a new third-party dependency or a format that loses scene data.
