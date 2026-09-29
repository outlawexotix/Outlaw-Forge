# Outlaw Forge

Outlaw Forge is a desktop-grade engineering workbench for 3D print preparation, deterministic mesh manipulation, and printer profile management.

## System Architecture

The application is architected around a decoupled Next.js frontend, a high-performance Python FastAPI backend, and a deterministic 3D/mesh processing engine.

```
d:/Outlaw-Forge/
├── backend/                  # FastAPI Application (Python 3.11+)
│   ├── app/
│   │   ├── api/v1/           # API Routers & Endpoints
│   │   ├── core/             # Configuration, Settings & Lifespan
│   │   ├── models/           # SQLite / Pydantic Models
│   │   ├── services/         # Domain Services (Mesh, Storage, Profiles)
│   │   └── main.py           # FastAPI Entrypoint
│   ├── tests/                # Backend pytest suite
│   ├── pyproject.toml        # Backend dependencies & metadata
│   └── requirements.txt
├── frontend/                 # Next.js 14+ / React 18+ App Router
│   ├── src/
│   │   ├── app/              # Next.js App Router (Layout & Views)
│   │   ├── components/       # UI & Workbench Components
│   │   │   ├── layout/       # App Shell, Header, Sidebar, Inspector
│   │   │   ├── viewport/     # 3D R3F Viewport & Controls
│   │   │   └── ui/           # Design System & Primitives
│   │   ├── lib/              # API Client & Utilities
│   │   └── types/            # TypeScript Interfaces & Shared Types
│   ├── package.json
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   └── vitest.config.ts
├── shared/                   # Shared API Contracts & Data Specifications
│   ├── contracts/            # JSON Schemas & OpenAPI definitions
│   └── types/                # Shared Cross-Tier Type Definitions
├── docs/                     # Architectural & Engineering Specifications
│   ├── ARCHITECTURE.md
│   └── VIEWPORT_SPEC.md
└── tests/                    # Integration & End-to-End Test Suite
```

## First Phase: Foundation Setup
- Backend: FastAPI with `/health` and structured JSON status.
- Frontend: Next.js workbench layout with Header, Inspector, Tool Palette, and 3D Viewport mount.
- 3D Engine Spec: Viewport coordinate system, mm unit determinism, and R3F integration architecture.
- QA: Independent health and UI test validations.
