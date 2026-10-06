#!/usr/bin/env python3
"""Challenger 2 Empirical Stress Test Harness for Standalone Sidecar Binary.

Target: binaries/outlaw-forge-api.exe
Adversarial Challenges:
1. Rapid Restarts on Dynamic Port 0 (5 consecutive spawns and teardowns)
2. Immediate Port Release Verification (Fixed port re-bind < 500ms after tree termination)
3. Non-Standard Host Bindings (--host 0.0.0.0, --host localhost, invalid host with proper cold-start budget)
4. Malformed Arguments and Edge Case Inputs (--unknown-flag-xyz, --port invalid)
5. Concurrent Binary Instances on Port 0 (3 simultaneous binary processes)
6. Pre-existing Handshake File Overwrite and Integrity
7. High-Rate Health Check Burst (100 rapid requests)
8. Job Object Zero-Zombie Containment (Win32 Job Object kernel kill guarantee)
"""

import ctypes
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
BINARY_PATH = REPO_ROOT / "binaries" / "outlaw-forge-api.exe"
DIST_BINARY_PATH = REPO_ROOT / "dist" / "outlaw-forge-api.exe"

kernel32 = ctypes.windll.kernel32 if sys.platform == "win32" else None
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
JobObjectExtendedLimitInformation = 9


def create_job_object():
    if sys.platform != "win32":
        return None
    job = kernel32.CreateJobObjectW(None, None)
    if not job:
        return None

    class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_int64),
            ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", ctypes.c_uint32),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", ctypes.c_uint32),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", ctypes.c_uint32),
            ("SchedulingClass", ctypes.c_uint32),
        ]

    class IO_COUNTERS(ctypes.Structure):
        _fields_ = [
            ("ReadOperationCount", ctypes.c_uint64),
            ("WriteOperationCount", ctypes.c_uint64),
            ("OtherOperationCount", ctypes.c_uint64),
            ("ReadTransferCount", ctypes.c_uint64),
            ("WriteTransferCount", ctypes.c_uint64),
            ("OtherTransferCount", ctypes.c_uint64),
        ]

    class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
            ("IoInfo", IO_COUNTERS),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryLimit", ctypes.c_size_t),
            ("PeakJobMemoryLimit", ctypes.c_size_t),
        ]

    info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
    info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    kernel32.SetInformationJobObject(
        job,
        JobObjectExtendedLimitInformation,
        ctypes.byref(info),
        ctypes.sizeof(info),
    )
    return job


def assign_pid_to_job(job, pid: int) -> bool:
    if not job or sys.platform != "win32":
        return False
    h_proc = kernel32.OpenProcess(0x0100 | 0x0001, False, pid)
    if not h_proc:
        return False
    assigned = bool(kernel32.AssignProcessToJobObject(job, h_proc))
    kernel32.CloseHandle(h_proc)
    return assigned


def is_pid_alive(pid: int) -> bool:
    """Check whether a process PID is currently alive on Windows."""
    if sys.platform != "win32":
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    h_proc = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h_proc:
        return False
    exit_code = ctypes.c_ulong()
    kernel32.GetExitCodeProcess(h_proc, ctypes.byref(exit_code))
    kernel32.CloseHandle(h_proc)
    STILL_ACTIVE = 259
    return exit_code.value == STILL_ACTIVE


def find_free_port(host: str = "127.0.0.1") -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, 0))
        return int(s.getsockname()[1])


def is_port_bindable(port: int, host: str = "127.0.0.1") -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            # Do NOT use SO_REUSEADDR on Windows to strictly ensure no other process is listening
            if sys.platform != "win32":
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((host, port))
            return True
    except OSError:
        return False


def terminate_process_tree(proc: subprocess.Popen, job_handle=None):
    """Terminates process and all descendant worker processes."""
    if job_handle and sys.platform == "win32":
        kernel32.CloseHandle(job_handle)
    if proc and proc.pid:
        pid = proc.pid
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            proc.terminate()
        try:
            proc.wait(timeout=2.0)
        except Exception:
            pass


def spawn_sidecar(
    exe_path: Path,
    args: List[str],
    timeout: float = 30.0,
    use_job: bool = True,
) -> Tuple[Optional[subprocess.Popen], Optional[int], Any, str, str]:
    """Spawn binary and wait for port in stdout."""
    cmd = [str(exe_path)] + args
    job = create_job_object() if use_job else None

    proc = subprocess.Popen(
        cmd,
        cwd=str(REPO_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

    if job and proc.pid:
        assign_pid_to_job(job, proc.pid)

    port = None
    stdout_lines: List[str] = []
    stderr_lines: List[str] = []

    def capture_stderr():
        try:
            for line in iter(proc.stderr.readline, ""):
                stderr_lines.append(line)
        except Exception:
            pass

    t_err = threading.Thread(target=capture_stderr, daemon=True)
    t_err.start()

    t_start = time.time()
    while time.time() - t_start < timeout:
        if proc.poll() is not None:
            break
        line = proc.stdout.readline()
        if line:
            stdout_lines.append(line)
            m = re.search(r"(?:OUTLAW_FORGE_API_READY:port=(\d+)|HEALTH_OK:\s*PORT=(\d+))", line)
            if m:
                port = int(m.group(1) or m.group(2))
                break
        else:
            time.sleep(0.04)

    return proc, port, job, "".join(stdout_lines), "".join(stderr_lines)


def http_get(url: str, timeout: float = 3.0) -> Tuple[int, dict]:
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return resp.status, data
    except urllib.error.HTTPError as e:
        data = json.loads(e.read().decode("utf-8")) if e.fp else {}
        return e.code, data
    except Exception as e:
        return 0, {"error": str(e)}


# =====================================================================
# CHALLENGE TESTS
# =====================================================================

def challenge_1_rapid_restarts_port_0(iterations: int = 5) -> Tuple[bool, str]:
    """Test 1: Rapid 5-cycle restart loop on dynamic port 0 against standalone binary."""
    print(f"\n--- Challenge 1: Rapid Restarts on Dynamic Port 0 ({iterations} cycles) ---")
    bound_ports = []
    durations = []

    for i in range(iterations):
        t0 = time.perf_counter()
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            db_path = tmp_path / f"cycle_{i}.db"
            storage_dir = tmp_path / "storage"
            hs_file = tmp_path / "hs.json"

            proc, port, job, out, err = spawn_sidecar(
                BINARY_PATH,
                [
                    "--port", "0",
                    "--host", "127.0.0.1",
                    "--db-path", str(db_path),
                    "--storage-dir", str(storage_dir),
                    "--handshake-file", str(hs_file),
                ],
                timeout=35.0,
            )

            try:
                if port is None or proc.poll() is not None:
                    return False, f"Cycle {i}: Failed to acquire port. Exit={proc.poll()}, Stderr={err[:200]}"

                bound_ports.append(port)

                # Query /health
                status, body = http_get(f"http://127.0.0.1:{port}/health")
                if status != 200 or body.get("status") != "healthy":
                    return False, f"Cycle {i}: Unhealthy on port {port}: status={status}, body={body}"

                pid = proc.pid
                terminate_process_tree(proc, job)

                # Check port release
                time.sleep(0.1)
                if not is_port_bindable(port):
                    return False, f"Cycle {i}: Port {port} not freed immediately"

                dt = time.perf_counter() - t0
                durations.append(dt)
                print(f"  Cycle {i+1}/{iterations}: Bound port {port}, HTTP 200 OK, terminated & freed in {dt:.2f}s")
            finally:
                terminate_process_tree(proc, job)

    avg_dt = sum(durations) / len(durations)
    return True, f"Completed {iterations} rapid restart cycles (avg {avg_dt:.2f}s/cycle). Ports: {bound_ports}"


def challenge_2_immediate_port_release() -> Tuple[bool, str]:
    """Test 2: Terminating process tree releases fixed port binding within 500ms."""
    print("\n--- Challenge 2: Fixed Port Immediate Release Verification (< 500ms) ---")
    fixed_port = find_free_port()

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        db_path = tmp_path / "fixed.db"

        proc, port, job, out, err = spawn_sidecar(
            BINARY_PATH,
            [
                "--port", str(fixed_port),
                "--host", "127.0.0.1",
                "--db-path", str(db_path),
            ],
            timeout=35.0,
        )

        try:
            if port != fixed_port:
                return False, f"Expected port {fixed_port}, got {port}"

            status, body = http_get(f"http://127.0.0.1:{fixed_port}/health")
            if status != 200:
                return False, f"Failed health check on fixed port {fixed_port}"

            # Terminate process tree and time port release
            pid = proc.pid
            t_term = time.perf_counter()
            terminate_process_tree(proc, job)

            # Check port release latency
            released = False
            release_ms = 0.0
            for attempt in range(20):
                if is_port_bindable(fixed_port):
                    released = True
                    release_ms = (time.perf_counter() - t_term) * 1000.0
                    break
                time.sleep(0.025)

            if not released:
                return False, f"Port {fixed_port} was NOT released within 500ms after tree terminate"

            print(f"  Port {fixed_port} released in {release_ms:.1f}ms after tree terminate (PID {pid})")
            return True, f"Port {fixed_port} released in {release_ms:.1f}ms (< 500ms target)"
        finally:
            terminate_process_tree(proc, job)


def challenge_3_non_standard_host_bindings() -> Tuple[bool, str]:
    """Test 3: Non-standard host bindings: 0.0.0.0, localhost, and invalid host."""
    print("\n--- Challenge 3: Non-Standard Host Bindings ---")

    # 3A: Bind 0.0.0.0 on dynamic port 0
    print("  Testing --host 0.0.0.0 with --port 0...")
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "all_hosts.db"
        proc, port, job, out, err = spawn_sidecar(
            BINARY_PATH,
            ["--host", "0.0.0.0", "--port", "0", "--db-path", str(db_path)],
            timeout=35.0,
        )
        try:
            if port is None:
                return False, f"Failed to bind --host 0.0.0.0. Stderr: {err[:200]}"

            print(f"  Bound 0.0.0.0 on dynamic port {port}")
            status, body = http_get(f"http://127.0.0.1:{port}/health")
            if status != 200 or body.get("status") != "healthy":
                return False, f"Failed to reach 0.0.0.0 server via 127.0.0.1:{port}: {status}"
            print("  Successfully queried 0.0.0.0 listener via 127.0.0.1 loopback")
        finally:
            terminate_process_tree(proc, job)

    # 3B: Bind localhost on dynamic port 0
    print("  Testing --host localhost with --port 0...")
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "localhost.db"
        proc, port, job, out, err = spawn_sidecar(
            BINARY_PATH,
            ["--host", "localhost", "--port", "0", "--db-path", str(db_path)],
            timeout=35.0,
        )
        try:
            if port is None:
                return False, f"Failed to bind --host localhost. Stderr: {err[:200]}"

            print(f"  Bound localhost on dynamic port {port}")
            status, body = http_get(f"http://localhost:{port}/health")
            if status != 200 or body.get("status") != "healthy":
                return False, f"Failed to reach localhost server: {status}"
        finally:
            terminate_process_tree(proc, job)

    # 3C: Invalid IP host binding (with realistic 35s cold-start budget)
    print("  Testing invalid host IP: --host 999.999.999.999...")
    t0 = time.perf_counter()
    proc_bad = subprocess.Popen(
        [str(BINARY_PATH), "--host", "999.999.999.999", "--port", "0"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        out_bad, err_bad = proc_bad.communicate(timeout=35.0)
        dt = time.perf_counter() - t0
        print(f"  Exit code for invalid host: {proc_bad.returncode} in {dt:.2f}s")
        if proc_bad.returncode == 0:
            return False, "Binary exited with code 0 on invalid host 999.999.999.999!"
        print("  Binary cleanly failed with non-zero exit code on invalid host (OK)")
    except subprocess.TimeoutExpired:
        terminate_process_tree(proc_bad)
        return False, "Binary hung on invalid host binding!"

    return True, "0.0.0.0 bound, localhost bound, invalid host rejected cleanly"


def challenge_4_malformed_arguments() -> Tuple[bool, str]:
    """Test 4: Malformed CLI arguments and unrecognized flags (with 35s cold-start budget)."""
    print("\n--- Challenge 4: Malformed Arguments & Edge Case Inputs ---")

    # 4A: Unknown option --unknown-flag
    print("  Testing unknown argument flag...")
    t0 = time.perf_counter()
    proc = subprocess.Popen(
        [str(BINARY_PATH), "--unknown-flag-xyz"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        out, err = proc.communicate(timeout=35.0)
        dt = time.perf_counter() - t0
        print(f"  Unknown flag exit code: {proc.returncode} in {dt:.2f}s (expected 2)")
        if proc.returncode != 2:
            return False, f"Expected argparse exit code 2 on unknown flag, got {proc.returncode}"
        if "unrecognized arguments" not in err:
            return False, f"Expected 'unrecognized arguments' in stderr, got: {err}"
        print("  Unknown flag properly rejected with exit code 2")
    except subprocess.TimeoutExpired:
        terminate_process_tree(proc)
        return False, "Binary hung on unknown flag"

    # 4B: Invalid port string --port abc
    print("  Testing non-numeric port argument...")
    t0 = time.perf_counter()
    proc = subprocess.Popen(
        [str(BINARY_PATH), "--port", "abc"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        out, err = proc.communicate(timeout=35.0)
        dt = time.perf_counter() - t0
        print(f"  Invalid port string exit code: {proc.returncode} in {dt:.2f}s (expected 2)")
        if proc.returncode != 2:
            return False, f"Expected argparse exit code 2 on invalid port type, got {proc.returncode}"
        print("  Invalid port string properly rejected with exit code 2")
    except subprocess.TimeoutExpired:
        terminate_process_tree(proc)
        return False, "Binary hung on invalid port string"

    # 4C: Deep nested non-existent storage-dir
    print("  Testing deep nested non-existent storage and db directory paths...")
    with tempfile.TemporaryDirectory() as tmp_dir:
        deep_dir = Path(tmp_dir) / "level1" / "level2" / "storage"
        deep_db = Path(tmp_dir) / "level1" / "level2" / "test.db"
        proc_deep, port_deep, job_deep, _, err_deep = spawn_sidecar(
            BINARY_PATH,
            [
                "--port", "0",
                "--storage-dir", str(deep_dir),
                "--db-path", str(deep_db),
            ],
            timeout=35.0,
        )
        try:
            if port_deep is None:
                return False, f"Failed to start with nested non-existent directory. Stderr: {err_deep[:200]}"
            print(f"  Binary automatically created and mounted nested paths on port {port_deep}")
            status, _ = http_get(f"http://127.0.0.1:{port_deep}/health")
            if status != 200:
                return False, "Health check failed with nested paths"
            if not deep_db.exists():
                return False, "Database file was not created in nested path"
        finally:
            terminate_process_tree(proc_deep, job_deep)

    return True, "Unknown flags rejected (code 2), invalid port rejected (code 2), nested paths handled"


def challenge_5_concurrent_binary_instances() -> Tuple[bool, str]:
    """Test 5: 3 concurrent binary processes on dynamic port 0."""
    print("\n--- Challenge 5: 3 Concurrent Binary Instances on Port 0 ---")
    procs = []
    ports = []
    jobs = []

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        try:
            for i in range(3):
                db_p = tmp_path / f"inst_{i}.db"
                hs_p = tmp_path / f"inst_{i}.json"
                proc, port, job, _, err = spawn_sidecar(
                    BINARY_PATH,
                    ["--port", "0", "--db-path", str(db_p), "--handshake-file", str(hs_p)],
                    timeout=35.0,
                )
                if port is None:
                    return False, f"Binary instance {i} failed to bind. Stderr: {err[:200]}"
                procs.append(proc)
                ports.append(port)
                jobs.append(job)
                print(f"  Instance {i}: PID {proc.pid} bound port {port}")

            if len(set(ports)) != 3:
                return False, f"Port collision across binary instances: {ports}"

            for i, p in enumerate(ports):
                st, bd = http_get(f"http://127.0.0.1:{p}/health")
                if st != 200 or bd.get("status") != "healthy":
                    return False, f"Instance {i} unhealthy on port {p}: {st}"

            print("  All 3 instances verified healthy simultaneously.")
            return True, f"3 concurrent binary instances running on unique ports {ports}"
        finally:
            for p, j in zip(procs, jobs):
                terminate_process_tree(p, j)


def challenge_6_handshake_file_overwrite() -> Tuple[bool, str]:
    """Test 6: Pre-existing stale handshake file is cleanly overwritten with correct port."""
    print("\n--- Challenge 6: Pre-existing Handshake File Overwrite ---")
    with tempfile.TemporaryDirectory() as tmp_dir:
        hs_file = Path(tmp_dir) / "handshake.json"
        hs_file.write_text(json.dumps({"status": "stale", "port": 99999}), encoding="utf-8")

        proc, port, job, _, err = spawn_sidecar(
            BINARY_PATH,
            ["--port", "0", "--handshake-file", str(hs_file)],
            timeout=35.0,
        )
        try:
            if port is None:
                return False, f"Failed to spawn binary. Stderr: {err[:200]}"

            time.sleep(0.1)
            content = json.loads(hs_file.read_text(encoding="utf-8"))
            if content.get("status") != "healthy" or content.get("port") != port:
                return False, f"Handshake file not properly overwritten: {content}"

            print(f"  Handshake file overwritten with live status: {content}")
            return True, f"Pre-existing handshake file correctly updated to port {port}"
        finally:
            terminate_process_tree(proc, job)


def challenge_7_health_request_burst() -> Tuple[bool, str]:
    """Test 7: Rapid burst of 100 GET /health requests against binary."""
    print("\n--- Challenge 7: 100 Request Health Burst Stress Test ---")
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_p = Path(tmp_dir) / "burst.db"
        proc, port, job, _, err = spawn_sidecar(
            BINARY_PATH,
            ["--port", "0", "--db-path", str(db_p)],
            timeout=35.0,
        )
        try:
            if port is None:
                return False, f"Failed to start binary. Stderr: {err[:200]}"

            url = f"http://127.0.0.1:{port}/health"
            t0 = time.perf_counter()
            latencies = []
            errors = 0

            for _ in range(100):
                t_req = time.perf_counter()
                st, body = http_get(url, timeout=1.0)
                lat = (time.perf_counter() - t_req) * 1000.0
                if st == 200 and body.get("status") == "healthy":
                    latencies.append(lat)
                else:
                    errors += 1

            total_sec = time.perf_counter() - t0
            rps = 100.0 / total_sec
            avg_lat = sum(latencies) / len(latencies) if latencies else 0.0
            max_lat = max(latencies) if latencies else 0.0

            print(f"  Completed 100 requests in {total_sec:.3f}s ({rps:.0f} req/s)")
            print(f"  Latencies: avg={avg_lat:.2f}ms, max={max_lat:.2f}ms, errors={errors}")

            if errors > 0:
                return False, f"Encountered {errors}/100 errors during burst"
            if avg_lat > 50.0:
                return False, f"Average latency too high: {avg_lat:.2f}ms"

            return True, f"100/100 requests passed in {total_sec:.2f}s ({rps:.0f} req/s, avg {avg_lat:.2f}ms)"
        finally:
            terminate_process_tree(proc, job)


def challenge_8_job_object_zero_zombies() -> Tuple[bool, str]:
    """Test 8: Strict Windows Job Object containment guarantees ZERO ZOMBIES."""
    print("\n--- Challenge 8: Win32 Job Object Zero-Zombie Containment Guarantee ---")
    if sys.platform != "win32":
        return True, "Skipped: Non-Windows platform"

    job = create_job_object()
    if not job:
        return False, "Failed to create Win32 Job Object"

    with tempfile.TemporaryDirectory() as tmp_dir:
        db_p = Path(tmp_dir) / "job_test.db"
        cmd = [str(BINARY_PATH), "--port", "0", "--db-path", str(db_p)]
        proc = subprocess.Popen(
            cmd,
            cwd=str(REPO_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

        try:
            assigned = assign_pid_to_job(job, proc.pid)
            if not assigned:
                return False, f"Failed to assign PID {proc.pid} to Job Object"

            # Wait for ready
            port = None
            t_start = time.time()
            while time.time() - t_start < 35.0:
                line = proc.stdout.readline()
                if "READY" in line:
                    m = re.search(r"port=(\d+)", line)
                    if m:
                        port = int(m.group(1))
                        break
                time.sleep(0.05)

            if port is None:
                return False, "Failed to detect port in Job Object test"

            print(f"  Sidecar running in Job Object on dynamic port {port}")
            status, _ = http_get(f"http://127.0.0.1:{port}/health")
            if status != 200:
                return False, "Sidecar unhealthy inside Job Object"

            # Now close Job Object handle ONLY (do NOT call taskkill or proc.terminate)
            print("  Closing Job Object handle...")
            kernel32.CloseHandle(job)
            job = None  # prevent double close

            # Give OS kernel 1 second to terminate all processes in job
            time.sleep(1.0)

            # Check if any outlaw-forge-api processes remain
            cmd_ps = "Get-Process -Name *outlaw* -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id"
            res = subprocess.run(["powershell", "-Command", cmd_ps], capture_output=True, text=True)
            remaining_pids = res.stdout.strip()

            if remaining_pids:
                return False, f"ZOMBIE LEAK: Remaining outlaw processes: {remaining_pids}"

            print("  Kernel cleanly eliminated all sidecar processes upon Job Object close.")
            return True, "Win32 Job Object achieved 100% zero-zombie containment"
        finally:
            if job:
                kernel32.CloseHandle(job)
            if proc.poll() is None:
                terminate_process_tree(proc)


def main():
    print("=" * 74)
    print(" CHALLENGER 2: ADVERSARIAL STRESS TEST HARNESS (v2)")
    print(f" Target Binary: {BINARY_PATH}")
    print("=" * 74)

    if not BINARY_PATH.exists():
        print(f"[FAIL] Target binary not found at: {BINARY_PATH}")
        sys.exit(1)

    tests = [
        ("Rapid Restarts on Dynamic Port 0 (5 cycles)", challenge_1_rapid_restarts_port_0),
        ("Immediate Port Release Verification (< 500ms)", challenge_2_immediate_port_release),
        ("Non-Standard Host Bindings (0.0.0.0, localhost, invalid)", challenge_3_non_standard_host_bindings),
        ("Malformed Arguments & Flag Rejection", challenge_4_malformed_arguments),
        ("3 Concurrent Binary Instances on Port 0", challenge_5_concurrent_binary_instances),
        ("Pre-existing Handshake File Overwrite", challenge_6_handshake_file_overwrite),
        ("100 Request Health Burst Stress Test", challenge_7_health_request_burst),
        ("Win32 Job Object Zero-Zombie Containment", challenge_8_job_object_zero_zombies),
    ]

    results = {}
    all_passed = True

    for name, fn in tests:
        try:
            passed, details = fn()
            results[name] = (passed, details)
        except Exception as ex:
            import traceback
            traceback.print_exc()
            results[name] = (False, f"Exception: {ex}")

        if not results[name][0]:
            all_passed = False

    print("\n" + "=" * 74)
    print(" CHALLENGER 2: EMPIRICAL STRESS TEST SUMMARY")
    print("=" * 74)
    for test_name, (passed, details) in results.items():
        tag = "[PASS]" if passed else "[FAIL]"
        print(f"  {tag:6} {test_name:48} {details}")

    print("=" * 74)
    print(f" Verdict: {'ALL ADVERSARIAL CHALLENGES PASSED (100%)' if all_passed else 'CHALLENGE FAILURES DETECTED'}")
    print("=" * 74)
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
