# Native Service-Backed Auto-Orient Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Add native Qt auto-orientation through the existing project API route, with downloaded geometry, visible result metrics, and safe recovery.

**Architecture:** Generalize the existing slice client as `GeometryCommandClient`, retaining its source registration and slicing behavior while adding asynchronous auto-orient and result-download retry. QML updates every scene instance sharing the service model only after the returned mesh loads; its instance transforms and the original imported geometry stay intact.

**Tech Stack:** C++20, Qt 6.6 Core/Quick/Quick3D/Network/Test, Qt Quick QML, existing FastAPI API.

**Spec:** `docs/superpowers/specs/2026-10-23-native-service-backed-auto-orient-design.md`

## Global Constraints

- Keep all model dimensions and geometry coordinates in millimetres and the Qt scene right-handed and Z-up.
- Never modify imported source files; load service output as a separate local geometry object.
- Reuse `POST /api/v1/projects/{project_id}/models/{model_id}/auto_orient` and `GET /api/v1/projects/{project_id}/models/{model_id}/file`; do not change FastAPI or shared TypeScript contracts.
- The service returns baked oriented geometry and mutates the existing working-model record; do not apply `optimal_rotation_deg` again as an instance transform.
- Only registered STL/OBJ models support this service command. Keep 3MF locally viewable and disable the service action for it.
- Do not claim auto-orient guarantees watertightness or overall printability.

## Review Focus

- A successful API operation followed by failed file download is persisted remotely: offer a GET-only retry without running auto-orient again.
- Malformed response metadata or an empty/unreadable file must leave the current displayed geometry unchanged.
- Deleted or replaced scene instances may complete after the response; update only extant instances with the matching backend model ID.
- Duplicate native instances share one service model ID; update their shared base geometry while preserving each instance's independent transform and visibility.
- The service output already contains the optimal rotation and bed placement; do not double-rotate or alter local instance transforms.

---

### Task 1: Generalize the native service command client

**Files:**
- Rename: `apps/native/src/SliceCommandClient.h` to `apps/native/src/GeometryCommandClient.h`
- Rename: `apps/native/src/SliceCommandClient.cpp` to `apps/native/src/GeometryCommandClient.cpp`
- Rename: `apps/native/tests/SliceCommandClientTests.cpp` to `apps/native/tests/GeometryCommandClientTests.cpp`
- Modify: `apps/native/CMakeLists.txt`, `apps/native/src/main.cpp`, `apps/native/qml/Main.qml`

**Interfaces:** Keep current source-registration and slice methods/signals unchanged, with class and QML context property renamed to `GeometryCommandClient` and `geometryCommandClient`.

- [ ] Rename class, files, test target, QML context property, and references without changing behavior.
- [ ] Run `cmake --build apps/native/build-mingw2` and `ctest --test-dir apps/native/build-mingw2 --output-on-failure`; expect the app target and all existing native tests to pass.

### Task 2: Implement and test asynchronous auto-orient requests

**Files:**
- Modify: `apps/native/src/GeometryCommandClient.h`
- Modify: `apps/native/src/GeometryCommandClient.cpp`
- Modify: `apps/native/tests/GeometryCommandClientTests.cpp`
- Modify: `apps/native/CMakeLists.txt`

**Interfaces:**
- `Q_INVOKABLE void autoOrientModel(const QString &requestId, const QString &modelId)` posts `{}` and emits `autoOrientCompleted(requestId, modelId, filename, localFileUrl, optimalRotationDeg, originalOverhangCm2, optimizedOverhangCm2, reductionPercentage, message)` after the result file is saved.
- `Q_INVOKABLE void retryAutoOrientDownload(const QString &requestId)` retries only the GET for a previously returned model ID after a download failure.
- Emit `autoOrientFailed(requestId, message)` for service/response failures and `autoOrientDownloadFailed(requestId, modelId, message)` when the service returned a persisted result but its file could not be downloaded.

- [ ] Add stub-server tests for success, exact route/payload, result metrics and file bytes; API rejection; malformed or incomplete response; and failed download followed by successful GET-only retry with exactly one POST.
- [ ] Build and run the new focused test to confirm the new client behavior is absent or failing.
- [ ] Implement the asynchronous POST, strict response parsing, collision-safe `QSaveFile` download under app-local `derived-geometry/`, and retained retry metadata.
- [ ] Run the focused auto-orient tests, then the complete `ctest --test-dir apps/native/build-mingw2 --output-on-failure`; expect all command, plane-mapping, and geometry tests to pass.

### Task 3: Add the Qt viewport action and atomic scene update

**Files:**
- Modify: `apps/native/qml/Main.qml`

**Interfaces:** Connect to `geometryCommandClient` signals from Task 2. Keep the command request ID tied to the selected instance and backend model ID.

- [ ] Add an Auto-orient control enabled only for a selected, registered STL/OBJ instance and while no request is pending; expose a retry control only after persisted-result download failure.
- [ ] On completion, load the saved STL/OBJ into temporary `MeshGeometry`; only after successful parsing, update all extant scene rows sharing that backend model ID to the new shared geometry key.
- [ ] Preserve every matching row's position, rotation, scale, and visibility; leave `importedGeometry` untouched. Keep geometry state and status unchanged on request, download, or local parse failure.
- [ ] Display the returned optimal rotation and overhang reduction in degrees/cm² and percent, plus service message; refresh mesh analysis and ensure retry does not repeat the POST.
- [ ] Build and launch `outlaw-forge-native`; manually verify registered STL and OBJ success, unregistered/3MF disabled state, a service error, and recovery after a simulated download failure.

### Task 4: Update migration documentation and verify the phase

**Files:**
- Modify: `docs/NATIVE_VIEWPORT_MIGRATION.md`
- Modify: `apps/native/README.md`
- Modify: `docs/ROADMAP.md`
- Modify: `docs/QA_ACCEPTANCE.md`

- [ ] Document auto-orient as a service-backed command, its in-place working-model identity, API dependency, baked output geometry, GET-only recovery, and STL/OBJ limitation.
- [ ] Run `cmake --build apps/native/build-mingw2 --target outlaw-forge-native`, then `ctest --test-dir apps/native/build-mingw2 --output-on-failure` and `git diff --check`; expect a successful build, all native tests passing, and no whitespace errors.
- [ ] Review docs and UI copy against the spec; distinguish local stub coverage from live API behavior and do not claim a live service check unless observed.

## Self-review

- Spec coverage: existing route and project identity, source immutability, shared duplicate geometry, per-instance transform preservation, metrics, STL/OBJ eligibility, service errors, and GET-only retry are covered in Tasks 2-4.
- Type consistency: the command uses the same `QString` request/model IDs, `QVector3D` rotation, and `QUrl` output expected by QML; all renamed C++ symbols and CMake sources are listed in Task 1.
- Review focus is tested in the stub client cases and manually checked at the QML scene boundary.
- Scope is limited to one existing API command and its native presentation; no API contracts, local orientation algorithm, project reopening, or repair behavior changes.
