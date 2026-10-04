# QA and verification

Outlaw Forge is verified in independent layers. Backend tests cover geometry and API behavior, frontend checks cover contracts and production output, and desktop suites cover static export, sidecar supervision, process cleanup, and packaging automation.

## Verification matrix

| Check | Command | Requires running API |
| --- | --- | --- |
| Backend suite | `npm run test:backend` | No |
| Frontend lint | `npm run lint` | No |
| Frontend production build | `npm run build` | No |
| Desktop development preflight | `npm run desktop:dev -- -DryRun` | No |
| Desktop package preflight | `npm run desktop:build -- -DryRun` | No |
| Desktop master E2E battery | `python tests/verify_m5_e2e_full.py` | No |
| Health smoke test | `npm run test:smoke` | Yes |
| Critical workflow test | `python tests/test_critical_workflow.py --base-url http://127.0.0.1:8000` | Yes |

The PowerShell orchestrator combines backend, frontend, and health checks:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/test.ps1
```

Run layers independently when a combined process times out. This distinguishes a code failure from a slow build, missing toolchain, or unavailable local service.

## Quality expectations

- Backend tests pass without schema or storage initialization failures.
- FastAPI responses remain synchronized with shared TypeScript contracts.
- Geometry calculations remain deterministic and use millimetres.
- Original uploads are preserved and derived revisions use working or export storage.
- Invalid input returns a controlled, actionable error.
- Frontend lint and production build complete without errors.
- Static desktop export creates `apps/web/out/index.html`.
- Sidecar startup selects a local port and reaches a healthy state.
- Closing the desktop app terminates its sidecar process.
- Desktop automation dry runs report prerequisite and path status without changing build outputs.
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

## Live troubleshooting

If a smoke check cannot connect, start Uvicorn from the repository root with `--app-dir apps/api`. If the frontend cannot reach the API, verify `NEXT_PUBLIC_API_URL`, the dynamic Tauri URL injection, and allowed local CORS origins.
