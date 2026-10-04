#!/usr/bin/env python3
"""Empirical stress test harness for Outlaw Forge CLI and sidecar architecture.

Tests:
1. Direct CLI script invocation (python apps/api/app/cli.py)
2. Module invocation from repo root (python -m app.cli)
3. Dynamic ephemeral port assignment (--port 0) with PYTHONPATH
4. Stdout pipe buffering and deadlock verification
5. Custom --storage-dir and --db-path isolation
6. Startup handshake file (--handshake-file) integrity & write ordering
7. Concurrent multi-instance dynamic port allocation
8. Desktop Tauri CORS origin validation
9. Fixed port assignment (--port 8000 / custom)
10. Port in use error handling
11. Frozen mode AppData resolution simulation
"""

import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, Optional, Tuple


REPO_ROOT = Path(__file__).resolve().parent.parent
API_DIR = REPO_ROOT / "apps" / "api"
CLI_SCRIPT = API_DIR / "app" / "cli.py"


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def get_base_env() -> Dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(API_DIR)
    return env


def run_process_with_timeout(
    cmd: list,
    cwd: Path = REPO_ROOT,
    env: Optional[Dict[str, str]] = None,
    timeout: float = 10.0,
) -> Tuple[Optional[subprocess.Popen], Optional[int], str, str]:
    """Start process, read stdout until HEALTH_OK: PORT=<port> is found or timeout expires."""
    merged_env = get_base_env()
    if env:
        merged_env.update(env)

    proc = subprocess.Popen(
        cmd,
        cwd=str(cwd),
        env=merged_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,  # Line buffered
    )

    port = None
    stdout_lines = []
    stderr_lines = []
    start_time = time.time()

    import threading

    def read_stderr():
        for line in iter(proc.stderr.readline, ""):
            stderr_lines.append(line)

    err_thread = threading.Thread(target=read_stderr, daemon=True)
    err_thread.start()

    while time.time() - start_time < timeout:
        if proc.poll() is not None:
            break
        line = proc.stdout.readline()
        if line:
            stdout_lines.append(line)
            match = re.search(r"HEALTH_OK:\s*PORT=(\d+)", line)
            if match:
                port = int(match.group(1))
                break
        else:
            time.sleep(0.05)

    return proc, port, "".join(stdout_lines), "".join(stderr_lines)


def http_get(url: str, headers: Optional[Dict[str, str]] = None, timeout: float = 3.0) -> Tuple[int, dict, dict]:
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return resp.status, dict(resp.headers), data
    except urllib.error.HTTPError as e:
        data = json.loads(e.read().decode("utf-8")) if e.fp else {}
        return e.code, dict(e.headers), data
    except Exception as e:
        return 0, {}, {"error": str(e)}


def kill_proc(proc: Optional[subprocess.Popen]):
    if proc and proc.poll() is None:
        try:
            proc.terminate()
            proc.wait(timeout=3)
        except Exception:
            try:
                proc.kill()
                proc.wait(timeout=2)
            except Exception:
                pass


def test_1_direct_script_invocation() -> Tuple[bool, str]:
    """Test running: python apps/api/app/cli.py --port 0"""
    print("\n--- Test 1: Direct Script Invocation (python apps/api/app/cli.py --port 0) ---")
    proc = subprocess.Popen(
        [sys.executable, str(CLI_SCRIPT), "--port", "0"],
        cwd=str(REPO_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        out, err = proc.communicate(timeout=5)
        print(f"Exit code: {proc.returncode}")
        print(f"Stdout:\n{out}")
        print(f"Stderr:\n{err}")
        has_module_not_found = "ModuleNotFoundError: No module named 'app'" in err
        if has_module_not_found:
            msg = "FAILED with ModuleNotFoundError: No module named 'app'"
            print(f"=> RESULT: {msg}")
            return False, msg
        return True, "Success"
    except subprocess.TimeoutExpired:
        kill_proc(proc)
        return True, "Running"


def test_2_module_invocation_without_pythonpath() -> Tuple[bool, str]:
    """Test running: python -m app.cli from repo root without PYTHONPATH"""
    print("\n--- Test 2: Module Invocation from Repo Root (python -m app.cli) ---")
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    proc = subprocess.Popen(
        [sys.executable, "-m", "app.cli", "--port", "0"],
        cwd=str(REPO_ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        out, err = proc.communicate(timeout=5)
        print(f"Exit code: {proc.returncode}")
        print(f"Stderr:\n{err}")
        has_error = "No module named 'app'" in err or "No module named app" in err
        if has_error:
            msg = "FAILED: No module named 'app' from repo root without PYTHONPATH"
            print(f"=> RESULT: {msg}")
            return False, msg
        return True, "Success"
    except subprocess.TimeoutExpired:
        kill_proc(proc)
        return True, "Running"


def test_3_ephemeral_port_with_pythonpath() -> Tuple[bool, str]:
    """Test --port 0 with PYTHONPATH=apps/api: dynamic port binding and HEALTH_OK handshake."""
    print("\n--- Test 3: Ephemeral Port 0 Binding & Handshake ---")
    proc, port, stdout, stderr = run_process_with_timeout(
        [sys.executable, "-m", "app.cli", "--port", "0"],
        cwd=REPO_ROOT,
        timeout=10.0,
    )
    try:
        print(f"Detected port: {port}")
        print(f"Stdout:\n{stdout}")
        if port is None:
            return False, f"Failed to detect port in stdout. Stderr: {stderr[:200]}"
        if not (1024 <= port <= 65535):
            return False, f"Port {port} out of range"
        if f"HEALTH_OK: PORT={port}" not in stdout:
            return False, f"Missing HEALTH_OK: PORT={port} in stdout"

        # Verify HTTP GET /health
        status, headers, body = http_get(f"http://127.0.0.1:{port}/health")
        print(f"GET /health: status={status}, body={body}")
        if status != 200:
            return False, f"Expected 200, got {status}"
        if body.get("status") != "healthy":
            return False, f"Expected status=='healthy', got {body}"

        return True, f"Port {port} bound, HTTP 200 healthy"
    finally:
        kill_proc(proc)


def test_4_piped_stdout_flushing() -> Tuple[bool, str]:
    """Test piped stdout unbuffered delivery (buffering deadlock verification)."""
    print("\n--- Test 4: Stdout Pipe Flushing (Deadlock Stress Test) ---")
    start_time = time.time()
    proc, port, stdout, stderr = run_process_with_timeout(
        [sys.executable, "-m", "app.cli", "--port", "0"],
        cwd=REPO_ROOT,
        timeout=6.0,
    )
    elapsed = time.time() - start_time
    try:
        if port is None:
            return False, f"Piped stdout timed out. Stderr: {stderr[:200]}"
        print(f"Handshake received in {elapsed:.2f}s (Port {port})")
        if elapsed > 5.0:
            return False, f"Handshake took too long ({elapsed:.2f}s), possible buffering latency"
        return True, f"Flushed immediately in {elapsed:.2f}s"
    finally:
        kill_proc(proc)


def test_5_custom_storage_and_db_paths() -> Tuple[bool, str]:
    """Test --storage-dir and --db-path arguments isolate asset storage and database."""
    print("\n--- Test 5: Custom --storage-dir and --db-path Isolation ---")
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        custom_storage = tmp_path / "custom_storage"
        custom_db = tmp_path / "custom_db_dir" / "isolated.db"
        handshake_file = tmp_path / "handshake.json"

        cmd = [
            sys.executable,
            "-m",
            "app.cli",
            "--port",
            "0",
            "--storage-dir",
            str(custom_storage),
            "--db-path",
            str(custom_db),
            "--handshake-file",
            str(handshake_file),
        ]
        proc, port, stdout, stderr = run_process_with_timeout(cmd, cwd=REPO_ROOT, timeout=10.0)
        try:
            if port is None:
                return False, f"Server failed to start. Stderr: {stderr[:200]}"

            # Poll briefly for handshake file to account for post-flush disk write
            for _ in range(20):
                if handshake_file.exists():
                    break
                time.sleep(0.05)

            if not handshake_file.exists():
                return False, "Handshake file was not created"
            hs_data = json.loads(handshake_file.read_text(encoding="utf-8"))
            if hs_data.get("status") != "healthy" or hs_data.get("port") != port:
                return False, f"Handshake file content mismatch: {hs_data}"

            # Verify database file was created
            if not custom_db.exists() or custom_db.stat().st_size == 0:
                return False, f"Custom database file missing or empty at {custom_db}"

            # Verify database contains expected tables
            import sqlite3
            conn = sqlite3.connect(str(custom_db))
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = {row[0] for row in cursor.fetchall()}
            conn.close()
            required = {"projects", "printer_profiles", "source_files", "working_models", "operations"}
            if not required.issubset(tables):
                return False, f"Required tables missing from custom DB: {required - tables}"

            return True, f"Custom DB ({len(tables)} tables) & handshake file verified"
        finally:
            kill_proc(proc)


def test_6_multiple_concurrent_instances() -> Tuple[bool, str]:
    """Test launching multiple concurrent instances with --port 0 to ensure distinct port allocations."""
    print("\n--- Test 6: Multiple Concurrent Instances with --port 0 ---")
    procs = []
    ports = []
    try:
        for i in range(3):
            proc, port, stdout, stderr = run_process_with_timeout(
                [sys.executable, "-m", "app.cli", "--port", "0"],
                cwd=REPO_ROOT,
                timeout=10.0,
            )
            if port is None:
                return False, f"Instance {i} failed to start. Stderr: {stderr[:200]}"
            procs.append(proc)
            ports.append(port)
            print(f"  Instance {i}: Bound to Port {port}")

        # Ensure all ports are unique
        if len(set(ports)) != 3:
            return False, f"Ports collided across instances: {ports}"

        # Verify all 3 instances respond to /health
        for i, port in enumerate(ports):
            status, _, body = http_get(f"http://127.0.0.1:{port}/health")
            if status != 200 or body.get("status") != "healthy":
                return False, f"Instance {i} on port {port} unhealthy: status={status}"

        return True, f"3 concurrent instances on ports {ports} OK"
    finally:
        for proc in procs:
            kill_proc(proc)


def test_7_tauri_cors_origins() -> Tuple[bool, str]:
    """Test CORS headers for Tauri desktop origins."""
    print("\n--- Test 7: Tauri Webview CORS Origins ---")
    proc, port, stdout, stderr = run_process_with_timeout(
        [sys.executable, "-m", "app.cli", "--port", "0"],
        cwd=REPO_ROOT,
        timeout=10.0,
    )
    try:
        if port is None:
            return False, f"Failed to start server. Stderr: {stderr[:200]}"
        tauri_origins = [
            "tauri://localhost",
            "http://tauri.localhost",
            "https://tauri.localhost",
        ]
        for origin in tauri_origins:
            status, headers, body = http_get(
                f"http://127.0.0.1:{port}/health",
                headers={"Origin": origin},
            )
            cors_header = headers.get("Access-Control-Allow-Origin") or headers.get("access-control-allow-origin")
            print(f"  Origin: {origin} -> Access-Control-Allow-Origin: {cors_header}")
            if cors_header != origin:
                return False, f"CORS failed for {origin}: got '{cors_header}'"

        # Test unauthorized origin
        status, headers, body = http_get(
            f"http://127.0.0.1:{port}/health",
            headers={"Origin": "http://malicious-site.example.com"},
        )
        cors_header = headers.get("Access-Control-Allow-Origin") or headers.get("access-control-allow-origin")
        if cors_header == "http://malicious-site.example.com":
            return False, f"Unauthorized origin was allowed: {cors_header}"
        print("  Origin: http://malicious-site.example.com -> Disallowed (OK)")

        return True, "All 3 Tauri origins accepted; untrusted origins rejected"
    finally:
        kill_proc(proc)


def test_8_fixed_port_binding() -> Tuple[bool, str]:
    """Test --port with a fixed port number."""
    print("\n--- Test 8: Fixed Port Binding ---")
    test_port = find_free_port()
    proc, port, stdout, stderr = run_process_with_timeout(
        [sys.executable, "-m", "app.cli", "--port", str(test_port)],
        cwd=REPO_ROOT,
        timeout=10.0,
    )
    try:
        if port is None:
            return False, f"Failed to start on fixed port {test_port}. Stderr: {stderr[:200]}"
        if port != test_port:
            return False, f"Port mismatch: requested {test_port}, bound {port}"

        status, _, body = http_get(f"http://127.0.0.1:{test_port}/health")
        if status != 200 or body.get("status") != "healthy":
            return False, f"GET /health on fixed port {test_port} failed: {status}"

        return True, f"Fixed port {test_port} bound and verified healthy"
    finally:
        kill_proc(proc)


def test_9_port_in_use_error_handling() -> Tuple[bool, str]:
    """Test how CLI responds when requested port is already in use."""
    print("\n--- Test 9: Port In Use Error Handling ---")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    busy_port = int(s.getsockname()[1])
    s.listen(1)
    print(f"Occupied port {busy_port} with mock listener")

    proc = subprocess.Popen(
        [sys.executable, "-m", "app.cli", "--port", str(busy_port)],
        cwd=REPO_ROOT,
        env=get_base_env(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        out, err = proc.communicate(timeout=6)
        s.close()
        print(f"Exit code: {proc.returncode}")
        print(f"Stderr:\n{err}")
        if proc.returncode != 0:
            return True, f"Exited cleanly with code {proc.returncode} on port conflict"
        return False, "Process did not fail despite port conflict"
    except subprocess.TimeoutExpired:
        s.close()
        kill_proc(proc)
        return False, "Process hung instead of failing on port conflict"


def test_10_handshake_write_ordering() -> Tuple[bool, str]:
    """Verify write ordering: is handshake file created before or after stdout flush?"""
    print("\n--- Test 10: Handshake Write Ordering (Race Condition Probe) ---")
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        handshake_file = tmp_path / "race_handshake.json"

        cmd = [
            sys.executable,
            "-m",
            "app.cli",
            "--port",
            "0",
            "--handshake-file",
            str(handshake_file),
        ]
        proc = subprocess.Popen(
            cmd,
            cwd=REPO_ROOT,
            env=get_base_env(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        try:
            # Read stdout until HEALTH_OK
            line = proc.stdout.readline()
            while line and "HEALTH_OK" not in line:
                line = proc.stdout.readline()

            # At the EXACT moment HEALTH_OK is read from stdout, check if file exists
            exists_immediately = handshake_file.exists()
            print(f"File exists immediately upon reading HEALTH_OK stdout: {exists_immediately}")

            # If false, check after 100ms
            time.sleep(0.1)
            exists_after_delay = handshake_file.exists()
            print(f"File exists after 100ms delay: {exists_after_delay}")

            if not exists_immediately:
                return (
                    False,
                    "RACE CONDITION CONFIRMED: Handshake file does not exist when HEALTH_OK is flushed to stdout (written afterwards)",
                )
            return True, "Handshake file exists immediately upon stdout flush"
        finally:
            kill_proc(proc)


def main():
    print("=================================================================")
    print(" Outlaw Forge M1 CLI & Sidecar Empirical Stress Test Harness    ")
    print("=================================================================")

    tests = [
        ("Direct Script Invocation (python apps/api/app/cli.py)", test_1_direct_script_invocation),
        ("Module Invocation without PYTHONPATH (python -m app.cli)", test_2_module_invocation_without_pythonpath),
        ("Ephemeral Port 0 Binding & Handshake", test_3_ephemeral_port_with_pythonpath),
        ("Stdout Pipe Flushing (Deadlock Stress)", test_4_piped_stdout_flushing),
        ("Custom Storage and DB Paths Isolation", test_5_custom_storage_and_db_paths),
        ("Multiple Concurrent Instances (--port 0)", test_6_multiple_concurrent_instances),
        ("Tauri Webview CORS Origins", test_7_tauri_cors_origins),
        ("Fixed Port Binding", test_8_fixed_port_binding),
        ("Port Conflict Error Handling", test_9_port_in_use_error_handling),
        ("Handshake Write Ordering (Race Condition)", test_10_handshake_write_ordering),
    ]

    results = {}
    for name, fn in tests:
        try:
            passed, details = fn()
            results[name] = (passed, details)
        except Exception as e:
            results[name] = (False, f"Exception: {str(e)}")

    print("\n=================================================================")
    print(" EMPIRICAL STRESS TEST RESULTS SUMMARY                          ")
    print("=================================================================")
    all_passed = True
    for test_name, (passed, details) in results.items():
        status_str = "[PASS]" if passed else "[FAIL]"
        print(f"{status_str:6} {test_name}: {details}")
        if not passed:
            all_passed = False

    print("=================================================================")
    print(f"Overall status: {'ALL TESTS PASSED' if all_passed else 'FAILURES DETECTED'}")
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
