# Native Project Save and Reopen Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Save and reopen the local Qt viewport scene from a self-contained, versioned project folder without changing source files or losing scene state on a failed load.

**Architecture:** A focused C++ `NativeProjectStore` owns manifest validation, content-addressed STL asset writes, SHA-256 checks, and atomic manifest replacement. QML snapshots and restores scene rows, geometry objects, dirty state, dialogs, and selection. `MeshGeometry::copyMeshFrom` lets QML stage and validate all assets before committing the source geometry into its existing QML object; `exportLocalStl` preserves exact local mesh coordinates for stable revision ids.

**Tech Stack:** C++20, Qt 6 Core, Quick, Quick3D, Quick Controls, QML, Qt Test, CMake.

**Spec:** `docs/superpowers/specs/2026-10-23-native-project-persistence-design.md`

## Global Constraints

- Store all mesh coordinates in millimetres and preserve the right-handed Z-up scene.
- Never overwrite imported source files; project mesh snapshots are separate assets.
- Save and open remain local with no API, network, cloud, or printer-service dependency.
- Keep mesh assets immutable and content-addressed; atomically replace the project manifest last.
- Validate every project asset before replacing the current scene; failed loads leave current state intact.
- Save current scene state and needed geometry revisions, not a durable command history.
- Do not add a project archive or another geometry dependency.

## Review Focus

- Missing, malformed, or unsupported project manifests fail with an actionable error and leave the current scene unchanged; pin in `NativeProjectStoreTests::rejectsMalformedSceneField` and QML integration review.
- Absolute paths and `..` traversal in asset references are rejected; pin in `NativeProjectStoreTests::rejectsUnsafeAssetPath`.
- Asset digest or triangle count mismatch is rejected before scene replacement; pin in `NativeProjectStoreTests::rejectsCorruptAssetDigest` and `NativeProjectStoreTests::rejectsTriangleCountMismatch`.
- A mesh export or manifest write failure does not invalidate the prior saved project; pin in `NativeProjectStoreTests::failedSavePreservesPreviousManifest`.
- Duplicate instances sharing one geometry revision reopen with identical independent transforms, visibility, ordering, and selected instance; pin in the scene round-trip integration check.

---

### Task 1: Add safe mesh cloning for staged project loads

**Files:**
- Modify: `apps/native/src/MeshGeometry.h`
- Modify: `apps/native/src/MeshGeometry.cpp`
- Test: `apps/native/tests/MeshGeometrySliceTests.cpp`

**Interfaces:**
- Produces: `Q_INVOKABLE bool MeshGeometry::copyMeshFrom(const MeshGeometry *source)`. It returns false when `source` is null or unloaded; otherwise it copies source triangle points through `setTrianglePoints`, preserving source file name and content revision id.
- Produces: `Q_INVOKABLE QVariantMap MeshGeometry::exportLocalStl(const QUrl &url) const`. It writes raw `m_trianglePoints` to a binary STL without applying instance transforms.

- [x] **Step 1: Write tests for copy and local STL snapshot behavior.**

Add `copyMeshFromCopiesGeometryAndRevision` and `exportLocalStlPreservesRevisionId`. Assert that cloning a loaded mesh preserves triangle count, dimensions, analysis, file name, and revision id; null/unloaded sources return false without mutating the destination. Export and reload a local STL and assert the mesh revision id is unchanged.

- [x] **Step 2: Run the focused test and confirm it fails because `copyMeshFrom` is absent.**

Run: `cmake --build apps/native/build-mingw2 --target native-mesh-slice-tests --parallel 4` then `apps/native/build-mingw2/native-mesh-slice-tests.exe copyMeshFromCopiesGeometryAndRevision exportLocalStlPreservesRevisionId`

- [x] **Step 3: Implement mesh copy and local snapshot export.**

Add both invokable declarations. Implement `copyMeshFrom` with `setTrianglePoints(source->m_trianglePoints, source->m_fileName, QStringLiteral("project mesh"))`. Factor the binary STL writer so `exportLocalStl` writes `m_trianglePoints` directly, without the identity-transform arithmetic in `exportStl`.

- [x] **Step 4: Run the focused test and confirm it passes.**

Expected: clone succeeds with equal revision id and mesh metrics; local STL export/reload keeps the exact revision id; invalid sources do not mutate the destination.

- [x] **Step 5: Commit the mesh staging primitive.**

### Task 2: Implement and test valid project round trips

**Files:**
- Create: `apps/native/src/NativeProjectStore.h`
- Create: `apps/native/src/NativeProjectStore.cpp`
- Create: `apps/native/tests/NativeProjectStoreTests.cpp`
- Modify: `apps/native/CMakeLists.txt`
- Modify: `apps/native/src/main.cpp`

**Interfaces:**
- `Q_INVOKABLE QVariantMap NativeProjectStore::saveProject(const QUrl &folderUrl, const QVariantMap &scene, const QVariantList &geometryRecords) const`
- `Q_INVOKABLE QVariantMap NativeProjectStore::loadProject(const QUrl &folderUrl) const`
- `geometryRecords` entries contain `geometryKey`, `sourceName`, `sourceFormat`, and `geometry` (`MeshGeometry*` as a QObject variant).
- `scene` contains `selectedInstanceId` and ordered `instances`; each instance has `instanceId`, `name`, `sourceUrl`, `piece`, `geometryKey`, `instanceVisible`, and numeric `offsetX/Y/Z`, `rotationX/Y/Z`, `scaleX/Y/Z` fields.
- Success returns `{ "ok": true, ... }`; failures return `{ "ok": false, "error": <actionable string> }`.
- `loadProject` returns a validated `document` and geometry entries with `geometryKey`, `revisionId`, `sourceName`, `sourceFormat`, `triangleCount`, and local `assetUrl`.

- [ ] **Step 1: Define the QML-facing contract and create the red project-store test target.**

Declare the `NativeProjectStore` API in its header, create `NativeProjectStoreTests.cpp`, and register `native-project-store-tests` in CMake with the test file and `MeshGeometry` sources. Do not add store method definitions yet.

- [ ] **Step 2: Write failing tests for a round trip and immutable revision reuse.**

Use a temporary project folder and real `MeshGeometry` STL fixtures. Save two geometry keys with identical mesh content, reload, and assert the ordered scene data survives and both keys refer to one content-addressed asset with the correct format id, schema version 1, units, axis, digest, triangle count, and exact mesh revision id. Also save a valid project, force a later save to fail after staging an asset, and assert the original manifest and assets still load.

- [ ] **Step 3: Run the new focused Qt test and confirm it fails because the project-store methods are undefined.**

Run: `cmake --build apps/native/build-mingw2 --target native-project-store-tests --parallel 4` then `apps/native/build-mingw2/native-project-store-tests.exe`

- [ ] **Step 4: Implement schema-v1 save/load for valid projects.**

Add `NativeProjectStore` as a QML-registered QObject with `saveProject(folderUrl, scene, geometryRecords)` and `loadProject(folderUrl)`. Store `project.json` and `meshes/<sha256>.stl`. Export unique revisions with `MeshGeometry::exportLocalStl`, hash bytes, atomically publish immutable assets, and commit the complete manifest with `QSaveFile` last. The load result contains the parsed document and validated local asset URLs.

- [ ] **Step 5: Add the implementation to the app target and register the QML type.**

- [ ] **Step 6: Run the round-trip test and confirm valid projects save and reopen.**

Expected: manifest metadata, ordered scene rows, geometry maps, exact revision ids, and content-addressed deduplication match the source document.

- [ ] **Step 7: Commit the valid project-store slice.**

### Task 3: Reject invalid projects

**Files:**
- Modify: `apps/native/src/NativeProjectStore.cpp`
- Modify: `apps/native/tests/NativeProjectStoreTests.cpp`

- [ ] **Step 1: Add failing tests for invalid manifests and assets.**

Add tests named `rejectsUnsupportedSchemaVersion`, `rejectsMalformedSceneField`, `rejectsUnknownGeometryReference`, `rejectsUnsafeAssetPath`, `rejectsMissingAsset`, `rejectsCorruptAssetDigest`, `rejectsTriangleCountMismatch`, and `rejectsAssetOverTriangleLimit`. Verify each failure returns an actionable error.

- [ ] **Step 2: Run the new validation tests and confirm each fails for its expected reason.**

Run: `cmake --build apps/native/build-mingw2 --target native-project-store-tests --parallel 4` then `apps/native/build-mingw2/native-project-store-tests.exe`

- [ ] **Step 3: Enforce schema, size, path, reference, hash, and triangle-count validation.**

Enforce a 16 MiB manifest limit, a 20,000,000-triangle per-mesh limit matching `MeshGeometry::loadStl`, and a 4 GiB total unique-asset limit before large allocation. Require finite transform values, unique instance and geometry keys, an existing selected instance when non-empty, valid geometry references, and safe relative asset paths rooted under `meshes/`. Check the binary STL byte length and declared count before hashing/loading; stream SHA-256 calculation so the asset does not need to be duplicated in memory. Return actionable errors without mutating an existing project.

- [ ] **Step 4: Commit after all project-store tests pass.**

### Task 4: Connect save/open to the native scene

**Files:**
- Modify: `apps/native/qml/Main.qml`
- Modify: `apps/native/src/main.cpp` only if QML type registration needs adjustment beyond Task 2.

**Interfaces:**
- Add `projectStore`, `projectDirectory`, and `projectDirty` QML state.
- Add `window.projectSceneDocument()`, `window.projectGeometryRecords()`, `window.saveNativeProject(folderUrl)`, `window.stageNativeProject(folderUrl)`, and `window.commitNativeProject(stagedProject)`.
- `stageNativeProject` constructs temporary `MeshGeometry` objects, loads every returned `assetUrl`, and verifies exact revision id and triangle count; it returns `{ ok, error, document, geometriesByKey }` and does not mutate the active scene.
- `commitNativeProject` copies the validated `source` geometry into `importedGeometry`, replaces derived geometry references and ordered `sceneInstances`, restores selected instance id, and clears dirty state only after commit.

- [ ] **Step 1: Implement QML scene snapshot construction.**

Serialize every scene row and unique geometry key. Include `importedGeometry` as the source geometry record even when active instances point to derived geometry; include each derived geometry still referenced by a scene row. Preserve source path as provenance only.

- [ ] **Step 2: Implement staged load and commit.**

Load all candidate geometries before mutating the live scene. Validate every instance reference against the candidate geometry map. On success, clone the source asset into the fixed `importedGeometry` object, install candidate derived objects, replace scene rows in order, restore selection by id, update next ids, and destroy superseded derived objects. On any staging or validation error, destroy candidates and retain the current scene exactly. Exact revision id comparison depends on `exportLocalStl` from Task 1.

- [ ] **Step 3: Add Save, Save As, and Open Project menu/dialog flows.**

Save As selects a parent directory, collects a project name, creates `<name>.oforge`, and saves there. Save targets `projectDirectory`, or routes to Save As if unset. Open selects the project folder and calls stage then commit. Add Ctrl+S for Save, Ctrl+Shift+S for Save As, and Ctrl+Shift+O for Open Project to avoid the existing Ctrl+O mesh-import shortcut. Set `projectDirectory` and clear `projectDirty` only after successful save or load.

- [ ] **Step 4: Add QML round-trip coverage where an established test harness permits it; otherwise record a deterministic manual scenario in the QA checklist.**

The scenario must include two instances sharing a geometry revision, different signed transforms, one hidden instance, a selected derived revision, source-path removal after save, and reopen comparison of order, selection, transforms, visibility, and mesh revision ids.

- [ ] **Step 5: Commit save/open integration.**

### Task 5: Protect unsaved scene work and update native documentation

**Files:**
- Modify: `apps/native/qml/Main.qml`
- Modify: `apps/native/README.md`
- Modify: `docs/NATIVE_VIEWPORT_MIGRATION.md`
- Modify: `docs/QA_ACCEPTANCE.md`

**Interfaces:**
- `window.markProjectDirty()` marks only persisted scene changes.
- A single pending action state handles Open Project, scene-replacing mesh import, and window close with Save, Discard, and Cancel choices.

- [ ] **Step 1: Identify every persisted-scene mutation in QML.**

Cover import, geometry commands, duplicate, remove, clear, visibility changes, and transform handlers. Do not mark selection, camera, measurement, or viewport display changes dirty.

- [ ] **Step 2: Write the dirty-state transitions before implementation.**

Manually verify a clean scene closes or opens without a prompt; a dirty scene prompts; Save proceeds only after a successful project save; Discard proceeds; Cancel preserves the current window/scene; failed Save keeps the prompt and dirty state.

- [ ] **Step 3: Implement the shared pending-action prompt.**

Route Open Project, an import that replaces current scene content, and window close through Save/Discard/Cancel. The import guard prevents the existing import behavior from replacing dirty source geometry without notice. Cancel clears the pending action and performs no scene replacement. A failed save retains the pending action and current scene.

- [ ] **Step 4: Update native docs and acceptance checks.**

Document project folder contents, Save/Open behavior, current-state scope, schema versioning, content-addressed assets, local-only boundary, and current exclusions (camera/display state and durable history). Add the persistence round-trip and corrupt-project scenarios to `docs/QA_ACCEPTANCE.md`.

- [ ] **Step 5: Commit dirty-state protection and docs.**

### Task 6: Verify the native persistence phase

**Files:**
- Verification only: native CMake build and tests, Windows Qt application.

- [ ] **Step 1: Run focused project-store and mesh tests.**

Run: `cmake --build apps/native/build-mingw2 --target native-project-store-tests native-mesh-slice-tests native-slice-plane-tests outlaw-forge-native --parallel 4`
Run: `ctest --test-dir apps/native/build-mingw2 --output-on-failure`
Expected: all native test targets pass and the application builds.

- [ ] **Step 2: Exercise the Windows app with a representative local project.**

Save a scene containing an imported model and a derived mesh, close and reopen the folder, compare scene and transform state, rename or move the original imported file and reopen again, then corrupt a copied test asset and verify load fails without replacing the current scene.

- [ ] **Step 3: Run `git diff --check` and inspect the final diff for accidental API/service coupling or source-file mutation.**

- [ ] **Step 4: Commit only after focused tests, full native tests, build, and the manual workflow pass; report any unavailable verification plainly.**
