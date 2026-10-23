# Native Service-Backed Repair

## Intent

Make the native viewport's existing Repair action use Outlaw Forge's canonical geometry service for registered STL and OBJ models. This gives native repair the same deterministic repair algorithm and project operation history as the main workbench while keeping imported source files immutable.

## Goals

- Send repair requests through the existing project-scoped repair endpoint and use its returned mesh and report.
- Preserve the working-model ID, all matching scene instances, their transforms and visibility, and the original upload.
- Replace visible geometry only after the service result has downloaded and parsed successfully.
- Report holes filled, degenerate faces removed, welded vertices, normal fixes, before/after watertightness, and triangle counts without promising that every repair becomes watertight.
- Preserve local repair for unregistered models, including 3MF.
- Provide GET-only retry when the repair operation succeeded but downloading its persisted mesh failed.

## Non-goals

- No changes to the FastAPI or shared TypeScript contracts or repair algorithm.
- No new repair controls beyond the existing weld tolerance.
- No saved-project reopening, 3MF service registration, or guarantee of watertightness.

## Approaches

1. **Call the existing project repair endpoint for registered STL/OBJ (selected):** reuses the service algorithm, report, and operation history. Keep the current local repair path for unregistered models.
2. **Add a native-only repair implementation or continue using local repair:** would duplicate or diverge from the service algorithm and would not create service operation history.
3. **Change the API contract to fit the native control:** unnecessary because the existing endpoint accepts a weld tolerance and its other repair options have suitable defaults.

The user selected the service-backed Repair phase. The existing API accepts weld tolerances from 0.00001 to 1.0 mm; the current native control can exceed 1.0 mm. For registered models, reject an out-of-range value with a clear prompt to choose a supported tolerance rather than silently changing it. Keep the current local range for unregistered models.

## First vertical slice

- Add an asynchronous repair operation to `GeometryCommandClient` using `POST /api/v1/projects/{project_id}/models/{model_id}/repair` with the selected `weld_tolerance_mm`; rely on existing service defaults for hole filling, normal fixing, degenerate removal, and vertex welding.
- Parse the existing `RepairModelResult`, download the persisted model through the project-scoped file route, and save it under app-local `derived-repairs/` storage.
- Route the current Repair button to the service for a registered STL/OBJ and keep local repair for unregistered models. Disable duplicate repair requests while one is pending.
- On successful parse, update every visible or hidden instance with that backend model ID to the new shared geometry. Preserve per-instance transform, visibility, selection, and model ID.
- On API error or invalid response, leave the scene unchanged. If the POST succeeded but the GET failed, expose a retry that repeats only the GET. If the downloaded file cannot be parsed, leave the scene unchanged and report that failure.
- Show the service report and whether the result is watertight. Do not describe a non-watertight result as closed or imply that a successful repair guarantees printability.

## Constraints and acceptance

- All weld tolerances and mesh dimensions are in millimetres; the current source upload remains read-only.
- Use existing Pydantic response fields and routes; no API or shared contract changes.
- A registered STL/OBJ repair creates a service operation record and downloads the updated geometry before the native scene changes. Other instances sharing the model ID receive that geometry without losing their individual state.
- API failures and file-download failures do not discard the current scene geometry; persisted download recovery does not repeat the repair POST.

## Feature decision record

- **Target seam:** `apps/native/src/GeometryCommandClient.*` for transport and persisted-result retrieval; `apps/native/qml/Main.qml` for eligibility, pending/retry state, scene replacement, and report display.
- **Topology edge cases:** use the service's existing hole-fill, normal, degenerate-face, and weld behavior. Report the returned watertight flag as measured; do not infer closure from a successful request.
- **Storage policy:** keep the raw upload immutable. The existing service route writes a derived working artifact and updates the same working-model ID; cache the downloaded result in app-local `derived-repairs/`.
- **Verification criterion:** build the native Qt target and check registered STL/OBJ success, local fallback for unregistered/3MF, shared-instance state preservation, service failure, and GET-only download recovery.
