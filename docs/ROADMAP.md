# Roadmap

The repository has moved beyond the original model-to-printability scaffold. This roadmap separates the current baseline from work that is still being designed.

## Current baseline

- Project and printer profile CRUD backed by SQLite.
- Mesh import, metadata, dimensions, surface area, volume, and watertightness checks.
- Three.js viewport with build plate, camera controls, orientation gizmo, wireframe, and model selection.
- Deterministic transforms: scale, rotate, lay on face, and coordinate conversion.
- Printability analysis, overhang inspection, auto-arrangement, and operation history.
- Plane-based slicing with connector pins, mesh healing, hollowing, and export support.
- OrcaSlicer-oriented materials and 3MF export workflow.
- MaskSmith and FigureForge studio workflows.
- Automated backend tests, frontend lint/build checks, and black-box HTTP verification.

## Near-term priorities

1. Make project state restoration and save feedback consistent across every model operation.
2. Expand printer profile editing and validate non-rectangular build volumes.
3. Add focused frontend component and browser workflow tests.
4. Improve export diagnostics and preserve a clearer provenance record for derived meshes.
5. Consolidate the remaining specification pages with implementation examples and screenshots.

## Deferred work

- Direct G-code generation and slicer process integration.
- Desktop packaging with Tauri or an equivalent shell.
- Provider-backed AI suggestions for orientation, reference analysis, and print diagnosis.
- Additional mesh algorithms such as advanced support planning and thin-wall analysis.
- Production deployment configuration and multi-user authentication.

Roadmap items are proposals until they are represented by code and verification. See the [QA guide](./QA_ACCEPTANCE.md) for the checks that define a usable change.
