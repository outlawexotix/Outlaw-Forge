# Outlaw Forge - Milestone 1 Roadmap

## Milestone 1: Functional Model-to-Printability Vertical Slice

**Core Workflow Goal**:
```
CREATE PROJECT  
→ IMPORT MODEL  
→ VIEW MODEL  
→ ANALYZE DIMENSIONS  
→ SCALE MODEL  
→ SELECT PRINTER  
→ CHECK BUILD VOLUME  
→ SAVE AND RELOAD  
→ EXPORT MODEL
```

---

## Phase Breakdown

### Phase 0: Repository & Environment Assessment (Current)
- [x] Runtime validation (Node.js 24.18.1, Python 3.11.0, npm 11.16.0).
- [x] Baseline shell audit and risk inventory.
- [x] Architectural documentation (`ARCHITECTURE.md`, `ROADMAP.md`, `AI_ARCHITECTURE.md`).
- [x] Milestone 1 phased implementation plan.

### Phase 1: Modular Structure & Foundation Alignment
- [x] Monorepo workspace boundaries: `apps/web` (or `frontend`), `apps/api` (or `backend`), `shared/`, `data/`.
- [x] Shared TypeScript contracts and schema definitions (`shared/types/api.ts`, `shared/types/viewport.ts`).
- [x] Standard scripts for install, test, dev, lint, format, and build.
- [x] Dark CAD workbench layout with disabled/“Coming Soon” badges on deferred controls.

### Phase 2: Persistence, Project Model & Project CRUD
- [ ] SQLite schema & asynchronous repository abstraction (`aiosqlite` / SQLAlchemy core).
- [ ] Entity models: `projects`, `source_files`, `working_models`, `printer_profiles`, `operations`, `notes`.
- [ ] Supported project types: Character, Collectible Figure, Mask, Bust, Statue, Prop, Plaque, Mechanical Part, Decorative Object, Other.
- [ ] Endpoints: `GET /projects`, `POST /projects`, `GET /projects/{id}`, `PATCH /projects/{id}`, `DELETE /projects/{id}`.
- [ ] UI project management: Project creation modal, project metadata inspector, save/unsaved indicator.

### Phase 3: Secure Model Upload & Isolated File Storage
- [ ] Isolated storage trees: `data/original/`, `data/working/`, `data/exports/`.
- [ ] Upload security: MIME/magic bytes validation, filename sanitization, path-traversal prevention, 100MB file limits.
- [ ] Supported formats: STL (binary/ASCII), OBJ, GLB, GLTF.
- [ ] Endpoint: `POST /projects/{id}/models/import`.
- [ ] Immutability invariant: Original uploaded files are never overwritten or mutated.

### Phase 4: Mesh Loading, Analysis & Deterministic Geometry Services
- [ ] Geometry pipeline (`trimesh`, `numpy`, `Open3D`).
- [ ] Core routines: `load_mesh()`, `analyze_mesh()`, `get_dimensions()`, `get_bounding_box()`, `calculate_surface_area()`, `calculate_volume()`, `check_watertight()`.
- [ ] Strict millimeter ($mm$) unit provenance.
- [ ] Endpoints: `GET /projects/{id}/models/{model_id}`, `POST /projects/{id}/models/{model_id}/analyze`.

### Phase 5: Interactive 3D Viewport & Scene Integration
- [ ] Three.js + React Three Fiber + Drei rendering canvas.
- [ ] Camera tools: Orbit, pan, zoom, reset, frame model ($F$), CAD preset views (Top, Front, Right, Isometric).
- [ ] Visual aids: Virtual print bed grid, orientation gizmo, dimensional bounding box wireframe.
- [ ] Display normalization without mutating working or source coordinates.

### Phase 6: Scaling, Working Models & Model Export
- [ ] Deterministic scaling engine: Uniform scale %, target height, width, depth (mm).
- [ ] Proportional aspect-ratio lock with explicit override toggle.
- [ ] Working model revision tracking in `data/working/`.
- [ ] Export engine (`STL`, `OBJ`, `GLB`) storing output in `data/exports/`.
- [ ] Endpoints: `POST /projects/{id}/models/{model_id}/scale`, `POST /projects/{id}/models/{model_id}/export`.

### Phase 7: Printer Profiles & Printability Analysis
- [ ] Seeded profiles: **Creality Ender-3** ($220 \times 220 \times 250\text{ mm}$), **Creality Ender-3 S1** ($220 \times 220 \times 270\text{ mm}$).
- [ ] Profile repository and endpoints: `GET /printers`, `POST /printers`.
- [ ] Deterministic build volume verification: Dimension-by-dimension check ($X, Y, Z$) with exact exceeded millimeters.
- [ ] Printability classification: `INFO`, `WARNING`, `ERROR`.

### Phase 8: Complete UI Workflow & Project State Restoration
- [ ] Full top-to-bottom integration of all 9 workflow steps.
- [ ] Project reload & state reconstruction across browser/server restarts.
- [ ] Primary workbench layout: Top bar, Left tool rail, Center 3D viewport, Right multi-tab inspector, Bottom status bar.

### Phase 9: Operation History & Undo/Redo Foundation
- [ ] Structured operation log: `IMPORT`, `SCALE`, `ROTATE`, `EXPORT`.
- [ ] Operation parameters and artifact provenance for future Undo/Redo compatibility.
- [ ] UI history audit feed.

### Phase 10: Automated Testing & Critical End-to-End Workflow
- [ ] Automated pytest unit & API tests (100% endpoint coverage).
- [ ] Frontend React Testing Library tests for forms, inspectors, and status indicators.
- [ ] Playwright E2E test verifying the complete 12-step critical user journey from project creation to export.

### Phase 11: Documentation, Hardening & Milestone Release
- [ ] Complete documentation suite (`README.md`, `ARCHITECTURE.md`, `MESH_PIPELINE.md`, `PRINTER_PROFILES.md`).
- [ ] Security audit: Path traversal, input validation, error masking, zero source-file mutations.
- [ ] Final verification against all Milestone 1 acceptance criteria.

---

## Deferred Backlog (Post-Milestone 1)

1. **Advanced Mesh Operations**: Automated mesh repair, hollowing, model splitting, connector generation, thin-wall analysis.
2. **Specialized Workflows**: MASKSMITH (wearable clearance, strap/magnet slots), FIGURE FORGE (bases, balance analysis).
3. **AI Generation & Diagnostics**: Vision analysis, orientation suggestions, repair guidance (provider interfaces specified in `docs/AI_ARCHITECTURE.md`).
4. **Desktop Packaging & Slicing**: Tauri desktop build, OrcaSlicer bridge, direct GCODE generation.
