# Native Service-Backed Slice Command

## Intent

Move the native viewport's planar cut behind the geometry command boundary in `docs/NATIVE_VIEWPORT_MIGRATION.md`. The native app keeps owning plane interaction and scene presentation; the existing FastAPI service produces and records the derived mesh revisions. This gives the cut a durable project identity and operation provenance while preserving the imported source.

## Goals

- Slice a selected native mesh through the existing project-scoped API and display the returned mesh results.
- Keep the input source revision unchanged. Associate native scene models with their API project and working-model IDs.
- Preserve millimetre coordinates, the current Z-up convention, the selected instance transform, and the sign of the requested cut side.
- Surface service connection, validation, and processing errors without changing the current scene geometry.
- Keep request and response types aligned with the existing Pydantic and shared TypeScript contracts; do not add a parallel slice API.

## First vertical slice

- Lazily create one API project for the native session and upload each supported source mesh through the existing project import route. Preserve the current local immutable source geometry for viewport display and associate it with the returned API identifiers.
- Enable service-backed slicing for STL and OBJ, which are supported by both native import and the API import path. If the API cannot import a selected format (including the current limited 3MF path), report that limitation and leave the scene untouched. Do not silently switch algorithms.
- Send the existing plane origin and normal after mapping them from world space into source-mesh coordinates using the inverse instance transform. This preserves the same visible plane for translated, rotated, scaled, or mirrored instances.
- Use the existing API defaults for capped faces and disabled pegs. Do not add peg controls in this phase.
- Fetch both returned working meshes using the project-scoped `/file` route, then add them as derived native scene geometry while retaining the selected instance placement transform.
- Carry each returned model's existing `is_watertight` metadata into the native status. Warn by half when the API output is not watertight; report closure only when both returned halves are watertight.
- For “keep both,” show both returned halves as separate scene entries. For either single-side option, replace the selected scene entry with that side and leave the other persisted result in API project history. The current API always creates and records both outputs.
- On request or download failure, keep the input selected and visible, discard any partial local result, and show an actionable status message. The service operation may already be persisted if a later download fails; show its returned model IDs when available so the user can recover it from the project.

## Alternatives considered

1. **Continue slicing locally in C++:** simplest and works without the API, but does not satisfy the migration command boundary or record provenance. Rejected for this phase.
2. **Call the existing service and keep results local only:** uses the service algorithm but loses the service's durable project records and diverges from its current route behavior. Rejected.
3. **Service-backed command using existing project import, slice, and file routes:** reuses deterministic service behavior and current provenance records with no new API contract. Chosen. It requires the local API to be reachable and adds backend project/model identity to the native session.

## Non-goals

- Reopening or browsing saved projects in the native UI.
- Moving, repairing, or otherwise migrating other geometry commands.
- Expanding API format support, changing the slice algorithm, or adding API contracts.
- Implementing service-free fallback slicing, peg creation controls, or parity/cutover work.

## Acceptance criteria

- Importing an STL or OBJ for service-backed use creates a project source model while preserving the original local scene geometry.
- A successful slice sends the selected model ID and mapped plane parameters, receives two persisted working models, and records a successful `SLICE` operation.
- Native status reports the API watertight result independently for both halves and does not claim that the cut is closed when either half is open.
- Both-side and single-side display modes show the expected returned geometry and preserve the original instance transform; the original source remains unchanged.
- Unsupported format, unreachable service, rejected cut, and failed result download leave the source scene entry intact and show a useful status.
- Regression coverage verifies plane mapping for translation, rotation, non-uniform scale, and reflection, plus service success and failure handling.

## Constraints and implementation boundary

The API receives coordinates in millimetres and uses the existing Pydantic `SliceModelPayload` and `SliceModelResult`. The native command client should own HTTP transport and typed parsing; QML should only start the command and reflect pending/success/failure state. Configure the API base URL with `OUTLAW_FORGE_API_URL`, defaulting to `http://127.0.0.1:8000`; API routes use the `/api/v1` prefix. The endpoints are `POST /api/v1/projects/{project_id}/models/{model_id}/slice` and `GET /api/v1/projects/{project_id}/models/{model_id}/file`. The API remains the source of durable operation provenance. No source file in `data/uploads/` is modified.
