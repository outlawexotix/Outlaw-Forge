# Outlaw Forge documentation

This directory documents the product that exists in the repository today. Plans and architectural proposals are labelled as such so they are not confused with shipped behavior.

## Start here

- [Getting started](./getting-started.md) - run the desktop workflow, browser workflow, and packaging preflight.
- [Architecture](./ARCHITECTURE.md) - applications, packages, storage boundaries, and engineering rules.
- [Desktop workflow](./skills/desktop-app-workflow.md) - Tauri shell, sidecar supervision, and package construction.
- [Mesh pipeline](./MESH_PIPELINE.md) - units, coordinate spaces, loaders, and deterministic geometry calculations.

## Product references

- [Viewport specification](./VIEWPORT_SPEC.md) - camera, bed, gizmo, and interaction behavior.
- [Printer profiles](./PRINTER_PROFILES.md) - build volumes, kinematics, and profile schema.
- [AI boundaries](./AI_ARCHITECTURE.md) - advisory AI contracts and the deterministic geometry boundary.

## Quality and planning

- [QA and verification](./QA_ACCEPTANCE.md) - web, API, desktop, lifecycle, and release checks.
- [Roadmap](./ROADMAP.md) - implemented capabilities, release priorities, and deferred work.

If a document disagrees with the running code, treat the code and automated tests as the current source of truth and open an issue with the mismatch.
