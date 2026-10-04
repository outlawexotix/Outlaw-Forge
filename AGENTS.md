# AGENTS.md

Canonical guidance for AI coding agents (Antigravity, Claude Code, OpenAI Codex, Cursor, GitHub Copilot, Gemini CLI) working in the **Outlaw Forge** codebase.

This is the central operating manual and single source of truth for agents. Read this file before undertaking non-trivial architectural, backend, mesh-processing, or frontend work.

---

## 1. Project Overview & Core Philosophy

Outlaw Forge is a web-based 3D-print preparation workbench for inspecting, repairing, transforming, and arranging mesh models before they reach a slicer. It unifies a **FastAPI geometry engine** with a **Next.js/Three.js CAD-style workbench**.

### Core Tenets (Non-Negotiable)
1. **Millimetre-Standard**: All dimensional data, bounding boxes, printer volumes, and mesh coordinates are in millimetres (`mm`).
2. **Immutability of Source Assets**: Never overwrite raw uploads (`data/uploads/`). Derived meshes are written to distinct working or export storage revisions.
3. **Deterministic Geometry**: Mesh repairs, transformations, cutting planes, and slicing must remain 100% deterministic. AI assistance is strictly advisory and must never silently mutate geometry or project state.
4. **Contract Synchronization**: Pydantic schemas in `apps/api` and TypeScript contracts in `packages/shared/` must always remain in lockstep.
5. **Anti-Slop Craft**: Engineering must follow structured workflows (Socratic grilling, deep-module seams, tracer-bullet TDD, and tight-loop investigation).

---

## 2. Repository Map

```text
d:\Outlaw-Forge\
├── apps/
│   ├── api/                 FastAPI service, SQLite persistence, and mesh operations (PyMeshLab, Trimesh, NumPy)
│   │   ├── app/             Core application code (api routes, core routers, models, schemas, services)
│   │   └── tests/           Pytest test suite (unit, integration, geometry checks)
│   └── web/                 Next.js 14+ / React 18 workbench and Three.js 3D viewport
│       ├── app/             App router pages and API route proxies
│       ├── components/      Workbench UI components, studio tools, toolbars, sidebars
│       └── hooks/           React hooks for project state, mesh manipulation, and viewport interaction
├── packages/
│   ├── shared/              Shared TypeScript API, schema, and viewport contracts (mirrors FastAPI Pydantic models)
│   ├── three-tools/         Three.js geometry loaders (STL/OBJ/3MF), transforms, materials, raycasting, camera rigs
│   └── ui/                  Shared design system primitives and Workbench UI components
├── data/                    Runtime database and asset storage (GITIGNORED - do not commit)
│   ├── uploads/             Original uploaded source meshes (immutable)
│   ├── working/             Derived / intermediate mesh revisions
│   ├── exports/             Exported 3MF / STL bundles
│   └── outlaw_forge.db      Local SQLite database
├── docs/                    Architecture, mesh pipeline, viewport specifications, printer profiles, QA
├── scripts/                 PowerShell dev/build/test scripts (`dev.ps1`, `test.ps1`, verification scripts)
└── tests/                   System-level smoke and critical-workflow black-box checks
```

---

## 3. Engineering Workflows & Craft

For in-depth operating instructions, refer to the dedicated skill documents in `docs/skills/`:

| Situation / Discipline | Skill Reference Document |
| :--- | :--- |
| **New features & vertical slices** | [Tracer Bullets & TDD Feature Development](docs/skills/tdd-tracer-bullets.md) |
| **Stress-testing assumptions & edge cases** | [Requirement Grilling & Socratic Protocol](docs/skills/grilling.md) |
| **Debugging broken geometry or regressions** | [Zero-Theorizing Investigation Protocol](docs/skills/investigate.md) |
| **CAD UI & 3D Viewport anti-slop rules** | [Anti-Slop Design System (CAD & Workbench)](docs/skills/anti-slop-design.md) |
| **Desktop app packaging & sidecar architecture** | [Desktop App Development & Packaging](docs/skills/desktop-app-workflow.md) |
| **Safety rails, command guard, & freeze mode** | [Safety Rails & Guard Protocol](docs/skills/guard.md) |

### A. The "Idea-to-Shipped" Feature Lifecycle
For all new features, follow this structured pipeline (detailed in [docs/skills/tdd-tracer-bullets.md](docs/skills/tdd-tracer-bullets.md)):
1. **Requirement Grilling**: Clarify and stress-test assumptions before writing code. Identify edge cases (non-manifold geometry, zero-thickness walls, degenerate triangles, printer volume overflows). See [docs/skills/grilling.md](docs/skills/grilling.md).
2. **Interface & Contract Design**: Define or update Pydantic models in `apps/api` and mirror them in `packages/shared/`.
3. **Tracer Bullets (Vertical Slices)**: Implement end-to-end in strict order:
   $$\text{Data Model} \longrightarrow \text{Geometry Service} \longrightarrow \text{API Endpoint} \longrightarrow \text{Frontend Store/Hook} \longrightarrow \text{Viewport/UI} \longrightarrow \text{Automated Tests}$$
4. **Verification & Standards Review**: Run the full verification suite before considering any task complete.

### B. The Zero-Theorizing Investigation Protocol
When debugging broken geometry calculations, failing tests, or unexpected viewport behavior (detailed in [docs/skills/investigate.md](docs/skills/investigate.md)):
1. **Reproduce First**: Prohibit speculation until a deterministic reproducer exists (a single `pytest` test or reproducible API call).
2. **Find the Seam**: Isolate whether the failure is in file parsing, Trimesh transformation matrices, coordinate frame conversions, SQLite transaction management, or Three.js scene-graph synchronization.
3. **Fix and Lock In**: Fix the issue at the root cause and ensure the reproducer is added as a permanent regression test.

### C. Safety Rails & Guard
- **Destructive Command Guard**: Never run unconstrained destructive operations (`git reset --hard`, `DROP TABLE`, deletion of `data/uploads`). See [docs/skills/guard.md](docs/skills/guard.md).
- **Freeze Mode**: When troubleshooting subtle geometry bugs, restrict edits to the targeted module to prevent collateral drift in viewport or API state.

---

## 4. Coding Standards & Conventions

### Backend (Python / FastAPI)
- **Runtime**: Python $\ge$ 3.11.
- **Typing**: Use strict type annotations throughout (`pydantic.BaseModel`, `typing.Optional`, `typing.Sequence`).
- **Error Handling**: Use structured HTTP exceptions (`HTTPException`) with actionable error payloads.
- **Mesh Processing**:
  - Keep compute-heavy mesh algorithms vectorized (NumPy / Trimesh / PyMeshLab).
  - Clean up temporary files on disk when generating intermediate meshes.
  - Coordinate system: Right-handed ($Z$-up) standard for 3D printing. Ensure consistent orientation conversions when loading into Three.js ($Y$-up).

### Frontend (TypeScript / Next.js / Three.js)
- **Runtime**: Node.js $\ge$ 20. TypeScript throughout.
- **State Management**: Keep UI state decoupled from Three.js render loops. Avoid storing heavy Three.js instances directly inside React component state (use refs or dedicated scene managers).
- **Styling**: Tailwind CSS with clean, high-contrast CAD/Workbench aesthetic.
- **Discipline (Anti-AI Slop)**:
  - No generic purple gradients or center-aligned marketing cards in CAD workbench views.
  - Prioritize dense, functional, keyboard-accessible engineering controls.
  - **Hard rule**: Never emit em-dashes (`—`) or separator en-dashes (`–`) in user-visible UI copy. Use hyphens `-`, colons, or clean phrasing.

---

## 5. Verification & Test Commands

Always verify changes with the appropriate commands from the workspace root:

```powershell
# 1. Backend test suite
npm run test:backend           # Runs: python -m pytest apps/api/tests

# 2. Frontend lint and type validation
npm run lint                   # Runs ESLint across apps/web

# 3. Frontend production build
npm run build                  # Builds apps/web

# 4. Black-box smoke test (requires running API)
npm run test:smoke             # Runs: python tests/verify_health.py

# 5. Full staged verification pipeline
powershell -ExecutionPolicy Bypass -File scripts/test.ps1
```

---

## 6. Pre-Flight Checklist for Agents

Before completing any task:
- [ ] Are all dimensions, bounding boxes, and coordinate calculations strictly in millimetres?
- [ ] Were raw source uploads preserved without in-place mutation?
- [ ] Are Pydantic schemas in `apps/api` and TypeScript contracts in `packages/shared` in sync?
- [ ] Did you run `npm run test:backend` and ensure all Pytest checks pass?
- [ ] Did you run `npm run lint` and verify no TypeScript or linting errors remain?
- [ ] Is user-facing copy free of em-dashes and AI design tropes?
