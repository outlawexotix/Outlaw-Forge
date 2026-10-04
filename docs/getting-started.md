# Getting started

Outlaw Forge can run as a standalone Tauri desktop application or as a local browser workbench. Both modes use the same FastAPI geometry engine and local project data.

## Requirements

- Node.js 20+ and npm
- Python 3.11+
- PowerShell on Windows
- Rust and a Tauri CLI for the native development shell or installer build
- PyInstaller for a bundled Python sidecar

## Install dependencies

From the repository root:

```powershell
npm install
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r apps/api/requirements.txt
```

Copy `.env.example` to `.env` when local storage, database, port, or CORS overrides are required. Defaults write project data and generated assets below `data/`.

## Desktop development

Validate the local desktop toolchain:

```powershell
npm run desktop:dev -- -DryRun
```

Launch the desktop development workflow:

```powershell
npm run desktop:dev
```

The launcher allocates an available loopback port, starts the FastAPI sidecar, waits for `/health`, and launches the available frontend runtime. When a native Tauri toolchain is not available, the same command can fall back to the browser workbench.

## Browser development

Start both local services:

```powershell
npm run dev:all
```

Or start them separately.

API:

```powershell
python -m uvicorn app.main:app --app-dir apps/api --host 127.0.0.1 --port 8000 --reload
```

Workbench:

```powershell
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). API documentation is available at [http://127.0.0.1:8000/api/v1/docs](http://127.0.0.1:8000/api/v1/docs).

## Build a standalone package

Inspect the packaging plan:

```powershell
npm run desktop:build -- -DryRun
```

Run the production pipeline:

```powershell
npm run desktop:build
```

The pipeline builds the Next.js static export, bundles the FastAPI sidecar when PyInstaller is installed, and invokes the Tauri package build when Rust is available.

## First preparation workflow

1. Create or select a project.
2. Choose a printer profile with the correct build dimensions.
3. Import an STL, OBJ, GLB, GLTF, or 3MF model.
4. Review overhangs, thin walls, watertightness, build-volume fit, and material estimate.
5. Repair, transform, orient, hollow, slice, reinforce, or arrange the model as required.
6. Use Prepare for Print to repair and optimize orientation.
7. Export an STL or OrcaSlicer-oriented 3MF package.

## Verify the setup

```powershell
npm run test:backend
npm run lint
npm run build
python tests/verify_m5_e2e_full.py
```

With the API running:

```powershell
python tests/verify_health.py --base-url http://127.0.0.1:8000
python tests/test_critical_workflow.py --base-url http://127.0.0.1:8000
```
