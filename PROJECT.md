# Project: Outlaw Forge Phase 10 — Parametric 3D Infill & Internal Lattice Generator

## Architecture
Outlaw Forge is a 3D-print preparation workbench combining a FastAPI geometry engine with a Next.js / Three.js CAD-style workbench. Phase 10 introduces procedural 3D infill lattice generation, internal cavity/rib reinforcement with drainage channels, real-time GPU cross-section cutaway visualization, and OrcaSlicer 3MF / single-mesh export integration.

```text
               ┌────────────────────────────────────────────────────────┐
               │         Next.js / Three.js Workbench (apps/web)        │
               │  - InfillStudio.tsx (pattern, density, scrubbers)      │
               │  - Inspector.tsx ('infill' tab, dense CAD controls)    │
               │  - ViewportContainer.tsx & ModelRenderer.tsx           │
               └───────────▲────────────────────────────────▲───────────┘
                           │ API Client                     │ 3D Rendering
                           │ (api-client.ts)                │ (localClipping)
                           ▼                                ▼
               ┌───────────────────────────┐    ┌───────────────────────────┐
               │    Shared Contracts       │    │  Three.js Tools           │
               │   (packages/shared)       │    │ (packages/three-tools)    │
               │  - InfillGeneratePayload  │    │  - infillCrossSection-    │
               │  - InfillGenerateResult   │    │    Material.ts            │
               │  - RibReinforcePayload    │    │  - ThreeMFLoader support  │
               │  - OrcaSlicer 3MF types   │    │  - Stencil Cap Shaders    │
               └───────────▲───────────────┘    └───────────────────────────┘
                           │ Mirrors 1:1
                           ▼
               ┌────────────────────────────────────────────────────────┐
               │          FastAPI Geometry Engine (apps/api)            │
               │  - InfillService (manifold3d TPMS, extrusions, ribs)   │
               │  - MeshService (export_project_3mf OrcaSlicer tags)    │
               │  - Endpoints (/models/{id}/infill, /ribs, /export)     │
               └────────────────────────────────────────────────────────┘
```

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Gyroid TPMS Infill | Triply periodic minimal surface infill with isotropic strength via SDF level set | M1 | ORIGINAL_REQUEST R1 |
| 2 | Honeycomb Lattice | High-strength vertical compressive hexagonal cell lattice | M1 | ORIGINAL_REQUEST R1 |
| 3 | Rectilinear & Cubic Infill | High-speed orthogonal 2D grid and 3D cubic lattices | M1 | ORIGINAL_REQUEST R1 |
| 4 | Parametric Density & Spacing | Configurable infill density (5% to 100%) and unit cell spacing in mm | M1 | ORIGINAL_REQUEST R1 |
| 5 | Internal Structural Ribbing | Automatic structural rib generation along thin hollow walls | M2 | ORIGINAL_REQUEST R2 |
| 6 | Continuous Drainage Channels | Internal drainage channels preventing trapped resin or air pockets | M2 | ORIGINAL_REQUEST R2 |
| 7 | Real-Time Cross-Section Shader | Three.js cut-away shader rendering internal lattice & shell thickness in real time | M3 | ORIGINAL_REQUEST R3 |
| 8 | Workbench Inspector UI | Dynamic clipping plane controls with density scrubbers in Workbench Inspector | M3 | ORIGINAL_REQUEST R3 |
| 9 | Single-Mesh Infill Embedding | Embed internal infill directly into derived export meshes (STL, OBJ, GLB) | M4 | ORIGINAL_REQUEST R4 |
| 10 | OrcaSlicer 3MF Metadata | Attach per-object infill tags and slice_info.config to 3MF archives | M4 | ORIGINAL_REQUEST R4 |
| 11 | 3MF Viewport Loader | Re-import and inspect exported 3MF archives in Three.js viewport | M4 | ORIGINAL_REQUEST R4 / Explorer 3 |
| 12 | E2E Verification & Auditing | 100% backend pytest passing, Next.js 0 errors, forensic integrity audit | M5 | Acceptance Criteria |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Parametric 3D Infill Engine | InfillService, manifold3d lattice generation, Pydantic & TS schemas, /infill endpoints | none | PLANNED |
| M2 | Rib Reinforcement & Drainage | Structural ribs along hollow walls, drainage conduits, /ribs endpoints | M1 | PLANNED |
| M3 | Cross-Section Shader & UI | Viewport clipping shader, local clipping enabled, InfillStudio, Inspector tab | M1 | PLANNED |
| M4 | Export & OrcaSlicer 3MF | 3MF OrcaSlicer tags, single-mesh embed_infill, 3MF Three.js loader | M1, M2 | PLANNED |
| M5 | E2E Suite, Dual Track & Audit | Unit & integration tests, E2E test runner, lint/build verification, forensic audit | M1, M2, M3, M4 | PLANNED |

## Interface Contracts

### Backend Pydantic Schemas (`apps/api/app/models/mesh.py`)
```python
class InfillPattern(str, Enum):
    GYROID = "gyroid"
    HONEYCOMB = "honeycomb"
    RECTILINEAR = "rectilinear"
    CUBIC = "cubic"

class InfillGeneratePayload(BaseModel):
    pattern: InfillPattern = InfillPattern.GYROID
    density: float = Field(default=0.20, ge=0.05, le=1.0)
    unit_cell_size_mm: float = Field(default=10.0, gt=0.0)
    wall_thickness_mm: float = Field(default=2.0, gt=0.0)
    hollow_first: bool = True

class InfillGenerateResult(BaseModel):
    success: bool
    model_id: str
    infill_pattern: InfillPattern
    density: float
    unit_cell_size_mm: float
    wall_thickness_mm: float
    volume_reduction_percent: float
    vertex_count: int
    triangle_count: int
    bounding_box_mm: Dict[str, float]
    mesh_path: str

class RibReinforcePayload(BaseModel):
    min_wall_thickness_mm: float = Field(default=2.0, gt=0.0)
    rib_spacing_mm: float = Field(default=15.0, gt=0.0)
    rib_thickness_mm: float = Field(default=1.5, gt=0.0)
    drainage_channel_diameter_mm: float = Field(default=3.0, gt=0.0)
    drainage_axis: str = Field(default="z")

class RibReinforceResult(BaseModel):
    success: bool
    model_id: str
    ribs_generated: int
    drainage_channels_generated: int
    vertex_count: int
    triangle_count: int
    mesh_path: str
```

### TypeScript Contracts (`packages/shared/types/api.ts`)
Mirrors the Pydantic schemas above 1:1, extending `OperationType` with `'INFILL_GENERATE'` and `'RIB_REINFORCE'`.

### Viewport Shader Uniforms (`packages/three-tools/src/materials/orcaCrossSectionMaterial.ts`)
```glsl
uniform int uInfillPattern; // 0=Gyroid, 1=Honeycomb, 2=Rectilinear, 3=Cubic
uniform float uInfillDensity; // 0.05 to 1.0
uniform float uCellSpacing; // mm
uniform float uShellThickness; // mm
uniform bool uShowLattice;
uniform vec3 uLatticeColor;
uniform vec3 uPlanePoint;
uniform vec3 uPlaneNormal;
```

## Code Layout
- `apps/api/app/models/mesh.py` & `apps/api/app/models/project.py`: Infill, Rib, Export schemas.
- `apps/api/app/services/infill_service.py`: Procedural infill & ribbing geometry generation via `manifold3d`.
- `apps/api/app/services/mesh_service.py`: 3MF OrcaSlicer metadata injection & single-mesh infill embedding.
- `apps/api/app/api/v1/endpoints/models.py`: Dual-routed infill, rib, and export endpoints.
- `apps/api/tests/test_infill_service.py`: Unit and integration pytest suite.
- `packages/shared/types/api.ts`: Shared TypeScript API models.
- `packages/three-tools/src/materials/orcaCrossSectionMaterial.ts`: Cross-section cutaway shader with procedural infill.
- `packages/three-tools/src/loaders/geometryLoader.ts`: 3MF format loading via `ThreeMFLoader`.
- `apps/web/src/components/studios/InfillStudio.tsx`: Infill Studio UI controls.
- `apps/web/src/components/layout/Inspector.tsx`: Inspector tab wiring.
- `apps/web/src/components/viewport/ViewportContainer.tsx` & `ModelRenderer.tsx`: Local clipping and cross-section material binding.
- `apps/web/src/lib/api-client.ts`: Frontend API client calls.
