# Native viewport view cube

## Intent

Improve camera orientation and control in the experimental Qt viewport. Make the Z-up XYZ axes easy to read and give users a direct on-screen way to snap and frame the camera, with the view cube styled like an ornate mechanical puzzle box.

## Goals

- Replace the current six-button axis triad with a compact view cube that shows the camera-relative X, Y, and Z directions.
- Let users click a face to snap to a standard view and click a corner or edge to snap to a useful angled view.
- Provide compact Fit and zoom controls beside the cube.
- Give the cube dark aged-metal faces, engraved geometric linework, and restrained bronze highlights while preserving clear orientation labels and hit targets.
- Reuse the existing camera rig, snapping, and framing logic so mesh placement and millimetre coordinates do not change.
- Keep the Top, Front, Right, Iso, and Frame toolbar actions and their shortcuts available.

## Non-goals and anti-goals

- Do not change mesh transforms, geometry, camera projection, or the Z-up scene convention.
- Do not add a new camera library or a second source of camera state.
- Do not add persistent preferences or animate camera motion with long transitions.

## Constraints

- Implement in `apps/native/qml/Main.qml` using the existing Qt Quick 3D camera rig and compact dark workbench styling.
- Preserve direct model manipulation, camera orbit and tilt, pan, and wheel zoom.
- Axis directions must stay aligned with the actual camera orientation, including after free orbit and snapping.
- Clicking a cube face, edge, or corner uses deterministic camera snapping and frames the selected mesh when one is loaded.
- Every snapped view keeps world +Z upright on screen. For top and bottom views, where +Z is parallel to the camera direction, use world +Y as the screen-up fallback.
- Clicks outside the projected cube silhouette do not change the camera.
- Provide explicit Orbit and Pan camera modes. Empty-space left-drag navigates the camera; Orbit uses horizontal drag to orbit around the scene and vertical drag to tilt while keeping Z up. Pan moves in screen directions. Dragging a model manipulates it and exits camera mode; Shift-left-drag navigates over a model. Keep middle-drag panning and wheel zoom available.

## Approaches

1. Refine the existing six endpoint buttons with clearer spacing and labels. This is the smallest change, but does not add direct orbit control on the widget.
2. Replace the endpoint buttons with an orbit compass: camera-relative XYZ indicators, drag-to-orbit, signed-axis click-to-snap, and compact zoom controls. This combines orientation feedback with direct camera control while reusing the current rig.
3. Use a view cube with clickable faces, edges, and corners plus compact Fit and zoom controls. **Selected.** This makes standard and angled views explicit and provides familiar one-click camera controls.

## Design decisions

- The user selected the view cube after comparing visual previews and requested an ornate dark fantasy puzzle-box appearance.
- Keep existing toolbar presets as a second access path and preserve their keyboard shortcuts.
- Use existing camera view and framing logic; Fit frames the selected mesh, and zoom buttons match the wheel zoom step.
- Keep the cube compact and anchored at the lower-right of the viewport, away from the transform inspector and status panel.
- Treat the requested Hellraiser box as visual direction for a fictional puzzle box: use an original geometric engraving pattern and avoid reproducing film-specific marks or exact prop details.

## Left to the builder

- Choose precise dimensions and hit targets; keep the dark metallic ornament readable at compact size and consistent with the current viewport.
- Map face, edge, and corner clicks to deterministic orientations using the existing camera rig and preserve the Z-up convention.
- Ensure Fit is disabled without a loaded mesh and zoom remains usable with or without one.
- Build the native Qt target and verify the app launches with the widget visible.
