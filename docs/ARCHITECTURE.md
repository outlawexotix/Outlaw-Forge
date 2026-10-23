# Outlaw Forge architecture

## Product shape

Outlaw Forge currently has two desktop-facing implementations and one shared geometry service:

1. **Main workbench:** a Tauri 2 application hosting the statically exported Next.js and Three.js interface. The Rust shell starts and supervises a local FastAPI sidecar.
2. **Browser development workbench:** the same Next.js interface served for development, connected to a separately started local API.
3. **Native viewport foundation:** a separate Qt Quick 3D executable under `apps/native/`. It is experimental and is not packaged into the Tauri application.

The main workbench remains the fuller project workflow. Its workflow rail tracks inspection, repair, readiness, print preparation, and export; the selected-model panel reports overhangs, thin walls, watertightness, printer-volume fit, and a PLA material estimate, with explicit repair, orientation preparation, and STL export actions. The native viewport has its own documented migration boundary and currently sends STL/OBJ slicing through the existing API. Native viewport features should not be described as Tauri features unless they have also been integrated into the Tauri workbench.

## Repository map

```text
apps/
├── api/          FastAPI routes, Pydantic models, SQLite persistence, geometry services
├── web/          Next.js App Router, React workbench, Three.js / React Three Fiber viewport
└── native/       Qt Quick 3D executable, local mesh reader, service-backed slice client
packages/
├── shared/       TypeScript API and viewport contracts corresponding to API models
├── three-tools/  Web renderer loaders, geometry transforms, materials, and viewport utilities
└── ui/           Shared web UI primitives
src-tauri/        Tauri window, capabilities, native menus, sidecar lifecycle, package config
data/             Ignored local database and source/working/export mesh storage
docs/             Product, architecture, geometry, workflow, QA, and migration documentation
scripts/          Development, packaging, and verification helpers
tests/            Service smoke and desktop acceptance checks
```

## Runtime paths

### Main desktop workbench

```text
Tauri 2 shell
  -> static Next.js build in apps/web/out
  -> FastAPI sidecar on a dynamically selected 127.0.0.1 port
  -> SQLite project data and local source/working/export files
```

The Rust shell starts the sidecar, waits for its health response, passes its selected address to the webview, and shuts the process down with the desktop app. On Windows, Job Object supervision cleans up sidecar descendants. Browser development can use a fixed local API port instead.

### Native viewport foundation

```text
Qt Quick 3D scene in Z-up millimetres
  -> local STL/OBJ and limited 3MF viewing
  -> Qt Network client for project import, slice, and result-file routes
```

The native client creates a service project lazily, uploads supported source meshes, maps the world-space plane into the selected instance's source coordinates, and displays returned revisions only after both files are downloaded. It uses existing API contracts. Mesh closure is reported from the API's `is_watertight` metadata for each half. The native phase does not make an open result watertight automatically.

## Coordinate and geometry boundaries

- Lengths, printer dimensions, persisted transforms, and API geometry coordinates use millimetres.
- The web workbench uses a Three.js Y-up render scene and keeps print-space calculations in the service's Z-up convention. Renderer conversion is performed at the viewport boundary.
- The Qt viewport uses a right-handed Z-up scene, so it does not share the web renderer's Y-up scene transform.
- Original source files are immutable. API operations write derived working models and record operation history; exports are separate artifacts.
- Geometry calculations are deterministic. AI suggestions, if introduced, remain advisory and cannot silently edit meshes or project data.
- Pydantic API models and shared TypeScript contracts must change together when the service contract changes.

## Persistence and local ownership

FastAPI repositories use SQLite through `aiosqlite`. The configured data root stores the local database, immutable originals, working revisions, and exports. Runtime mesh files, databases, and build output are not tracked by Git. The desktop API binds to loopback by default; it is not a hosted multi-user service.

## Packaging boundary

`scripts/desktop-build.ps1` builds the web export, optionally builds a PyInstaller sidecar, and invokes Tauri packaging when its toolchain is present. The Qt executable has its own CMake build in `apps/native/` and currently has no Tauri packaging integration. See [the desktop workflow](./skills/desktop-app-workflow.md) and [native migration plan](./NATIVE_VIEWPORT_MIGRATION.md).
