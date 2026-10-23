# Outlaw Forge

Outlaw Forge is a local-first workbench for preparing 3D mesh models for printing. The main desktop application uses a Tauri 2 shell, a Next.js and Three.js workbench, and a locally supervised FastAPI geometry service. An independent Qt Quick 3D application is also being developed as a native viewport foundation.

The software focuses on deterministic mesh preparation and printer-aware checks. Original uploads are retained as immutable sources; operations create working revisions, exports, and project history. Outlaw Forge is active development software, not a slicer engine: it prepares meshes and exports files for use in external slicers.

## Current state

| Application | Status | What it does today |
| --- | --- | --- |
| Tauri desktop workbench | Main desktop workflow implemented; installer and release checks remain | Project and printer-profile management, mesh preparation, print-readiness checks, viewport inspection, and export through a local API sidecar |
| Browser workbench | Development workflow implemented | Runs the same Next.js UI and connects to the local FastAPI service |
| Qt native viewport | Separate experimental application | Imports STL/OBJ and limited 3MF, displays and transforms scene instances, provides inspection and local repair, and routes STL/OBJ planar cuts through the geometry service |

The Qt application is not part of the Tauri package and does not replace the main workbench. Its service-backed slice command requires a reachable FastAPI service. It reports the service's watertight result for each half; requesting capped faces does not guarantee that every result is watertight. See [Native viewport migration](docs/NATIVE_VIEWPORT_MIGRATION.md).

## Main workbench capabilities

- Import STL, OBJ, GLB, GLTF, and 3MF through the supported project workflows.
- Inspect dimensions, mesh health, overhangs, thin walls, watertightness, printer fit, and estimated material cost.
- Follow the five-stage Inspect, Repair, Verify Readiness, Prepare for Print, and Export workflow. The readiness panel shows overhang, thin-wall, watertightness, printer-volume, and material-estimate results for the selected model.
- Transform, orient, arrange, repair, hollow, and slice meshes through deterministic API operations.
- Create connector pins, infill, and rib reinforcement where supported by the geometry service.
- Manage SQLite-backed projects, source files, working model revisions, printer profiles, and operation history.
- Export STL and OrcaSlicer-oriented 3MF project packages.
- Use MaskSmith and FigureForge project workflows.
- Run the Tauri desktop with a supervised loopback FastAPI sidecar, dynamic local port allocation, native menus, dialogs, and file associations.

The separate Qt viewport has its own format limits and feature boundary; the main workbench's features should not be assumed to exist there. Product behavior and migration status are documented under [`docs/`](docs/README.md).

## Architecture

```text
Main Tauri desktop
├── Tauri 2 shell: menus, dialogs, file associations, sidecar lifecycle
├── Static Next.js workbench: React 19 and Three.js / React Three Fiber
└── FastAPI geometry sidecar on loopback
    ├── deterministic mesh operations and project APIs
    ├── SQLite project and operation persistence
    └── immutable source uploads, working revisions, and exports

Separate native viewport foundation
└── Qt Quick 3D application with Z-up, millimetre scene coordinates
    └── Qt Network client for existing project import, slice, and file routes
```

The web viewport uses its renderer coordinate conversion at the scene boundary. The native viewport keeps a right-handed Z-up scene. Both use millimetres for model and printer dimensions. The local API remains the authority for persisted project operations; the Qt slice command reuses its existing API contracts.

## Repository layout

```text
apps/api/          FastAPI service, SQLite repositories, and mesh operations
apps/web/          Next.js workbench and Three.js viewport
apps/native/       Separate Qt Quick 3D viewport foundation
packages/shared/   Shared TypeScript API and viewport contracts
packages/three-tools/ Three.js geometry loaders, transforms, and viewport tools
src-tauri/         Tauri shell, capabilities, menus, and sidecar supervisor
docs/              Product, architecture, geometry, desktop, QA, and migration docs
scripts/           Development, packaging, and verification helpers
tests/             API smoke, critical workflow, and desktop acceptance checks
```

Runtime projects and mesh artifacts live under ignored `data/` paths. Do not commit user uploads, generated working meshes, exports, local databases, build directories, or sidecar binaries.

## Requirements

- Node.js 20 or newer and npm
- Python 3.11 or newer
- PowerShell on Windows for the desktop scripts
- Rust and the Tauri CLI for the Tauri shell and package
- PyInstaller for a bundled Python sidecar
- Qt 6.6+, CMake 3.21+, and a C++20 compiler for the separate native viewport

## Install and run

Install the JavaScript and Python dependencies:

```powershell
npm install
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r apps/api/requirements.txt
```

Run the main desktop development workflow, which starts the local API and available workbench runtime:

```powershell
npm run desktop:dev
```

For browser development, start the API and web UI separately or use the repository orchestrator:

```powershell
npm run dev:all
```

Open [http://localhost:3000](http://localhost:3000). The default API documentation URL is [http://127.0.0.1:8000/api/v1/docs](http://127.0.0.1:8000/api/v1/docs).

To configure and build the separate Qt application, see [apps/native/README.md](apps/native/README.md). Service-backed native slicing defaults to `http://127.0.0.1:8000`; set `OUTLAW_FORGE_API_URL` to a different API origin when needed.

## Build and verify

```powershell
npm run build
npm run lint
npm run test:backend
python tests/verify_m5_e2e_full.py
npm run test:smoke
```

The health smoke test requires the API to be running. Desktop packaging can be checked without starting or writing build outputs:

```powershell
npm run desktop:dev -- -DryRun
npm run desktop:build -- -DryRun
```

Native viewport C++ and command tests are configured through CMake in `apps/native/`; see its README for build-specific commands.

## Engineering invariants

1. Model dimensions, printer volumes, and geometry API coordinates use millimetres.
2. Original uploaded assets are immutable; edits produce derived working or export files.
3. Geometry operations are deterministic and do not rely on AI inference.
4. FastAPI schemas and shared TypeScript contracts stay aligned.
5. The desktop API binds to loopback and owns local project data by default.
6. Documented completion claims distinguish local tests, live service checks, and release validation.

## Documentation

- [Documentation index](docs/README.md)
- [Getting started](docs/getting-started.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Desktop workflow](docs/skills/desktop-app-workflow.md)
- [Mesh pipeline](docs/MESH_PIPELINE.md)
- [Viewport specification](docs/VIEWPORT_SPEC.md)
- [Native viewport migration](docs/NATIVE_VIEWPORT_MIGRATION.md)
- [Printer profiles](docs/PRINTER_PROFILES.md)
- [QA and verification](docs/QA_ACCEPTANCE.md)
- [Roadmap](docs/ROADMAP.md)
- [Contributing](CONTRIBUTING.md)

## License

Outlaw Forge is released under the [MIT License](LICENSE).
