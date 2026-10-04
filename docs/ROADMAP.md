# Roadmap

Outlaw Forge has moved from a browser prototype to an implemented local desktop architecture. This roadmap separates the verified baseline from release engineering and future slicing capabilities.

## Implemented baseline

- Tauri 2 desktop shell with a static Next.js and Three.js workbench.
- Supervised FastAPI geometry sidecar using a dynamic loopback port.
- Windows Job Object lifecycle management to prevent orphaned sidecar processes.
- Native menus, keyboard accelerators, dialogs, permissions, and STL/OBJ/3MF associations.
- SQLite-backed projects, printer profiles, working model revisions, and operation history.
- Print-readiness cockpit for overhangs, thin walls, watertightness, printer fit, and material estimates.
- Deterministic transform, repair, hollow, slice, connector, arrangement, infill, and reinforcement workflows.
- Interactive viewport inspection, layer and overhang modes, build-plate controls, and direct model manipulation.
- OrcaSlicer-oriented 3MF export, MaskSmith, and FigureForge workflows.
- PyInstaller and Tauri packaging automation with dry-run preflight checks.
- Backend, static export, supervisor, lifecycle, automation, and master E2E verification suites.

## Current priorities

1. Upgrade the Next.js dependency line and remove current production audit findings.
2. Produce repeatable signed Windows installer artifacts from a clean build host.
3. Add browser-level interaction tests for the print-readiness cockpit and advanced geometry drawer.
4. Improve native open/save integration so all import and export paths use desktop dialogs.
5. Add migration and backup tooling for local SQLite projects and derived mesh storage.
6. Expand printer profiles and validate non-rectangular build volumes.

## Deferred capabilities

- Direct G-code generation and full slicer-engine integration.
- Automatic support generation and toolpath optimization.
- Signed auto-update distribution for desktop releases.
- Multi-user server deployment and authentication.
- Provider-backed advisory AI for reference analysis and print diagnosis.

Roadmap items are proposals until code, contracts, and verification land together. See the [QA guide](./QA_ACCEPTANCE.md) for completion criteria.
