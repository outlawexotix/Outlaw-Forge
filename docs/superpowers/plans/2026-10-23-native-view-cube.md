# Ornate Native View Cube Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the native viewport's six-button axis triad with an ornate, interactive view cube that shows XYZ orientation and controls camera snapping, framing, and zoom.

**Architecture:** Keep the change inside the existing `orientationGizmo` in `apps/native/qml/Main.qml`. Reuse `cameraRig`, `setCameraView`, and the existing camera distance limits; add a signed-direction mapping for cube face, edge, and corner actions.

**Tech Stack:** Qt 6.10, Qt Quick Controls, Qt Quick 3D, QML.

**Spec:** `docs/superpowers/specs/2026-10-23-native-viewport-view-cube-design.md`

## Global Constraints

- All mesh dimensions and coordinates remain in millimetres.
- The scene remains right-handed and Z-up.
- Every snapped camera direction keeps projected world +Z aligned with screen-up; top and bottom views use world +Y as the fallback.
- Preserve direct model manipulation, camera orbit and tilt, pan, and wheel zoom. In Orbit/Pan mode, empty-space drag navigates; model drag manipulates the model and exits camera mode. Hold Shift to navigate over a model.
- Do not change mesh transforms, geometry, camera projection, or add a camera dependency.
- Use original geometric engravings and do not reproduce film-specific marks or exact prop details.
- Keep user-visible text free of em dashes and en dashes.

## Review Focus

- Six cardinal cube faces select the intended signed world axis; verify each click and confirm the existing Top, Front, Right, and shortcut actions still work.
- Edge and corner regions produce distinct useful angled views; click each region and verify camera orientation changes as indicated.
- Clicks outside the projected cube silhouette do not snap the camera.
- Camera-relative face labels remain correct after free orbit and after snapping; orbit, snap, and compare the displayed axis labels.
- Fit is disabled without a mesh, while zoom remains available; verify in an empty scene and with a selected mesh.
- Orbit and tilt with empty-space drag, pan in screen directions, model manipulation while Orbit/Pan is active, Shift-drag camera navigation over a model, and middle-drag pan.
- The cube and its controls remain inside the viewport at the minimum 1100 x 720 window size and do not cover the transform panel or status area; resize and inspect.

---

### Task 1: Replace the axis triad with the ornate interactive view cube

**Files:**
- Modify: `apps/native/qml/Main.qml` at the `orientationGizmo` overlay and camera-view helper functions.

**Interfaces:**
- Reuse `setCameraView(viewName)` for standard presets.
- Route standard presets, axis snaps, and cube snaps through `setCameraDirectionZUp(x, y, z)`. Build a right-handed camera basis from the requested view direction, projected world +Z screen-up, and world +Y fallback for views parallel to Z; convert the basis to a quaternion.
- Add `setCameraCubeDirection(xSign, ySign, zSign)` in `Main.qml`, with each sign in `{-1, 0, 1}` and at least one nonzero. Frame the selected model after changing orientation.
- Reuse `frameImportedModel()` for Fit and the existing wheel-zoom bounds and step (`0.88` in, `1.14` out) for zoom buttons.
- Add explicit Orbit and Pan camera drag modes. Left-drag empty viewport space in Orbit rotates around the scene horizontally and tilts vertically; left-drag in Pan translates in screen directions. Dragging a model keeps model manipulation available and exits camera mode; Shift-left-drag navigates over a model. Middle-drag continues to pan.

- [x] **Step 1: Build the camera-relative cube overlay**

Replace the six endpoint buttons in `orientationGizmo` with a compact lower-right puzzle-box cube. Use Qt Quick Shapes or existing QML primitives only. Give its visible faces dark aged-metal surfaces, original geometric engraved lines, bronze edges, and readable face/axis labels. Recompute the cube face order and signed axis labels from `cameraRig.mapDirectionFromScene(...)` so the visible faces communicate the live Z-up scene orientation.

- [x] **Step 2: Add deterministic cube camera actions**

Implement `setCameraCubeDirection(xSign, ySign, zSign)` using the exact mapping in Interfaces. Map each face to its signed axis and each edge or corner to its corresponding two-axis or three-axis sign combination. For an imported mesh, frame after a snap; without a mesh, keep the target and current camera distance unchanged.

- [x] **Step 3: Add Fit and zoom controls**

Place compact Fit, zoom-in, and zoom-out buttons beside the cube. Disable Fit when no mesh is loaded. Apply the same camera distance bounds and increments as the viewport wheel handler for zoom.

- [x] **Step 4: Build the native application**

Run from the repository root with Qt and MinGW on `PATH`:

```powershell
$env:PATH='D:\Qt\6.10.3\mingw_64\bin;D:\Qt\Tools\mingw1310_64\bin;' + $env:PATH
cmake --build apps/native/build-menu-mingw --target outlaw-forge-native
```

Expected: the target builds successfully and deploys its Qt runtime dependencies.

- [ ] **Step 5: Verify the running viewport**

Launch `apps/native/build-menu-mingw/outlaw-forge-native.exe`. Manually check the Review Focus cases, including Z-up on standard and angled snaps, Orbit and Pan drag modes, and ignored clicks outside the cube; confirm the native window stays responsive after repeated face, edge, corner, Fit, zoom, orbit, and pan actions.

**Task acceptance:** the view cube is legible and puzzle-box styled, accurately shows camera-relative axis orientation, and its controls change the camera without changing mesh state.
