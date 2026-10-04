# Desktop App Development and Packaging

Outlaw Forge uses a Tauri 2 desktop shell around a statically exported Next.js workbench. A FastAPI geometry sidecar supplies deterministic mesh operations and SQLite persistence over a loopback-only connection.

## Implemented runtime

```text
Tauri 2 native window
  -> static Next.js and Three.js interface
  -> dynamically assigned 127.0.0.1 API port
  -> FastAPI geometry sidecar
  -> SQLite plus uploads, working revisions, and exports
```

At startup, the Rust shell selects an available loopback port, launches the packaged sidecar or the development Python fallback, waits for the health check, and exposes the API address to the webview. On Windows, the sidecar is assigned to a Job Object so it cannot remain orphaned after the desktop process closes.

The desktop shell also provides native menus, keyboard accelerators, file-open handling, file associations, and native file dialogs. Browser development remains supported for fast UI work.

## Implementation map

| Area | Source |
| :--- | :--- |
| Tauri lifecycle and sidecar supervision | `src-tauri/src/lib.rs` |
| Window, bundle, and file association settings | `src-tauri/tauri.conf.json` |
| Desktop capability allowlist | `src-tauri/capabilities/default.json` |
| Python executable entry point | `apps/api/app/cli.py` |
| PyInstaller bundle definition | `apps/api/outlaw_forge.spec` |
| Static web export configuration | `apps/web/next.config.mjs` |
| Browser and native dialog bridge | `apps/web/src/lib/native-dialog.ts` |
| Desktop build orchestration | `scripts/desktop-dev.ps1`, `scripts/desktop-build.ps1` |

## Development commands

From the repository root:

```powershell
# Confirm the desktop toolchain and planned commands without launching it
npm run desktop:dev -- -DryRun

# Launch the desktop application in development mode
npm run desktop:dev

# Validate the production packaging plan
npm run desktop:build -- -DryRun

# Build the sidecar, static frontend, and desktop bundles
npm run desktop:build
```

Desktop development requires Node.js 20 or newer, Python 3.11 or newer, Rust, and the platform prerequisites required by Tauri. Windows production builds also require WebView2 and the relevant installer toolchain.

## Verification

Run the full desktop acceptance suite after changes to the shell, sidecar startup, static export, file handling, or packaging:

```powershell
python tests/verify_m5_e2e_full.py
```

The suite checks the backend, frontend, desktop configuration, Rust tests, static export, sidecar packaging, and lifecycle cleanup. Also test an actual packaged build on the target operating system before publishing an installer.

## Release checklist

- The sidecar starts without a separately installed Python runtime.
- The API binds only to `127.0.0.1` on a dynamically selected port.
- Closing the desktop app terminates the sidecar and its descendants.
- Original uploads remain immutable; derived files use working or export storage.
- Native open and save flows preserve STL, OBJ, and 3MF file behavior.
- The app writes runtime data to the configured user data location.
- Backend tests, lint, static export, Rust tests, and the desktop acceptance suite pass.
- Installers are signed and tested on clean machines before public release.

## Current release boundary

The desktop architecture and local packaging pipeline are implemented. Signed public installers, automatic updates, and direct G-code generation are not currently presented as completed release features. Keep documentation and UI copy explicit about those limits.
