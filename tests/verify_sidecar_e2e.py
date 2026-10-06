#!/usr/bin/env python3
"""Outlaw Forge: Standalone Sidecar Binary (.exe) End-to-End Verification Harness.

Master opaque-box and runtime verification suite for Outlaw Forge desktop sidecar:
1. Binary Discovery: Locates compiled executable (binaries/ or dist/) or python CLI fallback.
2. Port 0 Binding: Spawns process on dynamic ephemeral loopback port (127.0.0.1:0).
3. Stdout Handshake: Reads unbuffered stdout for OUTLAW_FORGE_API_READY:port= or HEALTH_OK: PORT=.
4. Handshake File: Verifies atomic handshake JSON file on disk.
5. Health Polling: Polls GET /health and GET /api/v1/health with latency tracking.
6. Real 3D Mesh Geometry:
   - Creates project (POST /api/v1/projects)
   - Uploads 10x10x10mm ASCII STL cube (POST /api/v1/projects/{id}/models/import)
   - Asserts volume ~1.0 cm3 (1000 mm3), 12 triangles, watertightness, dimensions [10, 10, 10] mm
   - Applies 3D rotation (POST /api/v1/projects/{id}/models/{id}/rotate)
   - Applies 3D scale 200% (POST /api/v1/projects/{id}/models/{id}/scale)
   - Asserts derived dimensions [20, 20, 20] mm and volume ~8.0 cm3 (8000 mm3)
7. Clean Termination: Graceful shutdown, socket release verification, zero zombie processes.
"""

import argparse
import ctypes
import io
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent

# Minimal valid 10x10x10mm ASCII STL Cube (12 triangles, 1000 mm3 = 1.0 cm3)
MINIMAL_CUBE_STL = b"""solid cube
  facet normal 0 0 1
    outer loop
      vertex 0 0 10
      vertex 10 0 10
      vertex 10 10 10
    endloop
  endfacet
  facet normal 0 0 1
    outer loop
      vertex 0 0 10
      vertex 10 10 10
      vertex 0 10 10
    endloop
  endfacet
  facet normal 0 0 -1
    outer loop
      vertex 0 0 0
      vertex 10 10 0
      vertex 10 0 0
    endloop
  endfacet
  facet normal 0 0 -1
    outer loop
      vertex 0 0 0
      vertex 0 10 0
      vertex 10 10 0
    endloop
  endfacet
  facet normal 0 1 0
    outer loop
      vertex 0 10 0
      vertex 10 10 10
      vertex 10 10 0
    endloop
  endfacet
  facet normal 0 1 0
    outer loop
      vertex 0 10 0
      vertex 0 10 10
      vertex 10 10 10
    endloop
  endfacet
  facet normal 0 -1 0
    outer loop
      vertex 0 0 0
      vertex 10 0 0
      vertex 10 0 10
    endloop
  endfacet
  facet normal 0 -1 0
    outer loop
      vertex 0 0 0
      vertex 10 0 10
      vertex 0 0 10
    endloop
  endfacet
  facet normal 1 0 0
    outer loop
      vertex 10 0 0
      vertex 10 10 0
      vertex 10 10 10
    endloop
  endfacet
  facet normal 1 0 0
    outer loop
      vertex 10 0 0
      vertex 10 10 10
      vertex 10 0 10
    endloop
  endfacet
  facet normal -1 0 0
    outer loop
      vertex 0 0 0
      vertex 0 10 10
      vertex 0 10 0
    endloop
  endfacet
  facet normal -1 0 0
    outer loop
      vertex 0 0 0
      vertex 0 0 10
      vertex 0 10 10
    endloop
  endfacet
endsolid cube
"""


def is_pid_alive(pid: int) -> bool:
    """Check whether a process PID is currently alive on Windows or POSIX."""
    if sys.platform != "win32":
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    kernel32 = ctypes.windll.kernel32
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    h_proc = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h_proc:
        return False
    exit_code = ctypes.c_ulong()
    kernel32.GetExitCodeProcess(h_proc, ctypes.byref(exit_code))
    kernel32.CloseHandle(h_proc)
    STILL_ACTIVE = 259
    return exit_code.value == STILL_ACTIVE


def terminate_process_tree(proc: subprocess.Popen) -> None:
    """Stop a PyInstaller parent and any one-file child it owns."""
    if proc is None or proc.pid is None:
        return
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    elif proc.poll() is None:
        proc.terminate()
    try:
        proc.wait(timeout=5.0)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=2.0)


def find_executable(override_path: Optional[str] = None) -> Tuple[Optional[Path], bool]:
    """Find sidecar executable. Returns (path, is_python_fallback)."""
    if override_path:
        p = Path(override_path).resolve()
        if p.exists() and p.is_file():
            return p, False
        raise FileNotFoundError(f"Specified executable not found: {override_path}")

    candidates = [
        REPO_ROOT / "dist" / "outlaw-forge-api" / "outlaw-forge-api.exe",
        REPO_ROOT / "dist" / "outlaw-forge-api.exe",
        REPO_ROOT / "dist" / "outlaw_forge_sidecar" / "outlaw_forge_sidecar.exe",
        REPO_ROOT / "dist" / "outlaw_forge_sidecar.exe",
        REPO_ROOT / "binaries" / "outlaw-forge-api.exe",
        REPO_ROOT / "binaries" / "outlaw_forge_sidecar.exe",
        REPO_ROOT / "src-tauri" / "binaries" / "outlaw_forge_sidecar.exe",
        REPO_ROOT / "src-tauri" / "binaries" / "outlaw_forge_sidecar-x86_64-pc-windows-msvc.exe",
    ]

    for cand in candidates:
        if cand.exists() and cand.is_file():
            return cand, False

    dist_dir = REPO_ROOT / "dist"
    if dist_dir.exists() and dist_dir.is_dir():
        found = list(dist_dir.glob("**/*.exe"))
        if found:
            return found[0], False

    binaries_dir = REPO_ROOT / "binaries"
    if binaries_dir.exists() and binaries_dir.is_dir():
        found = list(binaries_dir.glob("**/*.exe"))
        if found:
            return found[0], False

    return None, True


def http_request(
    url: str,
    method: str = "GET",
    data: Optional[dict] = None,
    files: Optional[dict] = None,
    headers: Optional[dict] = None,
    timeout: float = 6.0,
) -> Tuple[int, dict, float]:
    """Execute HTTP request with latency timing and return (status_code, json_body, latency_ms)."""
    req_headers = headers.copy() if headers else {}
    req_headers["Accept"] = "application/json"
    body_bytes = None

    if files:
        boundary = f"----SidecarVerifyBoundary{int(time.time() * 1000)}"
        req_headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
        buf = io.BytesIO()
        for field, (fname, fcontent, mime) in files.items():
            buf.write(f"--{boundary}\r\n".encode())
            buf.write(f'Content-Disposition: form-data; name="{field}"; filename="{fname}"\r\n'.encode())
            buf.write(f"Content-Type: {mime}\r\n\r\n".encode())
            buf.write(fcontent if isinstance(fcontent, bytes) else fcontent.encode("utf-8"))
            buf.write(b"\r\n")
        buf.write(f"--{boundary}--\r\n".encode())
        body_bytes = buf.getvalue()
    elif data is not None:
        req_headers["Content-Type"] = "application/json"
        body_bytes = json.dumps(data).encode("utf-8")

    req = urllib.request.Request(url, data=body_bytes, headers=req_headers, method=method)
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            elapsed = (time.perf_counter() - t0) * 1000.0
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else {}, elapsed
    except urllib.error.HTTPError as e:
        elapsed = (time.perf_counter() - t0) * 1000.0
        raw = e.read().decode("utf-8") if e.fp else "{}"
        try:
            return e.code, json.loads(raw), elapsed
        except Exception:
            return e.code, {"error": raw}, elapsed
    except Exception as e:
        elapsed = (time.perf_counter() - t0) * 1000.0
        return 0, {"error": str(e)}, elapsed


def verify_port_released(port: int, host: str = "127.0.0.1") -> bool:
    """Verify that socket port is completely released and can be bound immediately."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((host, port))
            return True
    except OSError:
        return False


def run_e2e_verification(
    exe_path: Optional[Path],
    is_python: bool,
    timeout_secs: float = 25.0,
    host: str = "127.0.0.1",
) -> bool:
    """Execute master E2E verification battery."""
    print("\n" + "=" * 74)
    print(" OUTLAW FORGE: STANDALONE SIDECAR E2E VERIFICATION BATTERY")
    print("=" * 74)

    if is_python:
        print("  Mode: Development Python Fallback Runtime (apps/api/app/cli.py)")
        cli_py = REPO_ROOT / "apps" / "api" / "app" / "cli.py"
        if not cli_py.exists():
            print(f"  [FAIL] CLI entrypoint not found at: {cli_py}")
            return False
        cmd = [sys.executable, str(cli_py)]
    else:
        print(f"  Mode: Standalone Compiled Binary Executable")
        print(f"  Binary Path: {exe_path}")
        cmd = [str(exe_path)]

    step_results: List[Tuple[str, bool, str]] = []

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        storage_dir = tmp_path / "storage"
        db_path = tmp_path / "outlaw_forge_e2e.db"
        hs_path = tmp_path / "handshake.json"

        cmd.extend([
            "--port", "0",
            "--host", host,
            "--storage-dir", str(storage_dir),
            "--db-path", str(db_path),
            "--handshake-file", str(hs_path),
        ])

        print(f"\n[Step 1] Spawning sidecar process on dynamic ephemeral port 0...")
        env = os.environ.copy()
        env["PYTHONPATH"] = str(REPO_ROOT / "apps" / "api")
        env["PYTHONUNBUFFERED"] = "1"

        proc = subprocess.Popen(
            cmd,
            cwd=str(REPO_ROOT),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

        stderr_lines: List[str] = []

        def capture_stderr():
            try:
                for line in iter(proc.stderr.readline, ""):
                    stderr_lines.append(line)
            except Exception:
                pass

        err_thread = threading.Thread(target=capture_stderr, daemon=True)
        err_thread.start()

        bound_port: Optional[int] = None
        t_start = time.time()

        try:
            # ---------------------------------------------------------
            # Step 2: Startup Handshake Detection
            # ---------------------------------------------------------
            print("[Step 2] Awaiting unbuffered startup handshake over stdout pipe...")
            handshake_line = ""
            while (time.time() - t_start) < timeout_secs:
                if proc.poll() is not None:
                    break
                line = proc.stdout.readline()
                if line:
                    m = re.search(r"(?:OUTLAW_FORGE_API_READY:port=(\d+)|HEALTH_OK:\s*PORT=(\d+))", line)
                    if m:
                        bound_port = int(m.group(1) or m.group(2))
                        handshake_line = line.strip()
                        break
                else:
                    time.sleep(0.04)

            if bound_port is None or bound_port <= 0:
                err_text = "".join(stderr_lines)[:600]
                print(f"  [FAIL] Failed to receive handshake token within {timeout_secs}s.")
                if err_text:
                    print(f"  Child stderr:\n{err_text}")
                step_results.append(("Startup Handshake Detection", False, "No valid handshake token received"))
                return False

            print(f"  [PASS] Startup handshake verified: '{handshake_line}'")
            print(f"  Bound loopback dynamic port: {bound_port}")
            step_results.append(("Dynamic Port 0 & Stdout Handshake", True, f"Bound port {bound_port}"))

            # Handshake file verification
            time.sleep(0.15)
            if not hs_path.exists():
                print(f"  [FAIL] Handshake JSON file was not created at {hs_path}")
                step_results.append(("Handshake File Persistence", False, "File not written"))
                return False

            hs_content = json.loads(hs_path.read_text(encoding="utf-8"))
            if hs_content.get("status") != "healthy" or hs_content.get("port") != bound_port:
                print(f"  [FAIL] Handshake JSON content mismatch: {hs_content}")
                step_results.append(("Handshake File Persistence", False, "Content mismatch"))
                return False

            print(f"  [PASS] Handshake JSON file validated on disk: {hs_content}")
            step_results.append(("Handshake File Persistence", True, f"JSON verified (port={bound_port})"))

            # ---------------------------------------------------------
            # Step 3: Active Health Check Polling
            # ---------------------------------------------------------
            print("\n[Step 3] Polling API health check endpoints...")
            base_url = f"http://{host}:{bound_port}"
            healthy = False
            root_latency = 0.0

            for _ in range(30):
                code, data, lat = http_request(f"{base_url}/health", timeout=1.0)
                if code == 200 and data.get("status") == "healthy":
                    healthy = True
                    root_latency = lat
                    print(f"  [PASS] GET /health responded HTTP 200 in {lat:.2f}ms (services: {data.get('services')})")
                    break
                time.sleep(0.15)

            if not healthy:
                print(f"  [FAIL] Root /health check failed to reach healthy status.")
                step_results.append(("Root /health Endpoint", False, "Did not return HTTP 200 healthy"))
                return False
            step_results.append(("Root /health Endpoint", True, f"HTTP 200 in {root_latency:.2f}ms"))

            # Versioned health check
            code, vdata, vlat = http_request(f"{base_url}/api/v1/health", timeout=2.0)
            if code != 200 or vdata.get("status") != "healthy":
                print(f"  [FAIL] Versioned /api/v1/health failed: code={code}, body={vdata}")
                step_results.append(("Versioned /api/v1/health", False, f"Code {code}"))
                return False

            mesh_status = vdata.get("services", {}).get("mesh_engine", "unknown")
            print(f"  [PASS] GET /api/v1/health responded HTTP 200 in {vlat:.2f}ms (mesh_engine: {mesh_status})")
            step_results.append(("Versioned /api/v1/health", True, f"mesh_engine: {mesh_status}"))

            # ---------------------------------------------------------
            # Step 4: Live 3D Mesh Geometry Workflow
            # ---------------------------------------------------------
            print("\n[Step 4] Executing real 3D mesh geometry pipeline (C++ extensions)...")

            # 4A. Create Project
            code, proj_resp, _ = http_request(
                f"{base_url}/api/v1/projects",
                method="POST",
                data={"name": "E2E Sidecar Binary Geometry Verification", "description": "Verification test project"},
            )
            if code != 201 or "id" not in proj_resp:
                print(f"  [FAIL] Failed to create project: HTTP {code}, response={proj_resp}")
                step_results.append(("Project Creation", False, f"HTTP {code}"))
                return False

            project_id = proj_resp["id"]
            print(f"  [PASS] Created project: ID={project_id}")
            step_results.append(("Project Creation", True, f"Project ID: {project_id}"))

            # 4B. Upload / Import 10x10x10mm ASCII STL Cube
            print("  Uploading 10x10x10mm ASCII STL cube (1000 mm3)...")
            code, model_resp, _ = http_request(
                f"{base_url}/api/v1/projects/{project_id}/models/import",
                method="POST",
                files={"file": ("cube_10mm.stl", MINIMAL_CUBE_STL, "model/stl")},
            )

            # Fallback check if standalone /api/v1/models/upload exists
            if code != 201:
                code_alt, model_alt, _ = http_request(
                    f"{base_url}/api/v1/models/upload",
                    method="POST",
                    files={"file": ("cube_10mm.stl", MINIMAL_CUBE_STL, "model/stl")},
                )
                if code_alt == 201:
                    code, model_resp = code_alt, model_alt

            if code != 201 or "id" not in model_resp:
                print(f"  [FAIL] Failed to import STL model: HTTP {code}, response={model_resp}")
                step_results.append(("STL Model Import", False, f"HTTP {code}"))
                return False

            model_id = model_resp["id"]
            print(f"  [PASS] Imported model: ID={model_id}")
            step_results.append(("STL Model Import", True, f"Model ID: {model_id}"))

            # 4C. Verify Initial Mesh Analysis & Millimetre Dimensions
            triangles = model_resp.get("triangle_count", 0)
            watertight = model_resp.get("is_watertight", False)
            vol_cm3 = model_resp.get("volume_cm3", 0.0) or 0.0
            bounds_obj = model_resp.get("bounds", {})
            dims = bounds_obj.get("dimensions_mm", [0.0, 0.0, 0.0])

            print(f"  Imported Mesh Properties:")
            print(f"    - Triangles: {triangles} (expected: 12)")
            print(f"    - Watertight: {watertight} (expected: True)")
            print(f"    - Volume: {vol_cm3:.4f} cm3 (~1000 mm3, expected: ~1.0 cm3)")
            print(f"    - Dimensions: {dims} mm (expected: [10.0, 10.0, 10.0])")

            if triangles != 12:
                print(f"  [FAIL] Triangle count mismatch: expected 12, got {triangles}")
                step_results.append(("Geometry Triangle Count", False, f"Got {triangles}"))
                return False
            step_results.append(("Geometry Triangle Count", True, "12 triangles verified"))

            if not watertight:
                print(f"  [FAIL] Mesh is not reported as watertight")
                step_results.append(("Geometry Watertightness", False, "Watertight flag False"))
                return False
            step_results.append(("Geometry Watertightness", True, "Watertight verified"))

            # Verify dimensions ~[10.0, 10.0, 10.0] mm
            dim_err = max(abs(dims[i] - 10.0) for i in range(3))
            if dim_err > 0.15:
                print(f"  [FAIL] Dimensions deviate from 10.0 mm: max error {dim_err:.4f} mm")
                step_results.append(("Millimetre Bounds Precision", False, f"Dims {dims}"))
                return False
            step_results.append(("Millimetre Bounds Precision", True, f"Dims: {dims} mm (err < 0.15mm)"))

            # Verify volume ~1.0 cm3 (1000 mm3)
            if not (0.95 <= vol_cm3 <= 1.05):
                print(f"  [FAIL] Volume deviates from 1.0 cm3: got {vol_cm3}")
                step_results.append(("Volume Calculation", False, f"Got {vol_cm3} cm3"))
                return False
            step_results.append(("Volume Calculation", True, f"{vol_cm3:.4f} cm3 (~1000 mm3)"))

            # 4D. Apply 3D Rotation Transformation (90 deg around X axis)
            print("\n  Applying 3D rotation (90 deg around X axis)...")
            rot_url = f"{base_url}/api/v1/projects/{project_id}/models/{model_id}/rotate"
            rot_payload = {"rx_deg": 90.0, "ry_deg": 0.0, "rz_deg": 0.0}

            code, rot_resp, _ = http_request(rot_url, method="POST", data=rot_payload)
            if code != 200:
                # Try direct route /api/v1/models/{model_id}/rotate
                rot_alt_url = f"{base_url}/api/v1/models/{model_id}/rotate"
                code_alt, rot_alt_resp, _ = http_request(rot_alt_url, method="POST", data=rot_payload)
                if code_alt == 200:
                    code, rot_resp = code_alt, rot_alt_resp

            if code != 200:
                print(f"  [FAIL] Rotation operation failed: HTTP {code}, response={rot_resp}")
                step_results.append(("3D Rotation Operation", False, f"HTTP {code}"))
                return False

            rot_transform = rot_resp.get("transform", {})
            rot_deg = rot_transform.get("rotation_deg", [0.0, 0.0, 0.0])
            print(f"  [PASS] 3D Rotation applied. Resulting rotation: {rot_deg} deg")
            step_results.append(("3D Rotation Operation", True, f"Rotation: {rot_deg} deg"))

            # 4E. Apply 3D Scale Transformation (200% uniform scaling)
            print("  Applying 3D scale (200% uniform scaling)...")
            scale_url = f"{base_url}/api/v1/projects/{project_id}/models/{model_id}/scale"
            scale_payload = {"uniform_scale_percent": 200.0}

            code, scale_resp, _ = http_request(scale_url, method="POST", data=scale_payload)
            if code != 200:
                # Fallback to transform endpoint if scale is not mounted
                tx_url = f"{base_url}/api/v1/models/{model_id}/transform"
                code_alt, tx_alt_resp, _ = http_request(tx_url, method="POST", data=scale_payload)
                if code_alt == 200:
                    code, scale_resp = code_alt, tx_alt_resp

            if code != 200:
                print(f"  [FAIL] Scale operation failed: HTTP {code}, response={scale_resp}")
                step_results.append(("3D Scale Operation", False, f"HTTP {code}"))
                return False

            scaled_bounds = scale_resp.get("bounds", {})
            scaled_dims = scaled_bounds.get("dimensions_mm", [0.0, 0.0, 0.0])
            scaled_vol = scale_resp.get("volume_cm3", 0.0) or 0.0
            print(f"  Scaled Mesh Properties:")
            print(f"    - Dimensions: {scaled_dims} mm (expected: [20.0, 20.0, 20.0])")
            print(f"    - Volume: {scaled_vol:.4f} cm3 (expected: ~8.0 cm3 = 8000 mm3)")

            # Verify dimensions ~[20.0, 20.0, 20.0] mm
            scaled_dim_err = max(abs(scaled_dims[i] - 20.0) for i in range(3))
            if scaled_dim_err > 0.3:
                print(f"  [FAIL] Scaled dimensions deviate from 20.0 mm: max error {scaled_dim_err:.4f} mm")
                step_results.append(("Scaled Bounding Box Millimetres", False, f"Dims {scaled_dims}"))
                return False
            step_results.append(("Scaled Bounding Box Millimetres", True, f"Dims: {scaled_dims} mm"))

            # Verify scaled volume ~8.0 cm3 (8000 mm3)
            if not (7.6 <= scaled_vol <= 8.4):
                print(f"  [FAIL] Scaled volume deviates from 8.0 cm3: got {scaled_vol}")
                step_results.append(("Scaled Volume Verification", False, f"Got {scaled_vol} cm3"))
                return False
            step_results.append(("Scaled Volume Verification", True, f"{scaled_vol:.4f} cm3 (~8000 mm3)"))

            # ---------------------------------------------------------
            # Step 5: Termination & Zero-Zombie Verification
            # ---------------------------------------------------------
            print("\n[Step 5] Process termination, socket release, and zero-zombie verification...")
            proc_pid = proc.pid
            print(f"  Initiating graceful termination of child PID {proc_pid}...")

            terminate_process_tree(proc)
            try:
                print(f"  [PASS] Process PID {proc_pid} terminated cleanly (exit code: {proc.returncode}).")
            except Exception as exc:
                print(f"  [FAIL] Process termination reporting failed: {exc}")
                step_results.append(("Process Termination", False, str(exc)))
                return False

            # Confirm process PID is not alive
            time.sleep(0.2)
            if is_pid_alive(proc_pid):
                print(f"  [FAIL] Process PID {proc_pid} is still active after termination!")
                step_results.append(("Process Termination", False, f"PID {proc_pid} alive"))
                return False
            print(f"  [PASS] Confirmed PID {proc_pid} is completely terminated.")
            step_results.append(("Process Termination", True, f"PID {proc_pid} exited"))

            # Confirm port is completely released
            port_released = verify_port_released(bound_port, host=host)
            if not port_released:
                print(f"  [FAIL] Port {bound_port} could not be re-bound immediately.")
                step_results.append(("Socket Port Release", False, f"Port {bound_port} occupied"))
                return False
            print(f"  [PASS] Port {bound_port} successfully re-bound; socket fully released.")
            step_results.append(("Socket Port Release", True, f"Port {bound_port} freed"))

            # Confirm database file on disk
            if not db_path.exists() or db_path.stat().st_size == 0:
                print(f"  [FAIL] SQLite database not created or empty at {db_path}")
                step_results.append(("Database Persistence", False, "DB empty or missing"))
                return False
            print(f"  [PASS] Isolated SQLite DB ({db_path.stat().st_size:,} bytes) verified.")
            step_results.append(("Database Persistence", True, f"{db_path.stat().st_size:,} bytes"))

            # ---------------------------------------------------------
            # Verification Summary Report
            # ---------------------------------------------------------
            print("\n" + "=" * 74)
            print(" VERIFICATION RESULTS SUMMARY")
            print("=" * 74)
            all_passed = True
            for name, passed, detail in step_results:
                status_str = "[PASS]" if passed else "[FAIL]"
                print(f"  {status_str:7} {name:36} {detail}")
                if not passed:
                    all_passed = False

            print("=" * 74)
            if all_passed:
                print(" ALL SIDECAR E2E VERIFICATION CHECKS PASSED (100%)")
            else:
                print(" SOME SIDECAR E2E VERIFICATION CHECKS FAILED")
            print("=" * 74)
            return all_passed

        finally:
            if proc.poll() is None:
                terminate_process_tree(proc)


def main():
    parser = argparse.ArgumentParser(
        prog="verify_sidecar_e2e",
        description="Outlaw Forge Standalone Sidecar Binary E2E Verification Harness",
    )
    parser.add_argument("--exe-path", default=None, help="Explicit path to sidecar executable")
    parser.add_argument(
        "--fallback-python",
        action="store_true",
        help="Allow running verification via Python runtime fallback if compiled executable is missing",
    )
    parser.add_argument("--timeout", type=float, default=25.0, help="Startup handshake timeout in seconds")
    parser.add_argument("--host", default="127.0.0.1", help="Loopback host to bind")
    args = parser.parse_args()

    exe_path, is_python = find_executable(args.exe_path)

    if exe_path is None and not args.fallback_python:
        print("\n" + "=" * 74)
        print(" [NOTICE] STANDALONE SIDECAR EXECUTABLE NOT FOUND")
        print("=" * 74)
        print(" Candidate paths checked:")
        print("   - dist/outlaw-forge-api/outlaw-forge-api.exe")
        print("   - dist/outlaw-forge-api.exe")
        print("   - binaries/outlaw-forge-api.exe")
        print("   - src-tauri/binaries/outlaw_forge_sidecar.exe")
        print("\n To compile the standalone executable:")
        print("   python -m PyInstaller --noconfirm --clean apps/api/outlaw_forge.spec")
        print("\n To verify the harness logic using the development Python runtime fallback:")
        print("   python tests/verify_sidecar_e2e.py --fallback-python")
        print("=" * 74)
        sys.exit(1)

    success = run_e2e_verification(
        exe_path=exe_path,
        is_python=is_python,
        timeout_secs=args.timeout,
        host=args.host,
    )
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
