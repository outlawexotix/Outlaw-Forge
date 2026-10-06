# Outlaw Forge Test Infrastructure: Standalone Sidecar E2E Verification

This document specifies the architecture, operational design, interface contracts, and execution protocols for the Outlaw Forge Standalone Sidecar End-to-End (E2E) Verification Harness (`tests/verify_sidecar_e2e.py`).

---

## 1. Executive Summary & Purpose

Outlaw Forge operates as a hybrid desktop CAD workbench combining a Next.js / Three.js frontend shell (packaged with Tauri 2.0) and a high-performance Python FastAPI geometry sidecar (compiled into a standalone Windows binary via PyInstaller).

The E2E sidecar test harness (`tests/verify_sidecar_e2e.py`) serves as the master opaque-box and runtime verifier for the geometry sidecar. It validates the complete operational lifecycle from process launch through 3D computational geometry execution to clean resource deallocation, ensuring:
- Zero dependency on external Python runtimes when testing the compiled executable.
- Dynamic ephemeral port binding on loopback (`127.0.0.1:0`) with zero port collisions.
- Unbuffered startup handshake detection via both stdout piping and file emission.
- Genuine 3D computational geometry execution using native C++ extensions (NumPy, Trimesh, manifold3d).
- Strict adherence to the Millimetre-Standard across all dimensions and bounding boxes.
- Zero orphaned background processes and instant socket release upon termination.

---

## 2. Architecture & Dual-Track Verification

The harness implements a dual-track verification strategy to support both pre-compilation development workflows and post-packaging binary qualification.

### Track A: Standalone Compiled Executable (Production Track)
- Target: `dist/outlaw-forge-api/outlaw-forge-api.exe` or `binaries/outlaw-forge-api.exe`
- Verification Type: Opaque-box execution.
- Scope: Validates bundled Python runtime, frozen C-extension dynamic libraries (`.pyd` / `.dll`), embedded assets, isolated database creation, and process supervisor lifecycle.

### Track B: Development Python Runtime Fallback (Development Track)
- Target: `python apps/api/app/cli.py`
- Trigger: Invoked explicitly via `--fallback-python` when the compiled binary is not yet staged.
- Scope: Validates CLI argument parsing, port resolution logic, FastAPI lifespan hooks, router wiring, and Trimesh/NumPy transformations in the local Python environment.

---

## 3. Verification Pipeline Stages

The test harness executes a 5-stage sequential verification battery:

```text
[Stage 1: Process Spawning]
  Spawn binary / CLI with --port 0 --host 127.0.0.1
  Isolate storage (--storage-dir) and SQLite DB (--db-path) in temp directory
      |
[Stage 2: Startup Handshake]
  Read unbuffered stdout for:
    "OUTLAW_FORGE_API_READY:port=<port>" or "HEALTH_OK: PORT=<port>"
  Verify atomic handshake JSON file on disk (handshake.json)
      |
[Stage 3: Health Polling]
  Poll GET /health (HTTP 200, status="healthy", latency tracking)
  Poll GET /api/v1/health (HTTP 200, services.mesh_engine="ready")
      |
[Stage 4: Real 3D Mesh Geometry Workflow]
  POST /api/v1/projects -> Create test project
  POST /api/v1/projects/{id}/models/import -> Upload 10x10x10mm ASCII STL cube
  Verify native geometry properties:
    - 12 triangles, watertight=True
    - Bounds dimensions: [10.0, 10.0, 10.0] mm
    - Volume: 1.0000 cm3 (1000.0 mm3)
  POST /api/v1/projects/{id}/models/{id}/rotate -> Rotate 90 deg around X axis
  POST /api/v1/projects/{id}/models/{id}/scale -> Uniform scale 200%
  Verify derived mesh properties:
    - Derived bounds dimensions: [20.0, 20.0, 20.0] mm
    - Derived volume: 8.0000 cm3 (8000.0 mm3)
      |
[Stage 5: Clean Termination & Zero-Zombie Verification]
  proc.terminate() -> wait(5s)
  Verify PID is dead (Win32 OpenProcess / GetExitCodeProcess check)
  Verify socket port release (immediate TCP re-bind on loopback)
  Verify SQLite DB file locks released and temp directory cleaned up
```

---

## 4. Authoritative Geometry & Contract Specifications

### 4.1 Minimal Benchmark STL Cube
The test harness generates a mathematically deterministic ASCII STL cube with coordinates:
- X: 0.0 mm to 10.0 mm
- Y: 0.0 mm to 10.0 mm
- Z: 0.0 mm to 10.0 mm

Authoritative properties:
- Face Count: 6 quad faces represented as 12 planar triangles.
- Vertex Count: 8 unique geometric vertices (36 indexed facet vertices).
- Watertightness: True (closed, 2-manifold surface with zero boundary edges).
- Surface Area: 6.0000 cm2 (600.0 mm2).
- Initial Volume: 1.0000 cm3 (1000.0 mm3).
- Initial Bounding Box Dimensions: [10.0, 10.0, 10.0] mm.

### 4.2 Derived Scale Transformation (200% Uniform)
Applying uniform scale of 200% (`uniform_scale_percent: 200.0`):
- Linear Scaling Factor: 2.0x.
- Derived Bounding Box Dimensions: [20.0, 20.0, 20.0] mm.
- Volume Scaling Factor: 2.0^3 = 8.0x.
- Derived Volume: 8.0000 cm3 (8000.0 mm3).

### 4.3 Millimetre Standard Enforcement
In accordance with Core Tenet 1 of `AGENTS.md`, all dimensions and coordinates are strictly measured in millimetres (`mm`), and volumes are represented in cubic centimetres (`cm3`) where 1.0 cm3 = 1000.0 mm3. Any deviation exceeding 0.15 mm on dimensions or 5% on volume fails the test suite.

---

## 5. Startup Handshake & Process Supervisor Contracts

### 5.1 Stdout Token Specifications
Upon completing SQLite schema initialization and port binding, the sidecar emits the following unbuffered tokens to standard output:
- Standard Desktop Supervisor Token: `OUTLAW_FORGE_API_READY:port=<port>\n`
- Legacy / Empirical Harness Token: `HEALTH_OK: PORT=<port>\n`

Both tokens are flushed immediately via `sys.stdout.flush()`. The test harness accepts either token via regex:
```python
r"(?:OUTLAW_FORGE_API_READY:port=(\d+)|HEALTH_OK:\s*PORT=(\d+))"
```

### 5.2 Handshake File Protocol
When launched with `--handshake-file <path>`, the sidecar writes an atomic JSON payload:
```json
{
  "status": "healthy",
  "port": 54321
}
```
The test harness asserts that this file exists on disk, parses cleanly, and matches the port reported over stdout.

### 5.3 Health Endpoint Schema
The harness validates both root and versioned health endpoints:
- `GET http://127.0.0.1:<port>/health`
- `GET http://127.0.0.1:<port>/api/v1/health`

Expected response payload:
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "app_name": "Outlaw Forge",
  "environment": "development",
  "services": {
    "database": "connected",
    "mesh_engine": "ready"
  },
  "system": {
    "platform": "Windows 10 (AMD64)",
    "python_version": "3.11.0"
  },
  "timestamp": "2026-10-05T23:45:25.560043+00:00"
}
```

---

## 6. Execution Instructions & CLI Reference

### 6.1 Running with Compiled Binary
When the sidecar binary has been built by PyInstaller:
```powershell
python tests/verify_sidecar_e2e.py
```
Or specify an explicit binary path:
```powershell
python tests/verify_sidecar_e2e.py --exe-path "dist/outlaw-forge-api/outlaw-forge-api.exe"
```

### 6.2 Running with Python Runtime Fallback
To test the harness logic or verify sidecar routes before packaging:
```powershell
python tests/verify_sidecar_e2e.py --fallback-python
```

### 6.3 Command Line Flags
| Flag | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `--exe-path` | string | `None` | Explicit path to compiled executable |
| `--fallback-python` | flag | `False` | Allow fallback to Python CLI if binary is missing |
| `--timeout` | float | `25.0` | Maximum startup handshake timeout in seconds |
| `--host` | string | `127.0.0.1` | Loopback IP interface to bind |

### 6.4 Expected Console Output (100% Pass)
```text
==========================================================================
 OUTLAW FORGE: STANDALONE SIDECAR E2E VERIFICATION BATTERY
==========================================================================
  Mode: Standalone Compiled Binary Executable
  Binary Path: d:\Outlaw-Forge\dist\outlaw-forge-api\outlaw-forge-api.exe

[Step 1] Spawning sidecar process on dynamic ephemeral port 0...
[Step 2] Awaiting unbuffered startup handshake over stdout pipe...
  [PASS] Startup handshake verified: 'OUTLAW_FORGE_API_READY:port=54321'
  Bound loopback dynamic port: 54321
  [PASS] Handshake JSON file validated on disk: {'status': 'healthy', 'port': 54321}

[Step 3] Polling API health check endpoints...
  [PASS] GET /health responded HTTP 200 in 14.20ms (services: {'database': 'connected', 'mesh_engine': 'ready'})
  [PASS] GET /api/v1/health responded HTTP 200 in 85.30ms (mesh_engine: ready)

[Step 4] Executing real 3D mesh geometry pipeline (C++ extensions)...
  [PASS] Created project: ID=proj_a1b2c3d4e5f6
  Uploading 10x10x10mm ASCII STL cube (1000 mm3)...
  [PASS] Imported model: ID=wm_f6e5d4c3b2a1
  Imported Mesh Properties:
    - Triangles: 12 (expected: 12)
    - Watertight: True (expected: True)
    - Volume: 1.0000 cm3 (~1000 mm3, expected: ~1.0 cm3)
    - Dimensions: [10.0, 10.0, 10.0] mm (expected: [10.0, 10.0, 10.0])
  Applying 3D rotation (90 deg around X axis)...
  [PASS] 3D Rotation applied. Resulting rotation: [90.0, 0.0, 0.0] deg
  Applying 3D scale (200% uniform scaling)...
  Scaled Mesh Properties:
    - Dimensions: [20.0, 20.0, 20.0] mm (expected: [20.0, 20.0, 20.0])
    - Volume: 8.0000 cm3 (expected: ~8.0 cm3 = 8000 mm3)

[Step 5] Process termination, socket release, and zero-zombie verification...
  Initiating graceful termination of child PID 12345...
  [PASS] Process PID 12345 terminated cleanly (exit code: 0).
  [PASS] Confirmed PID 12345 is completely terminated.
  [PASS] Port 54321 successfully re-bound; socket fully released.
  [PASS] Isolated SQLite DB (45,056 bytes) verified.

==========================================================================
 VERIFICATION RESULTS SUMMARY
==========================================================================
  [PASS]  Dynamic Port 0 & Stdout Handshake    Bound port 54321
  [PASS]  Handshake File Persistence           JSON verified (port=54321)
  [PASS]  Root /health Endpoint                HTTP 200 in 14.20ms
  [PASS]  Versioned /api/v1/health             mesh_engine: ready
  [PASS]  Project Creation                     Project ID: proj_a1b2c3d4e5f6
  [PASS]  STL Model Import                     Model ID: wm_f6e5d4c3b2a1
  [PASS]  Geometry Triangle Count              12 triangles verified
  [PASS]  Geometry Watertightness              Watertight verified
  [PASS]  Millimetre Bounds Precision          Dims: [10.0, 10.0, 10.0] mm (err < 0.15mm)
  [PASS]  Volume Calculation                   1.0000 cm3 (~1000 mm3)
  [PASS]  3D Rotation Operation                Rotation: [90.0, 0.0, 0.0] deg
  [PASS]  Scaled Bounding Box Millimetres      Dims: [20.0, 20.0, 20.0] mm
  [PASS]  Scaled Volume Verification           8.0000 cm3 (~8000 mm3)
  [PASS]  Process Termination                  PID 12345 exited
  [PASS]  Socket Port Release                  Port 54321 freed
  [PASS]  Database Persistence                 45,056 bytes
==========================================================================
 ALL SIDECAR E2E VERIFICATION CHECKS PASSED (100%)
==========================================================================
```

---

## 7. Packaging & Staging Locations

The PyInstaller spec (`apps/api/outlaw_forge.spec`) and build scripts output and stage the executable across standard repository locations:
1. Primary Build Directory: `dist/outlaw-forge-api/outlaw-forge-api.exe`
2. Staged Project Binaries: `binaries/outlaw-forge-api.exe`
3. Tauri Desktop Sidecar Target: `src-tauri/binaries/outlaw_forge_sidecar.exe`

The test harness searches all these locations in precedence order when `--exe-path` is not provided.
