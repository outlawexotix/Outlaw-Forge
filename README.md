# Outlaw Forge

Outlaw Forge is a desktop-grade engineering workbench for 3D print preparation, deterministic mesh manipulation, and printer profile management.

## Architecture

- `apps/api/` — FastAPI backend with SQLite persistence, mesh analysis, transformations, printability checks, and model export.
- `apps/web/` — Next.js frontend with the project workbench and Three.js viewport.
- `packages/shared/` — Shared TypeScript API and viewport contracts.
- `packages/three-tools/` — Deterministic geometry loading, transforms, metrics, and overhang analysis.
- `docs/` — Architecture, mesh pipeline, printer profiles, QA, and viewport specifications.
- `tests/` — Integration and health verification scripts.

## Development

Install JavaScript dependencies from the repository root, then run the frontend with:

```powershell
npm install
npm run dev
```

Run the backend test suite with:

```powershell
npm run test:backend
```

Run the frontend production build with:

```powershell
npm run build
```

The backend uses Python 3.11+ and dependencies listed in `apps/api/requirements.txt`. Runtime databases and generated mesh files remain local and are excluded from Git.
