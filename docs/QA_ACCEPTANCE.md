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
| Native top command menus | Open File/Edit/View/Window/Settings and exercise local scene actions, viewport toggles, panel/grid visibility, and local file dialogs | No |
| Native local geometry | Import local STL/OBJ/3MF files and run analyze, repair, auto-orient, cut, and STL export in `apps/native/` | No |
| Native components and simplification | Split disconnected components and simplify a derived mesh; inspect scene entries, triangle counts, and topology metrics | No |

Configure the native target with Qt 6.6+, CMake 3.21+, and a C++20 toolchain. See [the native README](../apps/native/README.md) for configuration and launch commands. Qt geometry commands run locally and do not require a running API. A passing test or build does not prove that every arbitrary customer mesh can be repaired or simplified without topology defects; inspect the output analysis before export.

The repository PowerShell orchestrator combines the primary web and backend checks:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/test.ps1
```

Run layers independently when a combined process times out. This distinguishes a code failure from a slow build, missing toolchain, or unavailable Tauri sidecar.

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
- The main workbench readiness panel displays overhang, thin-wall, watertightness, printer-volume, and PLA material-estimate results for its selected model; repair, prepare-for-print, and STL export actions report their operation status.
- The workflow rail reflects model presence, watertightness, build-volume fit, auto-orientation history, and export history. This UI state is separate from the backend and desktop lifecycle verification layers listed above.
- Native geometry commands require no API URL, network access, or running service.
- Native slice status distinguishes successful cap generation from the final watertightness metrics of each output.
- Native split and simplify operations create selectable derived geometry and leave the imported source revision unchanged.
- Native top command menus expose the same scene and viewport operations as the workbench controls. Actions requiring a selection are disabled with an empty scene; local file dialogs work without the FastAPI service.
- User-visible workbench copy contains no em dash or separator en dash characters.

## Release checks

A public desktop release should also verify:

- installer output on a clean Windows host
- first launch without a separately installed Python runtime
- native file associations and open-with behavior
- import, repair, prepare, and export using local user-selected files
- writable application data paths without administrator access
- clean shutdown with no remaining API listener or Python sidecar for the Tauri application
- dependency audit results and documented exceptions
- native viewport packaging separately, if it is added to a release bundle

Signed installers and automatic updates are not currently claimed as released features. The standalone Qt viewport is not included in the Tauri bundle.

## Live troubleshooting

If a smoke check cannot connect, start Uvicorn from the repository root with `--app-dir apps/api`. If the web frontend cannot reach the API, verify `NEXT_PUBLIC_API_URL`, dynamic Tauri URL injection, and allowed local CORS origins. The experimental Qt viewport has no API URL setting and should be diagnosed independently from the FastAPI sidecar.
