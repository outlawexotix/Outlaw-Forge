# Native Service-Backed Slice Command Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Route native planar slicing through the existing API and show its persisted result meshes in the native scene.

**Architecture:** Add a tested plane-coordinate mapper and an asynchronous Qt Network client. The client creates one project for the native session, uploads supported STL/OBJ sources, calls the project slice route, and downloads both working meshes to app-local derived storage. QML keeps plane interaction and scene state, invoking the client and displaying returned geometry only after the complete request succeeds.

**Tech Stack:** C++20, Qt 6.6 Core/Quick/Quick3D/Network/Test, Qt Quick QML, existing FastAPI and Pydantic contracts.

**Spec:** `docs/superpowers/specs/2026-10-23-native-service-backed-slice-design.md`

## Global Constraints

- All dimensional data, bounding boxes, printer volumes, and mesh coordinates are in millimetres (`mm`).
- Never overwrite raw uploads (`data/uploads/`). Derived meshes are written to distinct working or export storage revisions.
- Mesh repairs, transformations, cutting planes, and slicing must remain 100% deterministic.
- Pydantic schemas in `apps/api` and TypeScript contracts in `packages/shared/` must remain in lockstep.
- Keep the native scene right-handed, Z-up, and measured in millimetres.
- Preserve all existing workspace changes and do not reset or clean the worktree.

## Review Focus

- Non-invertible instance transforms (zero scale): reject before sending a request and preserve the source scene entry.
- Non-uniform scale, rotation, translation, and reflection: map plane origin and normal so the displayed world plane and keep-side choice remain correct.
- API project creation or STL/OBJ upload failure: keep the imported source visible, disable service slicing for it, and show an actionable message.
- Slice response success followed by one failed mesh download: keep the source visible and report persisted model IDs for recovery.
- 3MF import: preserve native viewing and show that service-backed slicing is unavailable for that format without silently invoking local slicing.

---

### Task 1: Plane mapping math

**Files:**
- Create: `apps/native/src/SlicePlaneMapper.h`
- Create: `apps/native/src/SlicePlaneMapper.cpp`
- Create: `apps/native/tests/SlicePlaneMapperTests.cpp`
- Modify: `apps/native/CMakeLists.txt`

**Interfaces:**
- `SlicePlaneMapper::mapWorldPlaneToLocal(const QMatrix4x4 &localToWorld, const QVector3D &worldOrigin, const QVector3D &worldNormal, QVector3D *localOrigin, QVector3D *localNormal, QString *error) -> bool`
- Reject singular matrices and zero-length normals; normalize the returned local normal.

- [x] **Step 1: Write failing tests** for identity mapping; translation plus rotation; non-uniform scale; reflection preserving signed plane side; singular transform and zero normal rejection.
- [x] **Step 2: Run the mapper tests and confirm the expected missing-symbol failures.** Run: `cmake --build apps/native/build-mingw2 --target native-slice-plane-tests`; then execute the test binary. Expected: compilation fails because the mapper implementation is absent.
- [x] **Step 3: Implement the mapper** using inverse matrix point mapping and the transpose of the transform's linear portion for plane-normal mapping. Normalize and reject degenerate results.
- [x] **Step 4: Run the mapper tests** with `ctest --test-dir apps/native/build-mingw2 -R native-slice-plane-tests --output-on-failure` and confirm every case passes.

### Task 2: Asynchronous API client

**Files:**
- Create: `apps/native/src/SliceCommandClient.h`
- Create: `apps/native/src/SliceCommandClient.cpp`
- Create: `apps/native/tests/SliceCommandClientTests.cpp`
- Modify: `apps/native/CMakeLists.txt`

**Interfaces:**
- `SliceCommandClient(QObject *parent = nullptr)` owns `QNetworkAccessManager` and exposes a configurable `apiBaseUrl` property, defaulting to `OUTLAW_FORGE_API_URL` or `http://127.0.0.1:8000`.
- `registerSource(const QUrl &sourceFile, const QString &filename) -> void` lazily creates a session project at `POST /api/v1/projects`, uploads STL/OBJ via multipart form data to `/api/v1/projects/{projectId}/models/import`, and emits `sourceRegistered(filename, projectId, modelId)` or `sourceRegistrationFailed(filename, message)`.
- `sliceModel(requestId, modelId, originMm, normal, keepPositive, localToWorld) -> void` maps the plane, posts `SliceModelPayload` defaults (`cap_faces=true`, `create_pegs=false`) to `/api/v1/projects/{projectId}/models/{modelId}/slice`, fetches both returned `/file` assets, and emits `sliceCompleted(requestId, topModelId, topName, topUrl, topWatertight, bottomModelId, bottomName, bottomUrl, bottomWatertight, cutAreaCm2, message)` or `sliceFailed(requestId, message, persistedTopModelId, persistedBottomModelId)`.
- Save downloaded outputs under `QStandardPaths::AppLocalDataLocation/derived-slices/` using collision-resistant names; never modify source files.

- [x] **Step 1: Write failing local-server tests** for project creation and source upload, exact slice payload/defaults and project-scoped paths, both result downloads, per-half watertight metadata, API error responses, malformed JSON, and partial download failure with returned persisted IDs.
- [x] **Step 2: Run the client tests and confirm expected missing-class failures.** Run: `cmake --build apps/native/build-mingw2 --target native-slice-command-tests`; expected: compilation fails because the client is absent.
- [x] **Step 3: Implement the client** as an asynchronous request state machine. Parse only fields needed from existing `Project`, `WorkingModel`, and `SliceModelResult` responses; do not change backend or shared contracts.
- [x] **Step 4: Run the local-server tests** with `ctest --test-dir apps/native/build-mingw2 -R native-slice-command-tests --output-on-failure` and confirm success and failure paths pass.

### Task 3: Native scene integration

**Files:**
- Modify: `apps/native/src/main.cpp`
- Modify: `apps/native/CMakeLists.txt`
- Modify: `apps/native/qml/Main.qml`

**Interfaces:**
- Register one `SliceCommandClient` instance as QML context property `sliceCommandClient`.
- Add `backendModelId` to each scene row; duplicates retain it and returned halves receive their respective API model IDs.
- The active scene instance's `sceneTransform` is passed to `sliceModel`; its transform values are copied to both returned scene rows.

- [x] **Step 1: Extend the client tests** to assert that successful completion includes both model IDs, filenames, saved paths, watertight flags, and cut area, while failures include any model IDs already persisted by the API.
- [x] **Step 2: Run the native test target** and confirm those assertions fail before the completion signals are implemented.
- [x] **Step 3: Implement QML integration** by replacing `applyPlaneSlice()`'s local geometry invocation with the async client call, loading downloaded results into temporary `MeshGeometry` objects, and mutating scene rows only after both files load.
- [x] **Step 4: Build and launch the native app**; compile succeeded. Runtime service behavior is covered by the local HTTP stub; live API workflow is pending because no service is listening on the configured local API port.

### Task 4: Migration docs and final verification

**Files:**
- Modify: `docs/NATIVE_VIEWPORT_MIGRATION.md`
- Modify: `apps/native/README.md`

- [x] **Step 1: Update native migration status** to describe service-backed STL/OBJ slice, API dependency, provenance, 3MF limitation, and the remaining geometry operations.
- [x] **Step 2: Run the native CTest target** with `ctest --test-dir apps/native/build-mingw2 --output-on-failure` and confirm all native geometry and command tests pass (3/3).
- [x] **Step 3: Build the native application** with `cmake --build apps/native/build-mingw2 --target outlaw-forge-native` and confirm a successful exit; the app was launched and its native viewport window was discovered.
- [x] **Step 4: Review the final diff** for source immutability, Z-up/mm consistency, synced API contracts, and user-facing copy without em or en dashes. `git diff --check` passed. The API was not running, so a live service-backed cut remains unverified; local HTTP stub success and failure paths passed.

## Self-review

- Spec coverage: source registration and identity are in Tasks 2-3; eligibility and error behavior are in Tasks 2-3; world-to-source plane conversion is in Tasks 1-3; derived file loading and both/single-side presentation are in Task 3; documentation and regression verification are in Task 4.
- Type consistency: the mapper accepts `QMatrix4x4`, `QVector3D` origin/normal, output pointers, and an error string; the client takes that matrix and emits downloaded paths before QML creates scene geometry.
- Highest-risk review inputs are listed once in Review Focus and included in Task 1, 2, or 3 checks.
- Scope: no backend/shared schema changes, saved-project browser, peg controls, or migration of other operations.
