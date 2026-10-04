# Outlaw Forge

Outlaw Forge is a local-first desktop workbench for preparing 3D models for printing. It brings mesh inspection, repair, transformation, print-readiness analysis, printer-fit validation, arrangement, and export into one engineering-focused application.

The desktop architecture combines a Tauri 2 shell, a static Next.js and Three.js workbench, and a supervised FastAPI geometry sidecar. Projects and printer profiles are stored locally in SQLite. Imported source meshes remain unchanged while repairs, transforms, slices, and exports create derived revisions.

> **Project status:** active development. The desktop shell, local geometry service, CAD viewport, print-readiness cockpit, mesh workflows, packaging automation, and end-to-end desktop verification harness are implemented. Direct G-code generation, signed public installers, and production auto-update distribution are not yet release features.

## Why Outlaw Forge

Most mesh utilities expose isolated operations. Outlaw Forge keeps the complete preparation context together:

- the source model and every derived revision
- the active printer and its build volume
- dimensions, topology, overhang, thin-wall, and material diagnostics
- deterministic repair, transform, slicing, infill, and reinforcement operations
- a visible operation history from import through export

The result is a print-preparation cockpit rather than another file converter.

## Implemented capabilities

### Print-readiness cockpit

- Live overhang, thin-wall, watertightness, build-volume, and material-cost checks
- Printer-aware dimensions and fit status in millimetres
- One-click repair and orientation preparation
- Direct STL export plus access to the full geometry inspector
- Five-stage workflow rail from inspection to export

### CAD and mesh preparation

- STL, OBJ, GLB, GLTF, and 3MF import paths
- Interactive Three.js build plate, camera views, selection, transforms, wireframe, and inspection modes
- Scale, rotate, translate, lay-on-face, auto-orient, and auto-arrange operations
- Mesh healing, hole filling, normal correction, vertex welding, hollowing, and planar slicing
- Connector pins, parametric infill, rib reinforcement, and derived mesh revisions
- OrcaSlicer-oriented 3MF export and project packaging

### Local project system

- SQLite-backed projects, printer profiles, working model revisions, and operation history
- Immutable original uploads with separate working and export storage
- MaskSmith workflows for wearable mask fit
- FigureForge workflows for center of mass, plinths, and mounting keys

### Standalone desktop runtime

- Tauri 2 native shell and static Next.js webview
- PyInstaller-ready FastAPI sidecar with dynamic loopback port allocation
- Native menus, keyboard accelerators, file dialogs, and STL/OBJ/3MF associations
- Windows Job Object supervision so the geometry sidecar terminates with the app
- Dry-run development and production packaging commands
- Master verification battery covering backend, static export, lifecycle, and automation layers

## Architecture

```text
Tauri 2 desktop shell
├── Native window, menus, dialogs, file associations, and process lifecycle
├── Next.js static export
│   └── React 18 + Three.js CAD and print-readiness workbench
└── FastAPI sidecar on a dynamic 127.0.0.1 port
    ├── Trimesh, PyMeshLab, and NumPy geometry services
    ├── SQLite project and operation persistence
    └── Local uploads, working revisions, and exports
```

The desktop shell injects the sidecar URL into the webview at startup. Geometry stays deterministic and local. AI integrations, when added, remain advisory and cannot silently mutate a model or project.

## Repository layout

```text
apps/
├── api/                 FastAPI geometry engine, SQLite persistence, and PyInstaller spec
└── web/                 Next.js workbench and Three.js viewport
packages/
├── shared/              Shared TypeScript API and viewport contracts
└── three-tools/         Geometry loaders, transforms, materials, and camera tools
src-tauri/               Tauri 2 desktop shell, permissions, menus, and sidecar supervisor
docs/                    Architecture, pipeline, desktop, QA, and roadmap documentation
scripts/                 Web, API, desktop development, build, and verification helpers
tests/                   Black-box, adversarial, lifecycle, and master E2E checks
```

Runtime data below `data/`, build outputs, sidecar binaries, and local design captures are ignored by Git.

## Quick start

### Requirements

- Node.js 20 or newer and npm
- Python 3.11 or newer
- PowerShell on Windows
- Rust and the Tauri CLI only when running or compiling the native shell
- PyInstaller only when producing a bundled sidecar executable

### Install

```powershell
npm install
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r apps/api/requirements.txt
```

Copy `.env.example` to `.env` only when you need to override local ports, CORS, storage, or database settings.

### Run the desktop development workflow

```powershell
npm run desktop:dev
```

The launcher allocates a local API port, starts the FastAPI sidecar, waits for health, and launches the available workbench runtime. To inspect prerequisites without launching processes:

```powershell
npm run desktop:dev -- -DryRun
```

### Run in browser development mode

```powershell
npm run dev:all
```

Then open [http://localhost:3000](http://localhost:3000). API documentation is available at [http://127.0.0.1:8000/api/v1/docs](http://127.0.0.1:8000/api/v1/docs) when the default API port is active.

### Build the standalone desktop package

```powershell
npm run desktop:build
```

This pipeline creates the static frontend export, bundles the Python sidecar when PyInstaller is available, and builds the Tauri package when Rust is available. Inspect the plan without writing build outputs:

```powershell
npm run desktop:build -- -DryRun
```

## Verification

```powershell
# Backend geometry and API suite
npm run test:backend

# Frontend quality gates
npm run lint
npm run build

# Desktop architecture, static export, lifecycle, and automation battery
python tests/verify_m5_e2e_full.py

# Live API smoke check when the API is running
npm run test:smoke
```

The checks are intentionally layered. A static build, backend suite, desktop lifecycle test, and live HTTP probe prove different parts of the product.

## Engineering principles

1. **Millimetres are canonical.** Dimensions, transforms, printer volumes, and mesh coordinates use millimetres.
2. **Source assets are immutable.** Original uploads are never silently overwritten.
3. **Geometry is deterministic.** Repairs, transforms, slicing, and analysis do not depend on model inference.
4. **Contracts stay synchronized.** FastAPI schemas and shared TypeScript types move together.
5. **Desktop means local ownership.** Project data and geometry processing stay on the user's machine by default.
6. **Verification is part of the feature.** A change is not complete until its relevant backend, frontend, and desktop layers pass.

## Documentation

- [Documentation index](docs/README.md)
- [Getting started](docs/getting-started.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Desktop workflow](docs/skills/desktop-app-workflow.md)
- [Mesh pipeline](docs/MESH_PIPELINE.md)
- [Viewport specification](docs/VIEWPORT_SPEC.md)
- [Printer profiles](docs/PRINTER_PROFILES.md)
- [QA and verification](docs/QA_ACCEPTANCE.md)
- [Roadmap](docs/ROADMAP.md)
- [Contributing](CONTRIBUTING.md)

## License

Outlaw Forge is released under the [MIT License](LICENSE).
