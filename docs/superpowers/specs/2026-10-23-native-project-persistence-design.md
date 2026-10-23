# Native project save and reopen

## Intent

Let users preserve and resume work in the experimental local-only Qt viewport. The app currently imports a source mesh and keeps scene instances and derived geometry revisions in memory; closing the app loses that scene. Project persistence gives the existing local geometry workflow a durable handoff between sessions and prepares a stable base for the later bed-aware arrangement phase.

## Goals

- Save and reopen the current native scene from a self-contained project folder.
- Preserve every active scene instance, its name and source provenance, geometry revision, visibility, translation, rotation, and signed scale, plus which instance is selected.
- Store a mesh asset for every geometry revision referenced by the scene and preserve the original imported geometry snapshot when it is still available.
- Keep all mesh coordinates in millimetres and the scene Z-up.
- Keep imported source files untouched and make project files usable without the original source path being available.
- Validate a project completely before replacing the open scene; report actionable errors for unsupported versions, invalid metadata, missing assets, or damaged meshes.
- Keep Save and Open entirely local with no API, network, cloud, or printer-service dependency.

## Non-goals

- Bed-aware arrangement, printer profiles, or printer-bed settings; arrangement follows as a separate phase.
- Durable undo/redo or a full command history. This format stores the current scene and the geometry revisions needed to render it, not every intermediate edit.
- Camera position, viewport display toggles, measurement points, or transient dialog state.
- Replacing the STL export workflow or changing source mesh formats and import behavior.
- Migration of project files into the Tauri workbench.

## Approaches

1. **Self-contained project folder (selected):** a versioned `project.json` manifest and immutable binary STL snapshots in a `meshes/` subfolder. This needs no archive dependency, is inspectable and recoverable, and supports atomic manifest replacement. Users can move or back up one folder.
2. **Single `.oforge` archive:** the same manifest and mesh assets in a ZIP-style package. It is easier to move as one file but adds archive writing, extraction, and corruption-handling complexity to the first persistence milestone.
3. **Manifest with external source references:** stores scene state and points to original files. This is small but breaks when a source is moved and cannot reliably retain locally-derived geometry, so it does not meet the self-contained goal.

## User workflow

- Add **Open Project**, **Save Project**, and **Save Project As** to the File menu, with native keyboard shortcuts where they do not conflict with existing commands.
- Save As selects an existing parent directory and a project name, then creates a new `<name>.oforge/` folder containing `project.json` and `meshes/`.
- Save updates the current project folder. If no project is open, Save behaves like Save As.
- Open selects a `.oforge` project folder and validates it before changing the current scene.
- Track unsaved scene changes. Opening another project, importing a new mesh that replaces the current scene, or closing the window prompts to Save, Discard, or Cancel; Cancel leaves the current project and window intact.
- Report success only after mesh assets and the manifest are committed. Report the failing path and reason on failure.

## Project format, version 1

```text
Example.oforge/
  project.json
  meshes/
    <sha256-of-canonical-stl>.stl
```

`project.json` contains a format identifier, integer schema version, units (`mm`), axis convention (`Z-up`), selected instance id, geometry records, and ordered scene-instance records. A geometry record contains its revision id, safe relative asset path, SHA-256 digest, triangle count, and source-format/name provenance where known. A scene-instance record contains its stable id, display name, source path as informational provenance, geometry revision id, piece kind, visibility, and translation/rotation/scale vectors. Mesh assets are canonical binary STL snapshots written with identity instance transforms, so reopening geometry and instance transforms separately reproduces the same scene.

Geometry assets are immutable and content-addressed. Saving writes any missing assets first, verifies their digests, and atomically replaces `project.json` last. A crash before the manifest commit may leave unused assets but cannot make the previous manifest point to partially-written geometry. Repeated save with unchanged geometry reuses its asset. The original imported mesh snapshot is retained even if the visible scene has moved to derived geometry; only derived geometry revisions still referenced by the active scene are required in v1.

Loading accepts only the known format and schema version, validates all fields and safe relative asset paths, checks each asset digest and triangle count, and loads all assets into temporary geometry objects. Only after every referenced mesh loads successfully does the UI replace the scene. Unknown future schema versions fail with a clear message instead of being partially loaded. The loader never follows absolute paths or parent-directory segments from the manifest.

## Architecture and constraints

- Keep file serialization and validation in a focused native C++ project-store seam; keep scene selection, dialogs, and dirty-state prompts in QML.
- Use Qt Core JSON, filesystem, hashing, and atomic-file primitives already available to the native target. Do not add a service or network client.
- Reuse `MeshGeometry` local mesh loading and identity-transform binary STL export for mesh snapshots; do not bake scene transforms into project geometry assets.
- Do not mutate or overwrite imported source files. The project stores its own geometry snapshot and records the original path only as provenance.
- Build the complete replacement scene off to the side; if any asset is missing or invalid, retain the current scene unchanged.
- Preserve instance order and identifiers so selection and duplicate relationships remain stable across a save/reopen cycle.
- Keep the first version focused on current scene state; future versions can add bed settings and arrangement metadata with explicit schema migration.

## Acceptance

- Save a scene containing an imported source, transformed and hidden instances, duplicates, and locally-derived cut/split/simplified geometry; reopen it and compare geometry revision references, instance order, names, visibility, selection, and all transforms.
- Move the source file after saving and confirm the project still opens from its embedded snapshots.
- Save a changed revision twice and interrupt a save before manifest replacement; the prior manifest remains loadable and references intact assets.
- Reject a missing asset, mismatched digest, malformed field, path traversal attempt, unsupported schema version, and unreadable mesh while leaving the current scene unchanged.
- Verify imported source file timestamps and hashes are unchanged by Save and Save As.
- Verify cancelling an import while the project is dirty leaves the current scene intact.
- Run focused project-store tests, existing native geometry tests, build the Qt executable, and exercise Open/Save/Save As and unsaved-change prompts in the Windows app.

## Left to the builder

- Choose exact C++ class and method names after checking existing registration and test seams.
- Choose bounded project and per-mesh size limits appropriate to the native app's currently-supported mesh limits; enforce them before allocating large buffers.
- Choose the prompt presentation that fits existing native dialogs while preserving Save, Discard, and Cancel semantics.
