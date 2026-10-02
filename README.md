# Outlaw Forge

Outlaw Forge is a web-based 3D-print preparation workbench for inspecting, repairing, transforming, and arranging mesh models before they reach a slicer.

It combines a FastAPI geometry service with a Next.js/Three.js CAD-style workbench. Projects, printer profiles, model revisions, printability checks, and operation history are kept together so a model can move from import to export without losing context.

> **Status:** active development. The core project, mesh, printer, viewport, printability, slicing, repair, arrangement, and studio workflows are implemented and covered by automated checks. Direct G-code generation and desktop packaging are still planned.

## What it does

- Create and persist print projects in SQLite.
- Import and inspect mesh models in an interactive Three.js viewport.
- Work in millimetres with explicit printer build-volume checks.
- Scale, orient, lay models on a face, slice with a cutting plane, heal meshes, hollow models, and generate connectors.
- Arrange multiple models on a build plate and export an OrcaSlicer-compatible 3MF package.
- Review mesh dimensions, surface area, volume, watertightness, overhangs, and printability findings.
- Use MaskSmith for wearable mask sizing and FigureForge for figure stability and display-base workflows.
- Keep AI ideas advisory: deterministic geometry and fit checks do not depend on model inference.

## Repository layout

```text
apps/
├── api/                 FastAPI service, SQLite persistence, and mesh operations
└── web/                 Next.js workbench and Three.js viewport
packages/
├── shared/              Shared TypeScript API and viewport contracts
└── three-tools/         Geometry loaders, transforms, materials, and camera tools
docs/                    Architecture, pipeline, viewport, printer, QA, and roadmap docs
scripts/                 PowerShell development and verification helpers
tests/                   Black-box health and critical-workflow checks
```

Runtime data is written below `data/` and is intentionally ignored by Git. Source uploads, working revisions, exports, and the local SQLite database stay on the machine running the API.

## Quick start

### Prerequisites

- Node.js 20 or newer and npm
- Python 3.11 or newer
- A Python environment with `apps/api/requirements.txt` installed

### Install

```powershell
npm install
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r apps/api/requirements.txt
```

Copy `.env.example` to `.env` if you need to change ports, CORS, storage, or database settings.

### Run the application

Start the API from the repository root:

```powershell
python -m uvicorn app.main:app --app-dir apps/api --host 127.0.0.1 --port 8000 --reload
```

In a second terminal, start the web workbench:

```powershell
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). The API documentation is available at [http://127.0.0.1:8000/api/v1/docs](http://127.0.0.1:8000/api/v1/docs).

For a one-command PowerShell startup, use `npm run dev:all`.

## Verification

Run checks from the repository root:

```powershell
# Backend tests
npm run test:backend

# Frontend lint and production build
npm run lint
npm run build

# Black-box health check against a running API
npm run test:smoke

# Full staged verification (backend, frontend build, and smoke test)
powershell -ExecutionPolicy Bypass -File scripts/test.ps1
```

The smoke and critical-workflow scripts require the API to be running. When diagnosing a failure, run backend tests, frontend checks, and live HTTP checks separately so one timeout does not hide the useful result.

## Documentation

- [Documentation index](docs/README.md)
- [Getting started](docs/getting-started.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Mesh pipeline](docs/MESH_PIPELINE.md)
- [Viewport specification](docs/VIEWPORT_SPEC.md)
- [Printer profiles](docs/PRINTER_PROFILES.md)
- [QA and verification](docs/QA_ACCEPTANCE.md)
- [Roadmap](docs/ROADMAP.md)
- [Contributing](CONTRIBUTING.md)

## Project principles

1. **Deterministic geometry first.** Dimensions, transforms, fit checks, and mesh metrics are calculated by explicit geometry code.
2. **Millimetres everywhere.** API, persistence, viewport contracts, and printability checks use millimetres unless a document says otherwise.
3. **Source meshes are preserved.** Transformations produce working revisions; the original upload is not silently overwritten.
4. **User-visible state matters.** The workbench reports backend health, save status, active printer, and operation results.
5. **AI stays advisory.** A suggestion never changes a model without an explicit user action.

## License

Outlaw Forge is released under the [MIT License](LICENSE).
