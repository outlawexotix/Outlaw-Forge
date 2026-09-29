# Outlaw Forge - System Architecture & Engineering Rules

## 1. Executive Summary

Outlaw Forge is a desktop-grade engineering workbench for 3D model preparation, deterministic mesh manipulation, printability verification, and printer profile management.

---

## 2. Monorepo Directory Architecture

The repository adheres to a modular multi-tier structure:

```
outlaw-forge/
├── apps/
│   ├── web/                    # Next.js 14+ / React 18+ App Router Frontend
│   └── api/                    # FastAPI (Python 3.11+) Backend REST Service
├── packages/
│   ├── ui/                     # Reusable CAD UI components & design system
│   ├── shared/                 # Shared TypeScript interfaces, schemas & enums
│   └── three-tools/            # 3D Math, R3F Viewport controls & shader tools
├── data/                       # Isolated storage trees (never exposed directly)
│   ├── original/               # Immutable source mesh uploads (STL, OBJ, GLB)
│   ├── working/                # Transformed working meshes & cached revisions
│   └── exports/                # Exported production artifacts
├── docs/                       # Specifications & Engineering Documentation
│   ├── ARCHITECTURE.md         # Monorepo architecture & engineering principles
│   ├── ROADMAP.md              # Milestone 1 phased implementation plan
│   ├── MESH_PIPELINE.md        # Computational geometry & unit standards
│   ├── PRINTER_PROFILES.md     # Printer build volumes & kinematics specs
│   └── AI_ARCHITECTURE.md      # Advisory AI interfaces & boundary rules
├── scripts/                    # Dev orchestration & automation scripts
└── tests/                      # End-to-end (Playwright) & smoke test suites
```

---

## 3. Core Architectural Rules

### 3.1 Deterministic Spatial Units & Coordinate Space
- **Canonical Distance Unit**: Millimeters ($mm$) across all internal representations, APIs, and persisted fields.
- **Coordinate Systems**:
  - **Slicer & Print Bed Space**: $Z\text{-up}$, right-handed Cartesian ($X\text{-right}, Y\text{-back}, Z\text{-up}$).
  - **Three.js Viewport Scene**: $Y\text{-up}$, right-handed Cartesian.
  - Transformation between Slicer Space and Viewport Space is managed via non-destructive affine rotations ($R_x(-\pi/2)$).
- **Scale Factor**: $1.0\text{ Three.js World Unit} = 1.0\text{ mm}$ strictly.

### 3.2 Immutability of Source Assets
- Uploaded original files in `data/original/` are **read-only and immutable**.
- Scaling, rotation, or transformation operations write derivative working geometries to `data/working/` with full provenance logs.
- Exported geometries are written cleanly to `data/exports/`.

### 3.3 Storage Security & Input Sanitization
- File uploads are validated via file extension, MIME type, and magic bytes.
- Filenames are sanitized (UUID-based storage keys) to prevent path traversal (`../`).
- Internal filesystem paths are never returned over API responses.

### 3.4 Decoupled Persistence
- Persistence is implemented through an asynchronous repository pattern (`ProjectRepository`, `PrinterRepository`, `OperationRepository`) backed by SQLite (`aiosqlite`) with clean future migration paths to PostgreSQL.

### 3.5 Clear User State Communication
- Controls for deferred or un-implemented features are explicitly labeled **"Coming Soon"** or visually disabled.
- Save status (**Saved** vs **Unsaved Changes**) is prominently visible in the UI header at all times.
