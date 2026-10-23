# QA and verification

Outlaw Forge is checked in separate layers because a backend test, static frontend build, desktop lifecycle check, and live API probe establish different behavior. Run the checks relevant to the code changed and report the exact layer that passed.

## Verification matrix

| Check | Command | Requires running API |
| --- | --- | --- |
| Backend suite | `npm run test:backend` | No |
| Frontend lint | `npm run lint` | No |
| Frontend production build | `npm run build` | No |
| Desktop development preflight | `npm run desktop:dev -- -DryRun` | No |
| Desktop package preflight | `npm run desktop:build -- -DryRun` | No |
| Desktop master E2E battery | `python tests/verify_m5_e2e_full.py` | No |
| Health smoke check | `npm run test:smoke` | Yes |
| Critical API workflow | `python tests/test_critical_workflow.py --base-url http://127.0.0.1:8000` | Yes |
| Native Qt build | `cmake --build <build-dir> --target outlaw-forge-native` | No |
| Native Qt tests | `ctest --test-dir <build-dir> --output-on-failure` | No |
| Native live slice | Import STL/OBJ and slice in `apps/native/` | Yes |

Configure the native target with Qt 6.6+, CMake 3.21+, and a C++20 toolchain. See [the native README](../apps/native/README.md) for configuration and launch commands. Native command tests use a local HTTP stub; they do not prove that the live API is running or that a particular customer mesh will produce a watertight cut.

The repository PowerShell orchestrator combines the primary web and backend checks:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/test.ps1
```

Run layers independently when a combined process times out. This distinguishes a code failure from a slow build, missing toolchain, or unavailable local service.

## Quality expectations

- Backend tests pass without schema or storage initialization failures.
- FastAPI responses remain synchronized with shared TypeScript contracts.
- Geometry calculations remain deterministic and use millimetres.
- Original uploads are preserved; derived revisions use working or export storage.
- Invalid input returns a controlled, actionable error.
- Frontend lint and production build complete without errors.
- Static desktop export creates `apps/web/out/index.html`.
- Sidecar startup selects a loopback port and reaches a healthy state.
- Closing the Tauri desktop app terminates its sidecar process.
- Desktop automation dry runs report prerequisite and path status without changing build outputs.
- The native slice request maps the active instance transform into source coordinates and keeps the original scene geometry on service/download failure.
- Native slice status reports `is_watertight` separately for both API results. Capping is requested, but the native client does not heal an open result.
- User-visible workbench copy contains no em dash or separator en dash characters.

## Release checks

A public desktop release should also verify:

- installer output on a clean Windows host
- first launch without a separately installed Python runtime
- native file associations and open-with behavior
- import, repair, prepare, and export using local user-selected files
- writable application data paths without administrator access
- clean shutdown with no remaining API listener or Python sidecar
- dependency audit results and documented exceptions
- native viewport packaging separately, if it is added to a release bundle

Signed installers and automatic updates are not currently claimed as released features. The standalone Qt viewport is not included in the Tauri bundle.

## Live troubleshooting

If a smoke check cannot connect, start Uvicorn from the repository root with `--app-dir apps/api`. If the web frontend cannot reach the API, verify `NEXT_PUBLIC_API_URL`, dynamic Tauri URL injection, and allowed local CORS origins. For the standalone Qt viewport, set `OUTLAW_FORGE_API_URL` to the FastAPI origin; it defaults to `http://127.0.0.1:8000`.
