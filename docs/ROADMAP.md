# Outlaw Forge roadmap

This roadmap distinguishes the implemented main workbench from the separate native viewport foundation and from capabilities that remain future work. A feature is considered implemented only in the application and workflow named below.

## Main workbench baseline

- Tauri 2 desktop shell hosting the static Next.js and Three.js workbench.
- FastAPI sidecar with dynamic loopback port allocation and supervised shutdown.
- SQLite projects, printer profiles, source files, derived working models, and operation history.
- Mesh import, inspection, printer-fit and print-readiness analysis, deterministic repair and transform operations, planar slicing, and export workflows.
- Viewport model selection, multi-selection, transform and display controls, camera presets, persisted camera and appearance state, and build-plate interaction.
- OrcaSlicer-oriented 3MF packaging plus MaskSmith and FigureForge workflows.
- Desktop development, packaging preflight, sidecar lifecycle, and acceptance automation.

See the [main README](../README.md) and [QA guide](./QA_ACCEPTANCE.md) for current commands and verification layers.

## Native viewport foundation

The Qt Quick 3D application in `apps/native/` is a separate experimental executable. It currently provides a Z-up millimetre scene; STL/OBJ and limited 3MF viewing; scene selection, transforms, display and inspection controls; local mesh analysis and repair; and service-backed planar slicing for STL and OBJ. The slice command uses the existing FastAPI project/import/slice/file routes and reports watertightness for each returned half.

This executable is not yet included in the Tauri package. Its current operation boundary, API dependency, format limits, and remaining migration work are listed in [Native viewport migration](./NATIVE_VIEWPORT_MIGRATION.md).

## Current engineering priorities

1. Maintain the React 19, Next.js, and React Three Fiber dependency line with clean production builds and dependency audits.
2. Add browser-level interaction coverage for multi-selection, camera persistence, display state, and print-readiness workflows.
3. Exercise the native slice command against a running local API with representative STL and OBJ assets, including open/non-manifold results and transformed instances.
4. Define project and revision persistence for the Qt app before adding native project save/reopen flows.
5. Continue native command migration one operation at a time, preserving API contracts and source immutability.
6. Produce repeatable signed Windows installer artifacts and validate first launch and file associations on a clean machine.

## Deferred capabilities

- Integrating the Qt viewport into the Tauri application or making it the default desktop renderer.
- Native persistence and project reopening for the Qt application.
- Direct G-code generation, toolpath editing, and slicer-engine integration.
- Automatic support generation and toolpath optimization.
- Signed automatic update distribution and a public installer release process.
- Multi-user hosting, authentication, and remote project collaboration.
- AI-driven geometry changes. Any future AI feature must remain advisory and require explicit user action before deterministic operations run.

These items are proposals until implementation, contracts, and relevant verification land together.
