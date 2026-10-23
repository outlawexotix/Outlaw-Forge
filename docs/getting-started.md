# Getting started

Outlaw Forge's main application is the Tauri desktop workbench. The same Next.js interface can run in a browser during development. A separate Qt Quick 3D viewport is available as an experimental native foundation and is built independently.

## Requirements

- Node.js 20 or newer and npm
- Python 3.11 or newer
- PowerShell on Windows for repository desktop scripts
- Rust and the Tauri CLI for the Tauri shell or installer
- PyInstaller for a bundled Python sidecar
- Qt 6.6+, CMake 3.21+, and a C++20 compiler only for `apps/native/`

## Install dependencies

From the repository root:

```powershell
npm install
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r apps/api/requirements.txt
```

Copy `.env.example` to `.env` only when local storage, database, port, or CORS overrides are needed. Defaults write project data and generated assets below ignored `data/` paths.

## Run the main desktop workbench

Check the desktop setup without starting processes:

```powershell
npm run desktop:dev -- -DryRun
```

Start the desktop development workflow:

```powershell
npm run desktop:dev
```

The launcher chooses an available loopback port, starts the FastAPI sidecar, waits for its health check, and launches the available workbench runtime. If the native Tauri toolchain is unavailable, it can fall back to the browser workbench.

## Run browser development

Start both services through the repository script:

```powershell
npm run dev:all
```

Or start the services in separate terminals. API:

```powershell
python -m uvicorn app.main:app --app-dir apps/api --host 127.0.0.1 --port 8000 --reload
```

Workbench:

```powershell
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). API docs are at [http://127.0.0.1:8000/api/v1/docs](http://127.0.0.1:8000/api/v1/docs).

## Build the standalone native viewport

The Qt app is not packaged into Tauri. Configure it in its own build directory, using a Qt kit installed on the machine:

```powershell
cmake -S apps/native -B build/native -DCMAKE_PREFIX_PATH="C:/Qt/6.8.0/msvc2022_64"
cmake --build build/native --config Release
./build/native/outlaw-forge-native.exe
```

The experimental Qt app opens supported STL/OBJ and limited 3MF files locally. Import, repair, auto-orient, planar cut, analysis, and STL export run in the native process; it has no API URL setting or FastAPI dependency. Read [the native application guide](../apps/native/README.md) and [migration boundary](./NATIVE_VIEWPORT_MIGRATION.md) for details. The separate Tauri workbench continues to use its supervised FastAPI sidecar.

## Build the Tauri package

Inspect the packaging plan:

```powershell
npm run desktop:build -- -DryRun
```

Run the production pipeline:

```powershell
npm run desktop:build
```

The pipeline creates a static frontend export, bundles the FastAPI sidecar when PyInstaller is available, and runs the Tauri package build when Rust is available. This does not package the separate Qt application.

## First preparation workflow

1. Create or select a project.
2. Choose a printer profile with the matching build dimensions.
3. Import a mesh in a format supported by the selected workflow.
4. Review dimensions, mesh health, overhangs, thin walls, watertightness, printer fit, and material estimate.
5. Repair, transform, orient, hollow, slice, reinforce, or arrange the model as needed.
6. Review the operation result and provenance, then export STL or an OrcaSlicer-oriented 3MF package.

Outlaw Forge prepares meshes for external slicers. It does not generate G-code or replace a slicer engine.

## Verify the setup

```powershell
npm run test:backend
npm run lint
npm run build
python tests/verify_m5_e2e_full.py
```

With FastAPI running:

```powershell
python tests/verify_health.py --base-url http://127.0.0.1:8000
python tests/test_critical_workflow.py --base-url http://127.0.0.1:8000
```

Native build and CTest instructions are in [apps/native/README.md](../apps/native/README.md).
