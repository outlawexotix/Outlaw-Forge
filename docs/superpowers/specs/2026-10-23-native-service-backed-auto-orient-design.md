# Native Service-Backed Auto-Orient

## Intent

Add an Auto-orient action to the standalone Qt viewport that uses the existing FastAPI orientation algorithm and records its operation in the native session project. This advances the native command boundary without adding a second orientation algorithm.

## Approaches

1. **Call the existing project auto-orient route and load its returned mesh (selected):** reuses the existing deterministic service behavior, response metrics, and operation history without changing API contracts. It requires a registered STL or OBJ and a reachable local service.
2. **Implement orientation locally in Qt:** works offline but duplicates the service algorithm and produces no service operation record; rejected for this migration phase.
3. **Add a new orientation API contract:** unnecessary because the project-scoped endpoint already accepts the required inputs and returns the mesh and metrics; rejected.

## Scope and behavior

- Add a native Auto-orient command for the selected scene geometry when it has a registered backend model ID. The supported service registration path is currently STL and OBJ; 3MF remains local-only.
- Call `POST /api/v1/projects/{project_id}/models/{model_id}/auto_orient` with the existing default payload `{}`. Do not add tunable orientation weights in this phase.
- Download the resulting model through the existing project-scoped file route and parse it into temporary native geometry. Update the scene only after the API response and local mesh load both succeed.
- The API creates a new working-file artifact and operation-history record but updates the existing working-model record in place, so its model ID remains the same. The original uploaded source remains immutable. Native scene instances sharing that backend model ID share the resulting oriented geometry; keep each instance's position, rotation, scale, and visibility unchanged.
- Report the service message, optimal rotation, and overhang-area reduction in the native status UI. A successful orientation is not a guarantee of watertightness or printability; continue to report mesh analysis from the returned geometry.
- If the service call or result download fails, keep the current scene geometry and show an actionable error. If the operation was recorded before download failed, explain that retrying may retrieve the persisted result.

## Non-goals and constraints

- Do not change the FastAPI or shared TypeScript contracts, implement a Qt orientation algorithm, add saved-project reopening, or enable 3MF service registration.
- Keep source uploads immutable, preserve millimetre units and the Qt Z-up scene, and use the service-returned mesh as the baked oriented geometry without applying its reported rotation a second time.
- Cover success, service errors, malformed/incomplete responses, failed result downloads, returned orientation metrics, and preservation of scene state on failure with native command-client tests.

## Acceptance

- A registered STL or OBJ can be auto-oriented through the existing route; the resulting geometry is loaded locally, the reported rotation/reduction are displayed, and the operation appears in the session's API history.
- Every visible instance sharing the backend model ID uses the returned geometry while retaining its own scene transform and visibility; the original imported geometry remains available and unchanged.
- Unsupported/unregistered models and service failures leave all displayed geometry and instance properties unchanged and show a useful status.
