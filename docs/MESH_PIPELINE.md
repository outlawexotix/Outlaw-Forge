# Mesh and geometry pipeline

Outlaw Forge separates file parsing, project persistence, deterministic geometry operations, and viewport presentation. The FastAPI service is the current authority for persisted source files, working revisions, operation history, and the main workbench's geometry commands.

## Main workbench data flow

```text
User-selected mesh
  -> format parser and validation
  -> immutable project source file
  -> working model revision
  -> explicit operation request to FastAPI
  -> derived working revision plus operation record
  -> viewport display or export artifact
```

The source upload is not overwritten. Operations take project/model identifiers and typed parameters, and successful results are recorded as derived revisions. Exported files use separate export storage. The API contracts live under `apps/api/app/models` and must stay aligned with TypeScript types under `packages/shared/`.

## Units and coordinate frames

- Geometry services and persisted model dimensions use millimetres.
- Print and build-volume calculations use right-handed Z-up coordinates.
- The web workbench renders through a Three.js Y-up scene conversion. Keep that renderer transform at the presentation boundary.
- The Qt native viewport uses Z-up scene coordinates and maps its active slice plane through the instance transform before calling the same service.
- Do not apply unit conversions implicitly to user-entered millimetres or rewrite the source vertex data to satisfy a renderer's up-axis.

The web and Qt applications have separate scene graphs. Similar labels or controls do not imply a shared runtime coordinate transform.

## Mesh formats

The web loader in `packages/three-tools/src/loaders/geometryLoader.ts` dispatches STL, OBJ, GLTF/GLB, and 3MF parsing through the `three-stdlib` loaders. OBJ and scene-based formats are merged into a display geometry for the viewport; this display path does not promise preservation of original hierarchy, material, color, or slicer project metadata. Project import and API operation support is defined by API validation and may be narrower than what a viewport parser can display.

The native Qt application has its own loaders: STL, OBJ, and limited 3MF. Its service-backed slicing currently accepts STL and OBJ. The native 3MF reader handles the first build item when it references a direct mesh object and applies the serialized transform and recognized unit conversion; component graphs and richer project data are not supported. See [native migration](./NATIVE_VIEWPORT_MIGRATION.md).

## Geometry metrics

For triangle vertices \(a,b,c\), area is computed from the cross product:

\[
A = \frac{1}{2}\| (b-a) \times (c-a) \|
\]

For a consistently oriented triangle mesh, signed volume uses the divergence formula:

\[
V = \frac{1}{6}\sum a \cdot (b \times c)
\]

Millimetre-based area converts to square centimetres by multiplying by `0.01`; volume converts to cubic centimetres by multiplying by `0.001`. API analysis also reports bounds, triangle/vertex counts, and watertightness. A visually closed surface is not evidence of a watertight mesh; use the service's computed result.

## Watertightness and slice closure

The API slice payload defaults to capped faces and does not create pegs unless requested. The native slice command requests `cap_faces=true` and `create_pegs=false`, then reads `is_watertight` independently from the two returned working models. The native UI does not label the result closed if either half reports false. Capping is an operation request, not a guarantee: non-manifold input, degenerate geometry, or difficult section loops can still yield an open result. Mesh repair remains a separate explicit operation.

## Determinism and source safety

- Geometry changes require explicit operation parameters.
- AI, if connected in a future workflow, can only recommend actions; it cannot silently mutate a mesh or project.
- Imported originals remain immutable. Do not write derived geometry over a path in `data/uploads/` or configured original storage.
- Failed requests should preserve the current displayed source and surface any persisted result identifiers that need recovery.
- Runtime databases, original uploads, working meshes, and exports are local data and are not source-control artifacts.
