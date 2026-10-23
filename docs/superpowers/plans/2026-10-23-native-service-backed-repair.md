# Native Service-Backed Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Route Repair for registered STL/OBJ models through the existing geometry service while preserving local repair for unregistered models.

**Architecture:** Extend `GeometryCommandClient` with an asynchronous project-scoped repair POST, persisted-file download, and GET-only retry. In QML, load the downloaded mesh into a temporary geometry before replacing every scene instance that shares the backend model ID. Keep the imported upload immutable and leave the existing local repair path for unsupported/unregistered geometry.

**Tech Stack:** C++20, Qt 6 Network, Qt Quick/QML, existing FastAPI project/model/file endpoints.

**Spec:** `docs/superpowers/specs/2026-10-23-native-service-backed-repair-design.md`

## Global Constraints

- All weld tolerances and mesh dimensions are in millimetres.
- Keep the raw upload immutable.
- Do not change FastAPI or shared TypeScript contracts.
- Registered STL/OBJ repair uses the existing project-scoped route and keeps its working-model ID.
- Unregistered models, including 3MF, retain local repair.
- A successful repair does not imply watertightness or printability.

## Review Focus

- A service POST error or malformed response must leave current geometry and every scene row unchanged; check through the running native UI with API error responses.
- A persisted result whose GET fails must expose a retry that does not repeat POST; inspect the route/request sequence while exercising download recovery.
- A returned file that cannot load must leave current geometry unchanged; exercise with a malformed persisted file.
- A repair of a model with duplicate/hidden instances must update shared geometry while preserving each instance's transform and visibility; inspect the scene after repair.
- A tolerance above the service's 1.0 mm maximum must be rejected clearly, while an unregistered model can still use the local repair range; exercise both eligibility paths.

---

### Task 1: Add service-backed repair transport and recovery

**Files:**
- Modify: `apps/native/src/GeometryCommandClient.h`
- Modify: `apps/native/src/GeometryCommandClient.cpp`

**Interfaces:**
- Consumes: registered `modelId`, request ID, and `weldToleranceMm` from QML.
- Produces: `void repairModel(const QString &requestId, const QString &modelId, double weldToleranceMm)`, `void retryRepairDownload(const QString &requestId)`, `repairCompleted(const QString &requestId, const QString &modelId, const QString &filename, const QUrl &localFileUrl, const QVariantMap &report, const QString &message)`, `repairFailed(const QString &requestId, const QString &message)`, and `repairDownloadFailed(const QString &requestId, const QString &modelId, const QString &message)`.

- [x] **Step 1: Add the public repair methods and result signals** using the interfaces above. Keep slice and auto-orient signatures unchanged.
- [x] **Step 2: Implement repair POST parsing** for `RepairModelResult` fields `repaired_model`, `report`, and `message`. Send `fill_holes`, `fix_normals`, `remove_degenerate`, and `weld_vertices` as `true`, and send the selected `weld_tolerance_mm`. Reject non-finite values and values outside `0.00001..1.0` mm before sending.
- [x] **Step 3: Implement persisted result download** from `/api/v1/projects/{project_id}/models/{model_id}/file`, saving to `QStandardPaths::AppLocalDataLocation/derived-repairs/` with a collision-resistant filename. Keep pending repair state after a successful POST if GET fails.
- [x] **Step 4: Implement GET-only retry** by resuming the retained persisted repair download. Keep pending state after retryable GET or local-write failures, remove it after successful download, and never repeat the repair POST during retry.

### Task 2: Connect the native Repair control to the service

**Files:**
- Modify: `apps/native/qml/Main.qml`

**Interfaces:**
- Consumes: Task 1 repair methods and signals, current `backendModelId`, `geometryKey`, and `repairTolerance` control.
- Produces: service repair for eligible registered STL/OBJ; local repair for unregistered models; visible pending, failure, retry, and report states.

- [x] **Step 1: Add QML repair request state and callbacks** keyed by request ID, including persisted-download retry state.
- [x] **Step 2: Route the existing Repair action** to `geometryCommandClient.repairModel` when the selected row has a registered backend model ID and STL/OBJ source. For unregistered geometry, retain the current `MeshGeometry::repairMesh` path. When a service repair tolerance exceeds 1.0 mm, show a clear range message and do not send the request.
- [x] **Step 3: Apply service output transactionally.** Load the downloaded file into temporary `MeshGeometry`; only after it parses, replace `geometryKey` on every scene row with the same backend model ID. Preserve all other scene row properties, selection, and transforms. On parse failure, destroy the temporary geometry and keep the scene unchanged. If no matching row remains, report that the service repair succeeded but the scene no longer contains that model.
- [x] **Step 4: Show the returned report** (holes filled, degenerate faces removed, vertices welded, normals fixed, before/after watertightness, and triangle counts). Show download-only retry after persisted GET failure. Do not show the retry for a POST failure or malformed mesh.
- [x] **Step 5: Keep local repair available for unregistered 3MF and other unsupported geometry** with its current weld-tolerance behavior and status reporting.

### Task 3: Update native operation documentation

**Files:**
- Modify: `apps/native/README.md`
- Modify: `docs/NATIVE_VIEWPORT_MIGRATION.md`
- Modify: `docs/ROADMAP.md`
- Modify: `docs/QA_ACCEPTANCE.md`

- [x] **Step 1: Document service-backed repair** for registered STL/OBJ, the existing API dependency, its repair report, the same-model-ID update, immutable source behavior, tolerance limit, and GET-only download recovery.
- [x] **Step 2: Document the local fallback** for unregistered models and 3MF, and state that the service's watertight result is measured and not guaranteed.
- [x] **Step 3: Update the roadmap and acceptance table** to distinguish implemented native repair from remaining live-service acceptance.

### Task 4: Build and inspect the native feature

**Files:**
- Review: all files changed in Tasks 1-3.

- [x] **Step 1: Build the native executable** with `cmake --build apps/native/build-mingw2 --target outlaw-forge-native -j 6` and resolve build errors.
- [x] **Step 2: Inspect the final diff** for source immutability, millimetre tolerance validation, same-ID instance replacement, retry issuing GET only, accurate report wording, and unrelated changes.
- [x] **Step 3: Launch the rebuilt native application** and confirm the viewport opens with the Repair control available. Do not claim live repair acceptance unless the operation is exercised against the geometry service.
