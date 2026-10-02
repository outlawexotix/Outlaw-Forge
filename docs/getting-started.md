# Getting started

Outlaw Forge is a two-service application: a Next.js workbench on port 3000 and a FastAPI geometry API on port 8000.

## Requirements

- Node.js 20+ and npm
- Python 3.11+
- PowerShell on Windows, or equivalent shell commands on another platform

## Install dependencies

From the repository root:

```powershell
npm install
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r apps/api/requirements.txt
```

Copy `.env.example` to `.env` when you need local overrides. The default configuration stores the SQLite database and generated assets below `data/`.

## Start the services

Terminal 1 — API:

```powershell
python -m uvicorn app.main:app --app-dir apps/api --host 127.0.0.1 --port 8000 --reload
```

Terminal 2 — web workbench:

```powershell
npm run dev
```

Then open [http://localhost:3000](http://localhost:3000). Use [the API docs](http://127.0.0.1:8000/api/v1/docs) to inspect available endpoints.

## First workflow

1. Create or select a project.
2. Choose a printer profile or create one with the build dimensions you need.
3. Import an STL, OBJ, GLB, GLTF, or 3MF model.
4. Inspect dimensions, mesh health, overhangs, and printability findings.
5. Transform, repair, hollow, slice, or arrange the model as needed.
6. Save the project and export the resulting mesh or 3MF package.

## Verify the setup

With the API running, use:

```powershell
python tests/verify_health.py --base-url http://127.0.0.1:8000
python tests/test_critical_workflow.py --base-url http://127.0.0.1:8000
```

For code changes, also run `npm run test:backend`, `npm run lint`, and `npm run build`.
