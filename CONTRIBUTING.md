# Contributing to Outlaw Forge

Outlaw Forge is a TypeScript/Python monorepo. Contributions are welcome when they keep geometry deterministic, preserve source assets, and include the verification needed to explain the change.

## Development flow

1. Fork the repository and create a focused branch, for example `codex/mesh-export-fix`.
2. Install the JavaScript and Python dependencies described in the [getting-started guide](docs/getting-started.md).
3. Make the smallest coherent change and update the relevant documentation.
4. Run `npm run test:backend`, `npm run lint`, and `npm run build`.
5. If the API behavior changed, run the live health and critical-workflow checks as well.
6. Open a pull request with the intent, verification performed, and any known limitations.

## Geometry and data rules

- Use millimetres for persisted dimensions and API values.
- Do not overwrite original uploads; derived meshes belong in working or export storage.
- Keep API contracts in `packages/shared/` synchronized with Pydantic models.
- Do not let advisory AI code silently mutate geometry or project state.
- Add regression coverage for bug fixes, especially mesh, storage, and printability behavior.

## Design submissions

Design assets should include a clear name, supported file format, dimensions, intended material, and any special printing instructions. Put reusable assets in the appropriate `designs/` subdirectory and keep generated runtime files out of Git.

Please be respectful, document assumptions, and respect the MIT license and third-party intellectual property.
