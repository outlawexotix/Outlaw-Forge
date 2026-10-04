# Outlaw Forge — Phase 10 E2E Test Suite Infrastructure & Architecture

## 1. Overview & System Under Test

This document defines the End-to-End (E2E) test infrastructure, architecture, verification methodology, and quality thresholds for **Outlaw Forge Phase 10: Parametric 3D Infill & Internal Lattice Generator**.

Outlaw Forge is a specialized 3D-printing preparation workbench combining a high-performance Python/FastAPI computational geometry engine with a Next.js / Three.js CAD workbench. Phase 10 provides:
1. **Procedural 3D Lattice Infill Generation (R1)**: Volumetric internal infill generation supporting Gyroid (TPMS), Honeycomb / Hexagonal, Rectilinear Grid, and Cubic lattices with parametric density (5% to 100%) and unit cell spacing in millimetres.
2. **Internal Cavity & Rib Reinforcement (R2)**: Automatic internal structural rib generation along thin hollow walls and continuous internal drainage channels to prevent resin suction and air pockets.
3. **Viewport Cross-Section & Infill Visualizer (R3)**: Real-time GPU cut-away cross-section shader and Workbench Inspector clipping controls with density scrubbers.
4. **Export & OrcaSlicer 3MF Integration (R4)**: Physical single-mesh infill embedding (STL, OBJ, GLB) and OrcaSlicer 3MF package metadata injection.

```text
 ┌────────────────────────────────────────────────────────────────────────┐
 │                      E2E Test Execution Engine                         │
 │                                                                        │
 │  ┌─────────────────────────┐             ┌──────────────────────────┐  │
 │  │   In-Process TestClient │             │  Black-Box HTTP Runner   │  │
 │  │   (FastAPI / Pytest)    │             │  (Live Running Daemon)   │  │
 │  └────────────┬────────────┘             └────────────┬─────────────┘  │
 │               │                                       │                │
 │               ▼                                       ▼                │
 │  ┌──────────────────────────────────────────────────────────────────┐  │
 │  │            Dual-Route API Endpoints (/v1/models/...)             │  │
 │  │            - POST /models/{id}/infill                            │  │
 │  │            - POST /models/{id}/reinforce_ribs                    │  │
 │  │            - POST /models/{id}/export (embed_infill: true)       │  │
 │  │            - POST /projects/{id}/export_3mf                      │  │
 │  └──────────────────────────────────┬───────────────────────────────┘  │
 │                                     │                                  │
 │                                     ▼                                  │
 │  ┌──────────────────────────────────────────────────────────────────┐  │
 │  │            Geometry Engine & Verification Oracles                │  │
 │  │            - Manifold3D (Exact 2-manifold CSG booleans)          │  │
 │  │            - Trimesh (Watertightness, volume, topology)          │  │
 │  │            - OPC ZIP Container & OrcaSlicer XML / INI Parser     │  │
 │  │            - GLSL Shader Uniform & Contract Validator            │  │
 │  └──────────────────────────────────────────────────────────────────┘  │
 └────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Feature Inventory & Requirement Traceability

| Req ID | Feature ID | Name | Description | Authoritative Source |
| :--- | :--- | :--- | :--- | :--- |
| **R1** | F1 | Gyroid TPMS Infill | Triply periodic minimal surface infill with isotropic shear and compressive strength. Level set SDF polygonization. | `ORIGINAL_REQUEST.md` R1, `PROJECT.md` F1 |
| **R1** | F2 | Honeycomb Lattice | High-strength vertical compressive hexagonal cell lattice extruded along Z-axis. | `ORIGINAL_REQUEST.md` R1, `PROJECT.md` F2 |
| **R1** | F3 | Rectilinear & Cubic Infill | Orthogonal 2D grid and 3D cubic lattice structures for high-speed slicing and support. | `ORIGINAL_REQUEST.md` R1, `PROJECT.md` F3 |
| **R1** | F4 | Parametric Density & Spacing | Configurable density (5% to 100%) and cell spacing in millimetres (strict 1.0 unit = 1.0 mm). | `ORIGINAL_REQUEST.md` R1, `PROJECT.md` F4 |
| **R2** | F5 | Internal Structural Ribbing | Automatic internal ribs along hollow walls below threshold thickness to prevent buckling. | `ORIGINAL_REQUEST.md` R2, `PROJECT.md` F5 |
| **R2** | F6 | Continuous Drainage Channels | Internal drainage conduits and weep holes along gravity vector to prevent liquid/air entrapment. | `ORIGINAL_REQUEST.md` R2, `PROJECT.md` F6 |
| **R3** | F7 | Viewport Cross-Section Shader | Three.js cut-away shader and stencil capping rendering internal lattice & shell in real time. | `ORIGINAL_REQUEST.md` R3, `PROJECT.md` F7 |
| **R3** | F8 | Workbench Inspector Controls | Dynamic clipping plane controls with density scrubbers in Workbench Inspector (dense CAD layout). | `ORIGINAL_REQUEST.md` R3, `PROJECT.md` F8 |
| **R4** | F9 | Single-Mesh Infill Embedding | Physical boolean fusion of internal infill with outer shell into watertight STL/OBJ/GLB exports. | `ORIGINAL_REQUEST.md` R4, `PROJECT.md` F9 |
| **R4** | F10 | OrcaSlicer 3MF Metadata | Injection of per-object infill tags, plate metadata, and `Metadata/slice_info.config` into 3MF. | `ORIGINAL_REQUEST.md` R4, `PROJECT.md` F10 |
| **R4** | F11 | 3MF Viewport Loader | Re-import and parsing of exported 3MF bundles via Three.js loader. | `ORIGINAL_REQUEST.md` R4, `PROJECT.md` F11 |

---

## 3. The 4-Tier Test Case Design Methodology

The test suite strictly applies the 4-Tier Test Case Design Methodology to ensure comprehensive, opaque-box, requirement-driven verification:

```text
 ┌────────────────────────────────────────────────────────────────────────┐
 │ 4-TIER TEST ARCHITECTURE                                               │
 │                                                                        │
 │  [Tier 1: Feature Coverage] >=5 test cases per feature (R1, R2, R3, R4)│
 │    - Systematic verification of all functional parameters and outputs   │
 │                                                                        │
 │  [Tier 2: Boundary & Corner Cases] >=5 test cases per feature          │
 │    - 5% min density, 100% solid density, tiny/huge spacing, invalid    │
 │                                                                        │
 │  [Tier 3: Cross-Feature Combinations] Pairwise interactions            │
 │    - Hollow + Infill, Ribbing + Drainage, Infill + 3MF Export, etc.    │
 │                                                                        │
 │  [Tier 4: Real-World Scenarios] End-to-end production workflows         │
 │    - Hollow Figurine + Gyroid + Drain, Structural Bracket + Honeycomb, │
 │      SLA Miniature + Rectilinear Grid + Viewport Cutaway               │
 └────────────────────────────────────────────────────────────────────────┘
```

### 3.1 Tier 1: Feature Coverage (>=5 test cases per feature)
- **Feature 1 (Gyroid TPMS)**:
  1. Default gyroid generation on 20mm cube with 20% density and 10mm unit cell spacing.
  2. Bounding box preservation: derived mesh bounds match input bounds within 0.05mm.
  3. Watertightness check: generated gyroid model is 2-manifold without boundary edges.
  4. Unit cell spacing scaling: 5mm vs 10mm vs 20mm pitch variation produces valid geometry.
  5. Density scaling progression: 10% vs 25% vs 50% density produces strictly increasing volume.
- **Feature 2 (Honeycomb Lattice)**:
  1. Default honeycomb generation on 20mm cube with hexagonal cells extruded along Z-axis.
  2. Vertical compressive orientation validation along Z-axis.
  3. Cell spacing variation (6mm vs 12mm vs 18mm) produces valid manifold mesh.
  4. Density variation (10% to 50%) alters hexagonal wall thickness proportionally.
  5. Watertightness and positive non-zero volume verification.
- **Feature 3 (Rectilinear & Cubic Infill)**:
  1. Rectilinear grid generation with orthogonal intersecting 2D walls.
  2. Cubic 3D lattice generation with 3-axis isotropic structural interconnects.
  3. Rectilinear grid spacing variation produces regular cell intervals.
  4. Cubic lattice cell spacing variation produces watertight multi-axis cells.
  5. Manifold integrity: zero open edges and zero self-intersections.
- **Feature 4 (Parametric Density & Cell Spacing)**:
  1. Density range test across allowed spectrum (0.05 to 1.0).
  2. Unit cell spacing test across normal spectrum (2.0mm to 30.0mm).
  3. Wall thickness derivation or manual override compliance.
  4. Volume reduction computation accuracy (`volume_reduction_percent > 0`).
  5. Metadata audit tracking: operation recorded in project audit history.
- **Feature 5 (Internal Structural Ribbing)**:
  1. Structural rib generation on thin hollow walls.
  2. Rib spacing parameter control (10mm, 15mm, 20mm).
  3. Rib thickness parameter control (1.0mm, 1.5mm, 2.0mm).
  4. Rib protrusion height parameter control into internal cavity.
  5. Rib count accounting in result payload (`ribs_generated >= 1`).
- **Feature 6 (Continuous Drainage Channels)**:
  1. Drainage conduit generation along gravity vector (Z-axis).
  2. Drainage diameter parameter variation (2.0mm vs 4.0mm).
  3. Weep hole perforation in structural ribs.
  4. Continuous drain path from internal cavity to exterior.
  5. Cavity inspection: zero isolated fluid/resin trap bays.
- **Feature 7 (Viewport Cross-Section Shader Contract)**:
  1. Shader uniform contract validation (`uInfillPattern`, `uInfillDensity`, `uCellSpacing`, `uShellThickness`, `uPlanePoint`, `uPlaneNormal`).
  2. Pattern uniform mapping (0=Gyroid, 1=Honeycomb, 2=Rectilinear, 3=Cubic).
  3. Local clipping flag enablement contract (`localClippingEnabled = true`).
  4. Cutting plane normal direction invertibility.
  5. Cut edge highlight threshold contract.
- **Feature 8 (Workbench Inspector Controls & Client)**:
  1. API client contract payload formatting (`InfillGeneratePayload`).
  2. Inspector density scrubber range constraint (0.05 to 1.0).
  3. Unit cell spacing slider step and range constraints.
  4. Cutting plane position scrubber synchronization.
  5. Anti-slop copy audit: zero em-dashes (`—`) in UI copy.
- **Feature 9 (Single-Mesh Infill Embedding)**:
  1. Physical embedding into STL export.
  2. Physical embedding into OBJ export.
  3. Physical embedding into GLB export.
  4. Watertight composite geometry verification.
  5. Export artifact persistence on disk in `data/exports/`.
- **Feature 10 (OrcaSlicer 3MF Metadata)**:
  1. 3MF OPC ZIP container integrity (`[Content_Types].xml`, `_rels/.rels`, `3D/3dmodel.model`).
  2. `Metadata/project_info.json` infill configuration tags.
  3. `Metadata/slice_info.config` OrcaSlicer process INI parameter injection.
  4. `3D/3dmodel.model` object-level infill metadata tags (`sparse_infill_pattern`, `sparse_infill_density`).
  5. Multi-object plate export packaging.
- **Feature 11 (3MF Viewport Loader)**:
  1. `geometryLoader` format detector recognition for `3mf`.
  2. `parseMeshBuffer` dispatching to `ThreeMFLoader`.
  3. Mesh geometry and vertex buffer extraction from 3MF buffer.
  4. Transformation and unit scale preservation (mm).
  5. Error handling for malformed or truncated 3MF archive.

### 3.2 Tier 2: Boundary & Corner Cases (>=5 test cases per feature)
- Minimum density boundary ($5\% / 0.05$): verified minimal physical lattice struts.
- Maximum solid density boundary ($100\% / 1.0$): verified full solid infill without void cutouts.
- Tiny unit cell spacing ($1.0\text{ mm} - 2.0\text{ mm}$): dense lattice generation without numerical crash.
- Large unit cell spacing ($50.0\text{ mm}$ exceeding cavity bounds): graceful boundary handling.
- Zero / negative density or cell spacing: strict schema rejection with HTTP 422 Unprocessable Entity.
- Extreme aspect-ratio meshes: thin flat plates ($100\times 100\times 1\text{ mm}$) and tall slender needles ($1\times 1\times 100\text{ mm}$).
- Degenerate/Extreme mesh bounding boxes ($1\text{ mm}$ calibration cube vs $300\text{ mm}$ oversized volume).
- Clipping plane placed outside bounding box: graceful cross-section handling.
- Zero drainage radius or oversize drainage radius exceeding wall dimensions: strict schema validation.

### 3.3 Tier 3: Cross-Feature Combinations (Pairwise Interactions)
1. **Infill + Hollow**: Import solid mesh -> Hollow with 2.0mm wall -> Generate Gyroid infill in internal cavity -> Verify shell thickness preserved.
2. **Infill + Ribbing + Drainage**: Hollow model -> Reinforce with structural ribs -> Perforate continuous drainage channel -> Generate honeycomb lattice.
3. **Infill + Scaling & Bed Centering**: Scale model to 150mm -> Center on build bed ($Z_{\min} = 0$) -> Generate infill -> Verify exact millimeter coordinates.
4. **Infill + OrcaSlicer 3MF Export**: Generate procedural infill -> Export to 3MF -> Unpack archive -> Verify both embedded 3D model and OrcaSlicer XML/INI metadata.
5. **Infill + Single-Mesh Physical STL Export**: Generate infill -> Embed into single composite STL -> Read back with `trimesh` -> Verify watertight 2-manifold STL.
6. **Infill + Cross-Section Shader Viewport Sync**: Generate infill -> Synchronize cut plane origin and normal with viewport shader uniforms.

### 3.4 Tier 4: Real-World Production Workflows
1. **Scenario 1: Hollow SLA Resin Figurine with Gyroid Infill & Drainage**:
   Full resin printing preparation workflow: Import hollow statue model -> Apply 15% isotropic Gyroid infill -> Add vertical Z drainage conduit -> Verify resin fluid escape path -> Export SLA-ready composite mesh.
2. **Scenario 2: High-Strength FDM Structural Bracket with Honeycomb Infill & Rib Reinforcement**:
   Industrial mechanical bracket workflow: Import bracket model -> Evaluate printability on Ender-3 bed -> Add 1.5mm wall-stiffening ribs -> Fill with 30% Honeycomb compressive lattice -> Export OrcaSlicer 3MF plate with process tags.
3. **Scenario 3: SLA Miniature Base with Rectilinear Grid Infill, Drainage Weep Holes & Stencil Cross-Section**:
   Gaming miniature base workflow: Import plinth geometry -> Hollow to 1.2mm -> Generate 20% Rectilinear grid infill -> Perforate weep drainage holes -> Inspect interactive cross-section clipping plane -> Export validated STL.

---

## 4. Expected Output Derivation & Verification Oracles

| Metric / Property | Authoritative Source / Oracle | Tolerance / Expected Value |
| :--- | :--- | :--- |
| **Dimensional Coordinates** | `PROJECT.md` Core Tenet 1: Millimetre-Standard | Absolute error $\le 0.05\text{ mm}$ |
| **Mesh Watertightness** | `trimesh.Trimesh.is_watertight` | Must be `True` |
| **Manifold Topology** | Euler characteristic / `trimesh.Trimesh.is_volume` | 2-manifold, positive volume $> 0$ |
| **Density Monotonicity** | Mathematical volume fraction: $V_{\text{infill}}(D_2) > V_{\text{infill}}(D_1)$ for $D_2 > D_1$ | Strictly monotonic volume scaling |
| **Volume Reduction** | $\text{VR} = (1.0 - V_{\text{infilled}} / V_{\text{solid}}) \times 100\%$ | $0.0\% < \text{VR} < 95.0\%$ |
| **3MF Container Spec** | 3MF Consortium Core Specification & OPC ZIP packaging | Valid ZIP containing `[Content_Types].xml`, `3D/3dmodel.model` |
| **OrcaSlicer Metadata** | OrcaSlicer Process Config Specification | `sparse_infill_pattern`, `sparse_infill_density` present in `3D/3dmodel.model` & `slice_info.config` |
| **HTTP Contracts** | FastAPI OpenAPI / Pydantic models in `apps/api/app/models/mesh.py` | HTTP 200/201 on success, HTTP 422 on invalid parameters |
| **Copy & Design Standard** | `AGENTS.md` Anti-AI Slop Craft | Zero em-dashes (`—`) in user-facing copy |

---

## 5. Test Infrastructure Execution Modes

The Phase 10 E2E test suite supports two complementary execution modes:

### Mode A: In-Process Pytest E2E Runner
- Uses `fastapi.testclient.TestClient` with temporary isolated SQLite database and isolated storage fixtures.
- Integrated into standard CI: `python -m pytest tests/e2e/test_phase10_e2e.py -v`.
- Requires no manual background server launch.
- Provides deep geometric verification using `trimesh`, `manifold3d`, and `zipfile`.

### Mode B: Out-of-Process Black-Box HTTP Runner
- Executable as standalone script: `python tests/e2e/test_phase10_e2e.py --base-url http://127.0.0.1:8000`.
- Operates strictly over HTTP using standard library `urllib` or `requests`.
- Validates deployed container or dev server without touching internal application state.

---

## 6. Quality Thresholds & Verification Gates

1. **Pass Rate**: 100% of executed E2E tests must pass.
2. **Execution Latency**: Full E2E suite should complete within 120 seconds in local environment.
3. **Immutability of Source Assets**: Uploaded source files in `data/original/` must have unchanged SHA-256 hashes before and after test execution.
4. **Clean File Lifecycle**: Temporary working and export meshes created during test runs are properly accounted for or isolated in test directories.
