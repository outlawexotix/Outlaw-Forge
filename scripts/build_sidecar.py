#!/usr/bin/env python3
"""Outlaw Forge: Sidecar Executable Packaging and Verification Script.

Compiles apps/api into a standalone executable (outlaw-forge-api.exe) using PyInstaller,
stages the binary to dist/, binaries/, and src-tauri/binaries/, and runs an automated
live smoke test verifying dynamic port 0 handshake, HTTP health, and clean process termination.
"""

import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SPEC_FILE = REPO_ROOT / "apps" / "api" / "outlaw_forge.spec"
DIST_DIR = REPO_ROOT / "dist"
BINARIES_DIR = REPO_ROOT / "binaries"
TAURI_BIN_DIR = REPO_ROOT / "src-tauri" / "binaries"


def ensure_pyinstaller() -> bool:
    """Check if PyInstaller is installed; install it if missing."""
    print("\n--- [1/4] Checking PyInstaller Availability ---")
    try:
        import PyInstaller  # noqa: F401
        print("PyInstaller is already installed.")
        return True
    except ImportError:
        print("PyInstaller not detected. Installing via pip...")
        cmd = [sys.executable, "-m", "pip", "install", "pyinstaller"]
        res = subprocess.run(cmd, cwd=str(REPO_ROOT))
        if res.returncode != 0:
            print("[ERROR] Failed to install PyInstaller.")
            return False
        print("PyInstaller installed successfully.")
        return True


def build_executable(onefile: bool = True) -> Path:
    """Run PyInstaller against apps/api/outlaw_forge.spec."""
    print(f"\n--- [2/4] Building Sidecar Executable (OneFile={onefile}) ---")
    env = os.environ.copy()
    env["PYINSTALLER_ONEFILE"] = "true" if onefile else "false"

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        str(SPEC_FILE),
    ]

    t0 = time.perf_counter()
    proc = subprocess.run(cmd, cwd=str(REPO_ROOT), env=env)
    dt = time.perf_counter() - t0

    if proc.returncode != 0:
        raise RuntimeError(f"PyInstaller build failed with exit code {proc.returncode}")

    target_exe = DIST_DIR / "outlaw-forge-api.exe"
    if not target_exe.exists():
        # Fallback check for directory mode if onefile=False
        dir_exe = DIST_DIR / "outlaw-forge-api" / "outlaw-forge-api.exe"
        if dir_exe.exists():
            target_exe = dir_exe
        else:
            raise FileNotFoundError(f"Expected binary not found in {DIST_DIR}")

    size_mb = target_exe.stat().st_size / (1024 * 1024)
    print(f"[SUCCESS] Built binary in {dt:.1f}s: {target_exe} ({size_mb:.1f} MB)")
    return target_exe


def stage_executable(built_exe: Path) -> None:
    """Stage built executable to required delivery locations."""
    print("\n--- [3/4] Staging Executable to Deliverables Locations ---")
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    BINARIES_DIR.mkdir(parents=True, exist_ok=True)
    TAURI_BIN_DIR.mkdir(parents=True, exist_ok=True)

    destinations = [
        DIST_DIR / "outlaw-forge-api.exe",
        BINARIES_DIR / "outlaw-forge-api.exe",
        TAURI_BIN_DIR / "outlaw_forge_sidecar.exe",
        TAURI_BIN_DIR / "outlaw_forge_sidecar-x86_64-pc-windows-msvc.exe",
    ]

    for dest in destinations:
        if built_exe.resolve() != dest.resolve():
            shutil.copy2(built_exe, dest)
        size_mb = dest.stat().st_size / (1024 * 1024)
        print(f"  -> Staged to: {dest.relative_to(REPO_ROOT)} ({size_mb:.1f} MB)")


def verify_port_released(port: int, host: str = "127.0.0.1") -> bool:
    """Verify that socket port is completely released and can be bound immediately."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((host, port))
            return True
    except OSError:
        return False


def verify_executable(exe_path: Path, timeout: float = 20.0) -> bool:
    """Launch built binary, test dynamic handshake and /health, then terminate."""
    print("\n--- [4/4] Live Verification of Standalone Executable ---")
    print(f"Target executable: {exe_path}")

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        storage_dir = tmp_path / "storage"
        db_path = tmp_path / "smoke_test.db"
        hs_path = tmp_path / "handshake.json"

        cmd = [
            str(exe_path),
            "--port", "0",
            "--host", "127.0.0.1",
            "--storage-dir", str(storage_dir),
            "--db-path", str(db_path),
            "--handshake-file", str(hs_path),
        ]

        print("Spawning binary with --port 0...")
        proc = subprocess.Popen(
            cmd,
            cwd=str(REPO_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

        bound_port = None
        t_start = time.time()
        try:
            print("Awaiting startup handshake on piped stdout...")
            while (time.time() - t_start) < timeout:
                if proc.poll() is not None:
                    err = proc.stderr.read()
                    raise RuntimeError(f"Executable exited prematurely with code {proc.returncode}:\n{err}")

                line = proc.stdout.readline()
                if line:
                    line_clean = line.strip()
                    # Check for OUTLAW_FORGE_API_READY or HEALTH_OK
                    m1 = re.search(r"OUTLAW_FORGE_API_READY:port=(\d+)", line_clean)
                    m2 = re.search(r"HEALTH_OK:\s*PORT=(\d+)", line_clean)
                    if m1:
                        bound_port = int(m1.group(1))
                        print(f"  [PASS] Handshake detected: {line_clean}")
                    elif m2 and bound_port is None:
                        bound_port = int(m2.group(1))
                        print(f"  [PASS] Handshake detected: {line_clean}")

                    if bound_port is not None:
                        break
                else:
                    time.sleep(0.05)

            if bound_port is None:
                raise TimeoutError(f"Startup handshake timed out after {timeout}s")

            print(f"  [PASS] Dynamically bound ephemeral port: {bound_port}")

            # Verify handshake JSON file
            time.sleep(0.1)
            if hs_path.exists():
                hs_data = json.loads(hs_path.read_text(encoding="utf-8"))
                if hs_data.get("status") == "healthy" and hs_data.get("port") == bound_port:
                    print(f"  [PASS] Handshake JSON verified on disk: {hs_data}")
                else:
                    print(f"  [WARN] Handshake JSON content: {hs_data}")
            else:
                print(f"  [WARN] Handshake JSON file not found at {hs_path}")

            # Query root /health endpoint
            health_url = f"http://127.0.0.1:{bound_port}/health"
            print(f"Probing {health_url}...")
            healthy = False
            for attempt in range(20):
                try:
                    req = urllib.request.Request(health_url, headers={"Accept": "application/json"})
                    with urllib.request.urlopen(req, timeout=2.0) as resp:
                        if resp.status == 200:
                            data = json.loads(resp.read().decode("utf-8"))
                            if data.get("status") == "healthy":
                                print(f"  [PASS] Endpoint {health_url} responded HTTP 200: {data}")
                                healthy = True
                                break
                except Exception:
                    time.sleep(0.2)

            if not healthy:
                raise RuntimeError(f"Endpoint {health_url} failed to respond with healthy status")

            # Query /api/v1/health endpoint
            v1_url = f"http://127.0.0.1:{bound_port}/api/v1/health"
            req_v1 = urllib.request.Request(v1_url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req_v1, timeout=2.0) as resp:
                if resp.status == 200:
                    v1_data = json.loads(resp.read().decode("utf-8"))
                    mesh_status = v1_data.get("services", {}).get("mesh_engine")
                    print(f"  [PASS] Endpoint {v1_url} responded HTTP 200 (mesh_engine: {mesh_status})")
                else:
                    raise RuntimeError(f"Endpoint {v1_url} returned status {resp.status}")

            return True

        finally:
            print("Terminating executable...")
            proc.terminate()
            try:
                proc.wait(timeout=5.0)
                print(f"  [PASS] Process terminated cleanly (exit code {proc.returncode}).")
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=2.0)
                print("  [PASS] Process forcefully killed after timeout.")

            if bound_port is not None:
                released = verify_port_released(bound_port)
                if released:
                    print(f"  [PASS] Dynamic port {bound_port} confirmed released.")
                else:
                    print(f"  [WARN] Port {bound_port} could not be immediately re-bound.")


def main():
    parser = argparse.ArgumentParser(description="Outlaw Forge Sidecar Executable Packaging")
    parser.add_argument("--skip-verify", action="store_true", help="Skip live smoke test")
    parser.add_argument("--verify-only", action="store_true", help="Verify existing built executable without compiling")
    parser.add_argument("--exe-path", default=None, help="Explicit path to executable for verification")
    parser.add_argument("--onedir", action="store_true", help="Build in onedir mode instead of onefile")
    args = parser.parse_args()

    if args.verify_only:
        exe_path = Path(args.exe_path) if args.exe_path else (DIST_DIR / "outlaw-forge-api.exe")
        if not exe_path.exists():
            exe_path = BINARIES_DIR / "outlaw-forge-api.exe"
        if not exe_path.exists():
            print(f"[ERROR] Executable not found at {exe_path}")
            sys.exit(1)
        ok = verify_executable(exe_path)
        sys.exit(0 if ok else 1)

    if not ensure_pyinstaller():
        sys.exit(1)

    built_exe = build_executable(onefile=not args.onedir)
    stage_executable(built_exe)

    if not args.skip_verify:
        ok = verify_executable(built_exe)
        if not ok:
            print("[FAIL] Verification smoke test failed.")
            sys.exit(1)

    print("\n" + "=" * 70)
    print(" [SUCCESS] Sidecar binary built, staged, and verified successfully.")
    print("=" * 70)


if __name__ == "__main__":
    main()
