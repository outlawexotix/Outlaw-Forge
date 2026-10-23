# Native Component Split and Simplify Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add local connected-component splitting and reviewable deterministic mesh simplification to the Qt viewport.

**Architecture:** Keep the geometry algorithms in `MeshGeometry`, return new output geometries, and let QML publish successful outputs as selectable derived scene instances. Component connectivity uses shared undirected edges with the existing 0.00001 mm quantized position tolerance. Simplification uses deterministic vertex clustering and reports requested and achieved triangle reduction plus output topology metrics.

**Tech Stack:** C++20, Qt 6.6 Quick 3D, Qt Quick/QML, Qt Test.

**Spec:** `docs/superpowers/specs/2026-10-23-native-local-orcaslicer-feature-set-design.md`

## Global Constraints

- All dimensional data and mesh coordinates are in millimetres.
- Never overwrite raw source meshes.
- Operations are deterministic and local to the Qt application.
- Failed or unsupported operations leave current scene and source files unchanged.
- Derived results remain selectable and keep correct millimetre dimensions.

## Review Focus

- Triangles that only touch at one vertex remain separate edge-connected components; test this explicitly.
- A mesh with one component is reported without replacing or duplicating the source.
- Component output ordering remains stable when component triangle counts tie; test stable source-order tie breaking.
- Simplification requests outside 1-95 percent fail without changing source or publishing a result; test boundary values.
- Clustering that cannot reach the requested reduction still produces a valid best-effort result with the actual reduction reported; test a low-redundancy mesh.

---

### Task 1: Split edge-connected components

**Files:**
- Modify: `apps/native/src/MeshGeometry.h`
- Modify: `apps/native/src/MeshGeometry.cpp`
- Test: `apps/native/tests/MeshGeometrySliceTests.cpp`
- Modify: `apps/native/qml/Main.qml`
- Modify: `apps/native/README.md`

**Interfaces:**
- Produces `int MeshGeometry::connectedComponentCount() const` and `QVariantMap MeshGeometry::splitConnectedComponents(const QVariantList &outputs) const`.
- Component metadata includes `componentIndex`, `components`, `triangles`, and `revisionId`; each output geometry receives a fresh revision and retains source file identity only as provenance. One batch split call labels and emits every component to avoid repeating a full mesh traversal for each island.
- QML creates temporary derived geometries, cleans all of them on any error, replaces the selected instance with the first component, and appends remaining components with the original instance transforms.

- [x] **Step 1: Write failing component tests** named `splitsEdgeConnectedIslandsInStableOrder`, `doesNotJoinTrianglesTouchingOnlyAtAVertex`, and `rejectsInvalidComponentOutputWithoutChangingSource`. Assert component counts, per-output triangle counts, stable tie ordering, source revision preservation, and invalid-output errors.
- [x] **Step 2: Run the native geometry test target and confirm those tests fail because the component API is missing.**
- [x] **Step 3: Implement deterministic shared-edge component labeling and output extraction in `MeshGeometry.cpp`, using 0.00001 mm quantized endpoint keys and sorting by triangle count descending then first source triangle ascending.**
- [x] **Step 4: Run the focused component tests and confirm they pass.**
- [x] **Step 5: Add a `Split components` action to the mesh tools panel. Use temporary derived geometries and publish them only after every extraction succeeds. On one component, report that no split was needed.**
- [x] **Step 6: Run the complete native CTest suite and build `outlaw-forge-native`; document the local split behavior and edge-connectivity rule.**
- [x] **Step 7: Commit as `feat(native): split disconnected mesh components`.**

### Task 2: Deterministic mesh simplification

**Files:**
- Modify: `apps/native/src/MeshGeometry.h`
- Modify: `apps/native/src/MeshGeometry.cpp`
- Test: `apps/native/tests/MeshGeometrySliceTests.cpp`
- Modify: `apps/native/qml/Main.qml`
- Modify: `apps/native/README.md`

**Interfaces:**
- Produces `QVariantMap MeshGeometry::simplifyMesh(double targetReductionPercent, MeshGeometry *output) const`.
- Accepts integer percentage requests from 1 through 95. The result reports `originalTriangles`, `resultTriangles`, `requestedReductionPercent`, `actualReductionPercent`, `boundaryEdges`, `nonManifoldEdges`, and `degenerateTriangles`.
- QML publishes a derived geometry only on success and leaves the selected source geometry untouched.

- [x] **Step 1: Write failing tests** named `simplifiesSubdividedMeshAndPreservesSource` and `rejectsInvalidSimplificationTargetWithoutChangingOutput`. Assert fewer triangles for a subdivided grid at 50 percent target, finite output points, unchanged source revision/count, valid reported metrics, and invalid-input non-mutation.
- [x] **Step 2: Run the native geometry test target and confirm those tests fail because the simplify API is missing.**
- [x] **Step 3: Implement deterministic spatial vertex clustering in `MeshGeometry.cpp`; remove collapsed faces, choose the deterministic candidate nearest the requested remaining triangle count, validate non-empty finite output, and populate topology and achieved-reduction metrics.**
- [x] **Step 4: Run the focused simplification tests and confirm they pass.**
- [x] **Step 5: Add a bounded 1-95 percent target control and `Simplify` action. Create a derived output; only replace the selected instance after a successful result. Report requested versus achieved reduction and topology counts.**
- [x] **Step 6: Run the complete native CTest suite and build `outlaw-forge-native`; document the best-effort clustering behavior and reported actual reduction.**
- [x] **Step 7: Commit as `feat(native): add local mesh simplification`.**
