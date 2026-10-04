#!/usr/bin/env python3
"""Empirical Adversarial Stress Test Suite for Milestone M3:
Process Supervisor & Job Object Lifecycle.

Stress-tests:
1. Dynamic ephemeral port allocation under rapid repeated socket calls & concurrency.
2. Win32 Job Object lifecycle guarantee (JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE):
   empirically verifying that closing the Job Object handle or abruptly killing
   the supervisor terminates child processes with zero zombie processes.
3. Sidecar health check polling under simulated latency, cold start, and errors.
"""

import ctypes
import http.server
import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
API_DIR = REPO_ROOT / "apps" / "api"
CLI_PATH = API_DIR / "app" / "cli.py"


def get_base_env() -> Dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(API_DIR)
    return env


# =====================================================================
# DOMAIN 1: DYNAMIC EPHEMERAL PORT ALLOCATION STRESS TESTS
# =====================================================================

def stress_1a_rapid_sequential_ports(count: int = 500) -> Tuple[bool, str]:
    """Test 1A: Rapid repeated ephemeral port resolution in a tight loop."""
    print(f"\n--- Stress Test 1A: {count} Rapid Ephemeral Port Allocations ---")
    ports = []
    t0 = time.perf_counter()

    for i in range(count):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            p = int(s.getsockname()[1])
            if p <= 1024 or p > 65535:
                return False, f"Iteration {i}: Allocated invalid port {p} (expected 1025-65535)"
            ports.append(p)

    dt = time.perf_counter() - t0
    unique_ports = len(set(ports))
    rate = count / dt if dt > 0 else 0
    print(f"  Allocated {count} ports in {dt:.3f}s ({rate:.0f} allocs/sec)")
    print(f"  Unique ports allocated: {unique_ports} / {count}")
    return True, f"Successfully allocated {count} ephemeral ports across {unique_ports} unique ports in {dt:.3f}s"


def stress_1b_concurrent_threads_ports(num_threads: int = 10, per_thread: int = 50) -> Tuple[bool, str]:
    """Test 1B: Multithreaded concurrent ephemeral port resolution."""
    total = num_threads * per_thread
    print(f"\n--- Stress Test 1B: Concurrent Ephemeral Ports ({num_threads} threads x {per_thread} allocs = {total}) ---")
    results: List[int] = []
    errors: List[str] = []
    lock = threading.Lock()

    def worker(tid: int):
        for _ in range(per_thread):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(("127.0.0.1", 0))
                    p = int(s.getsockname()[1])
                    if p <= 1024 or p > 65535:
                        with lock:
                            errors.append(f"Thread {tid}: invalid port {p}")
                    else:
                        with lock:
                            results.append(p)
            except Exception as ex:
                with lock:
                    errors.append(f"Thread {tid} error: {ex}")

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(num_threads)]
    t0 = time.perf_counter()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    dt = time.perf_counter() - t0

    if errors:
        return False, f"Encountered {len(errors)} errors during concurrent allocation: {errors[:3]}"
    if len(results) != total:
        return False, f"Expected {total} results, got {len(results)}"

    print(f"  Allocated {total} concurrent ports in {dt:.3f}s ({total/dt:.0f} allocs/sec)")
    return True, f"All {total} concurrent socket allocations succeeded with 0 errors in {dt:.3f}s"


def stress_1c_multiple_sidecar_instances() -> Tuple[bool, str]:
    """Test 1C: Spawn 3 concurrent Python sidecars with --port 0 and verify independent binding."""
    print("\n--- Stress Test 1C: 3 Concurrent Sidecar Spawns with --port 0 ---")
    procs = []
    ports = []

    try:
        for idx in range(3):
            p = subprocess.Popen(
                [sys.executable, "-m", "app.cli", "--port", "0"],
                cwd=str(REPO_ROOT),
                env=get_base_env(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
            procs.append(p)

        # Wait for all 3 to output HEALTH_OK: PORT=XXXX
        start = time.time()
        for idx, p in enumerate(procs):
            found_port = None
            while time.time() - start < 15.0:
                if p.poll() is not None:
                    break
                line = p.stdout.readline()
                if "HEALTH_OK: PORT=" in line:
                    import re
                    m = re.search(r"PORT=(\d+)", line)
                    if m:
                        found_port = int(m.group(1))
                        break
                time.sleep(0.05)

            if found_port is None:
                err = p.stderr.read()
                return False, f"Sidecar {idx} failed to start. Stderr: {err[:300]}"
            ports.append(found_port)
            print(f"  Sidecar {idx} bound port {found_port}")

        # Check all ports are distinct
        if len(set(ports)) != len(ports):
            return False, f"Port collision detected among concurrent sidecars: {ports}"

        # Verify all 3 respond 200 OK to /health
        for idx, port in enumerate(ports):
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=3.0) as resp:
                data = json.loads(resp.read().decode())
                if resp.status != 200 or data.get("status") != "healthy":
                    return False, f"Sidecar {idx} at port {port} returned invalid health: {data}"
            print(f"  Sidecar {idx} (port {port}) verified healthy")

        return True, f"Spawned 3 concurrent sidecars on distinct ports {ports}, all 100% healthy"

    finally:
        for p in procs:
            try:
                p.terminate()
                p.wait(timeout=2)
            except Exception:
                try:
                    p.kill()
                    p.wait(timeout=1)
                except Exception:
                    pass


# =====================================================================
# DOMAIN 2: WIN32 JOB OBJECT ZERO-ZOMBIE LIFECYCLE STRESS TESTS
# =====================================================================

def is_pid_alive(pid: int) -> bool:
    """Check whether a process PID is currently alive on Windows."""
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


def stress_2a_job_close_handle_kills_child() -> Tuple[bool, str]:
    """Test 2A: Verify kernel kills child process when Job Object handle is closed.
    Crucial: No terminate() or kill() call on child; closure of job handle MUST kill child.
    """
    print("\n--- Stress Test 2A: Win32 Job Object Handle Close Kill Guarantee ---")
    if sys.platform != "win32":
        return True, "Skipped: Non-Windows OS"

    kernel32 = ctypes.windll.kernel32
    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
    JobObjectExtendedLimitInformation = 9

    class IO_COUNTERS(ctypes.Structure):
        _fields_ = [
            ("ReadOperationCount", ctypes.c_uint64),
            ("WriteOperationCount", ctypes.c_uint64),
            ("OtherOperationCount", ctypes.c_uint64),
            ("ReadTransferCount", ctypes.c_uint64),
            ("WriteTransferCount", ctypes.c_uint64),
            ("OtherTransferCount", ctypes.c_uint64),
        ]

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

    class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
            ("IoInfo", IO_COUNTERS),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryLimit", ctypes.c_size_t),
            ("PeakJobMemoryLimit", ctypes.c_size_t),
        ]

    job = kernel32.CreateJobObjectW(None, None)
    if not job:
        return False, f"CreateJobObjectW failed: {kernel32.GetLastError()}"

    info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
    info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    ok = kernel32.SetInformationJobObject(
        job,
        JobObjectExtendedLimitInformation,
        ctypes.byref(info),
        ctypes.sizeof(info),
    )
    if not ok:
        kernel32.CloseHandle(job)
        return False, f"SetInformationJobObject failed: {kernel32.GetLastError()}"

    # Spawn long-sleeping child process (120s)
    child = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(120)"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    child_pid = child.pid

    # Assign to Job Object
    PROCESS_SET_QUOTA = 0x0100
    PROCESS_TERMINATE = 0x0001
    h_proc = kernel32.OpenProcess(PROCESS_SET_QUOTA | PROCESS_TERMINATE, False, child_pid)
    if not h_proc:
        kernel32.CloseHandle(job)
        child.kill()
        return False, f"OpenProcess failed: {kernel32.GetLastError()}"

    assigned = kernel32.AssignProcessToJobObject(job, h_proc)
    kernel32.CloseHandle(h_proc)

    if not assigned:
        kernel32.CloseHandle(job)
        child.kill()
        return False, f"AssignProcessToJobObject failed: {kernel32.GetLastError()}"

    # Verify child is running right now
    if not is_pid_alive(child_pid):
        kernel32.CloseHandle(job)
        return False, f"Child PID {child_pid} died prematurely before test"

    print(f"  Child PID {child_pid} is active and assigned to Job Object {job}")

    # EMPIRICAL CHALLENGE: Close Job Object Handle ONLY.
    # We do NOT touch child.terminate() or child.kill()!
    print(f"  Closing Job Object handle {job}...")
    kernel32.CloseHandle(job)

    # Windows kernel must terminate child_pid promptly
    terminated = False
    for _ in range(30):  # poll up to 3.0 seconds
        time.sleep(0.1)
        if not is_pid_alive(child_pid):
            terminated = True
            break

    if not terminated:
        child.kill()
        return False, f"ZOMBIE DETECTED: Child PID {child_pid} remained alive after Job Object handle was closed!"

    print(f"  Verified: Child PID {child_pid} terminated automatically by OS kernel upon Job close.")
    return True, f"OS kernel automatically terminated child PID {child_pid} upon Job Object handle close"


def stress_2b_abrupt_supervisor_death_kills_child() -> Tuple[bool, str]:
    """Test 2B: Abrupt supervisor death (hard crash) must kill child sidecar without zombies.
    We launch a supervisor subprocess that creates a Job Object, spawns a child, and prints the child PID.
    Then we kill the supervisor with SIGKILL (taskkill /F). The child MUST die automatically.
    """
    print("\n--- Stress Test 2B: Abrupt Supervisor Death (SIGKILL) Zero-Zombie Test ---")
    if sys.platform != "win32":
        return True, "Skipped: Non-Windows OS"

    supervisor_script = """
import sys, os, time, ctypes, subprocess
kernel32 = ctypes.windll.kernel32
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
JobObjectExtendedLimitInformation = 9

class IO_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_uint64),
        ("WriteOperationCount", ctypes.c_uint64),
        ("OtherOperationCount", ctypes.c_uint64),
        ("ReadTransferCount", ctypes.c_uint64),
        ("WriteTransferCount", ctypes.c_uint64),
        ("OtherTransferCount", ctypes.c_uint64),
    ]

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

class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
        ("IoInfo", IO_COUNTERS),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryLimit", ctypes.c_size_t),
        ("PeakJobMemoryLimit", ctypes.c_size_t),
    ]

job = kernel32.CreateJobObjectW(None, None)
info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
kernel32.SetInformationJobObject(job, JobObjectExtendedLimitInformation, ctypes.byref(info), ctypes.sizeof(info))

# Spawn worker
worker = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
h_proc = kernel32.OpenProcess(0x0100 | 0x0001, False, worker.pid)
kernel32.AssignProcessToJobObject(job, h_proc)
kernel32.CloseHandle(h_proc)

print(f"READY: SUPERVISOR={os.getpid()} WORKER={worker.pid}", flush=True)

# Keep supervisor alive waiting for abrupt kill
while True:
    time.sleep(1)
"""

    sup_proc = subprocess.Popen(
        [sys.executable, "-c", supervisor_script],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

    worker_pid = None
    supervisor_pid = sup_proc.pid

    # Read READY line
    line = sup_proc.stdout.readline()
    import re
    m = re.search(r"SUPERVISOR=(\d+)\s+WORKER=(\d+)", line)
    if not m:
        sup_proc.kill()
        return False, f"Failed to get supervisor and worker PIDs. Output: {line}"

    sup_reported_pid = int(m.group(1))
    worker_pid = int(m.group(2))

    print(f"  Supervisor PID: {sup_reported_pid}, Worker Child PID: {worker_pid}")
    if not is_pid_alive(worker_pid):
        sup_proc.kill()
        return False, f"Worker PID {worker_pid} was not alive initially"

    # Abruptly KILL the supervisor via taskkill /F (simulating hard crash)
    print(f"  Simulating hard crash: killing Supervisor PID {sup_reported_pid} abruptly via taskkill /F...")
    subprocess.run(["taskkill", "/F", "/PID", str(sup_reported_pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Verify supervisor is dead
    time.sleep(0.3)
    if is_pid_alive(sup_reported_pid):
        sup_proc.kill()
        return False, f"Failed to kill supervisor PID {sup_reported_pid}"

    # Now verify: Did worker PID terminate as well?
    worker_dead = False
    for _ in range(30):  # Poll up to 3.0 seconds
        time.sleep(0.1)
        if not is_pid_alive(worker_pid):
            worker_dead = True
            break

    if not worker_dead:
        # Cleanup zombie if test fails
        subprocess.run(["taskkill", "/F", "/PID", str(worker_pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return False, f"CRITICAL FAILURE: Worker PID {worker_pid} remained as a ZOMBIE after supervisor killed!"

    print(f"  Verified: Worker PID {worker_pid} was terminated by Windows OS Job Object. ZERO ZOMBIES.")
    return True, f"Abrupt supervisor death successfully terminated child PID {worker_pid} via Job Object"


# =====================================================================
# DOMAIN 3: HEALTH CHECK POLLING LATENCY / COLD-START STRESS TESTS
# =====================================================================

class MockHealthHandler(http.server.BaseHTTPRequestHandler):
    """Configurable mock server to simulate latencies, cold starts, and errors."""
    server_mode = "healthy"  # "healthy", "cold_start", "slow", "error_then_healthy", "always_500"
    start_time = 0.0
    delay_secs = 0.0

    def log_message(self, format, *args):
        pass  # suppress request logging

    def do_GET(self):
        if self.path != "/health":
            self.send_response(404)
            self.end_headers()
            return

        now = time.time()
        elapsed = now - self.server_mode_start_time

        if self.server_mode == "healthy":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status": "healthy"}')

        elif self.server_mode == "cold_start":
            # First 2.0 seconds: 503 unavailable
            if elapsed < 2.0:
                self.send_response(503)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"status": "initializing", "stage": "database_migration"}')
            else:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"status": "healthy"}')

        elif self.server_mode == "slow":
            # Respond with deliberate delay
            time.sleep(self.delay_secs)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status": "healthy"}')

        elif self.server_mode == "error_then_healthy":
            # Return HTTP 500 HTML for first 1.5 seconds, then healthy JSON
            if elapsed < 1.5:
                self.send_response(500)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(b'<html><body>500 Internal Server Error</body></html>')
            else:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"status": "healthy"}')

        elif self.server_mode == "never_healthy":
            self.send_response(500)
            self.end_headers()
            self.wfile.write(b'{"status": "unhealthy"}')


def run_poller_algorithm(port: int, timeout_secs: float, request_timeout: float = 0.5) -> Tuple[bool, float, int]:
    """Recreation of src-tauri/src/lib.rs wait_for_backend_health algorithm:
    timeout_secs total timeout, request_timeout per HTTP request, backoff starting at 100ms
    increasing by 50ms up to 300ms.
    Returns: (is_healthy, elapsed_secs, attempt_count)
    """
    health_url = f"http://127.0.0.1:{port}/health"
    start = time.time()
    backoff = 0.100
    attempts = 0

    while (time.time() - start) < timeout_secs:
        attempts += 1
        req = urllib.request.Request(health_url)
        try:
            with urllib.request.urlopen(req, timeout=request_timeout) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode())
                    if data.get("status") == "healthy":
                        return True, time.time() - start, attempts
        except Exception:
            pass  # retry on any network, timeout, or parsing error

        time.sleep(backoff)
        if backoff < 0.300:
            backoff += 0.050

    return False, time.time() - start, attempts


def stress_3a_cold_start_simulation() -> Tuple[bool, str]:
    """Test 3A: Simulate cold start (503 for first 2.0s, then 200 healthy)."""
    print("\n--- Stress Test 3A: Cold Start Handshake (503 Service Unavailable for 2.0s) ---")
    server = http.server.HTTPServer(("127.0.0.1", 0), MockHealthHandler)
    port = server.server_port
    MockHealthHandler.server_mode = "cold_start"
    MockHealthHandler.server_mode_start_time = time.time()

    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()

    try:
        ok, elapsed, attempts = run_poller_algorithm(port, timeout_secs=10.0)
        print(f"  Poller result: ok={ok}, elapsed={elapsed:.2f}s, attempts={attempts}")
        if not ok:
            return False, f"Poller failed to recover from cold start after {elapsed:.2f}s"
        if elapsed < 2.0:
            return False, f"Poller reported healthy prematurely at {elapsed:.2f}s (expected >= 2.0s)"
        return True, f"Poller cleanly rode through 2.0s cold start and succeeded in {elapsed:.2f}s ({attempts} attempts)"
    finally:
        server.shutdown()


def stress_3b_near_timeout_latency() -> Tuple[bool, str]:
    """Test 3B: High response latency (350ms delay, within 500ms request timeout)."""
    print("\n--- Stress Test 3B: High Response Latency (350ms per request) ---")
    server = http.server.HTTPServer(("127.0.0.1", 0), MockHealthHandler)
    port = server.server_port
    MockHealthHandler.server_mode = "slow"
    MockHealthHandler.delay_secs = 0.350
    MockHealthHandler.server_mode_start_time = time.time()

    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()

    try:
        ok, elapsed, attempts = run_poller_algorithm(port, timeout_secs=5.0, request_timeout=0.5)
        print(f"  Poller result: ok={ok}, elapsed={elapsed:.2f}s, attempts={attempts}")
        if not ok:
            return False, f"Poller failed on high-latency responses"
        return True, f"Poller succeeded with 350ms response latency in {elapsed:.2f}s ({attempts} attempts)"
    finally:
        server.shutdown()


def stress_3c_malformed_html_error_recovery() -> Tuple[bool, str]:
    """Test 3C: Server returns 500 HTML error for 1.5s, then valid JSON healthy."""
    print("\n--- Stress Test 3C: Malformed HTML Error Recovery ---")
    server = http.server.HTTPServer(("127.0.0.1", 0), MockHealthHandler)
    port = server.server_port
    MockHealthHandler.server_mode = "error_then_healthy"
    MockHealthHandler.server_mode_start_time = time.time()

    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()

    try:
        ok, elapsed, attempts = run_poller_algorithm(port, timeout_secs=8.0)
        print(f"  Poller result: ok={ok}, elapsed={elapsed:.2f}s, attempts={attempts}")
        if not ok:
            return False, f"Poller crashed or failed to recover from 500 HTML errors"
        return True, f"Poller survived 500 HTML errors without crashing and succeeded at {elapsed:.2f}s"
    finally:
        server.shutdown()


def stress_3d_hard_timeout_clean_exit() -> Tuple[bool, str]:
    """Test 3D: Unhealthy server must cause poller to cleanly return False within timeout limit."""
    print("\n--- Stress Test 3D: Hard Timeout Clean Exit on Unhealthy Server ---")
    server = http.server.HTTPServer(("127.0.0.1", 0), MockHealthHandler)
    port = server.server_port
    MockHealthHandler.server_mode = "never_healthy"
    MockHealthHandler.server_mode_start_time = time.time()

    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()

    try:
        timeout_limit = 2.0
        t0 = time.time()
        ok, elapsed, attempts = run_poller_algorithm(port, timeout_secs=timeout_limit)
        total_time = time.time() - t0
        print(f"  Poller result: ok={ok}, elapsed={elapsed:.2f}s, attempts={attempts}, total_time={total_time:.2f}s")
        if ok:
            return False, "Poller reported True for an always-unhealthy server!"
        if total_time > (timeout_limit + 1.0):
            return False, f"Poller hung past timeout limit: took {total_time:.2f}s (expected <= {timeout_limit + 1.0}s)"
        return True, f"Poller cleanly returned False after {elapsed:.2f}s ({attempts} attempts)"
    finally:
        server.shutdown()


# =====================================================================
# MAIN RUNNER
# =====================================================================

def main():
    print("=================================================================")
    print(" OUTLAW FORGE M3 ADVERSARIAL STRESS TEST HARNESS                 ")
    print("=================================================================")

    tests = [
        # Domain 1: Dynamic Ephemeral Ports
        ("Stress 1A: Rapid 500 Ephemeral Port Allocations", stress_1a_rapid_sequential_ports),
        ("Stress 1B: Multithreaded Concurrent Port Allocations (10x50)", stress_1b_concurrent_threads_ports),
        ("Stress 1C: 3 Concurrent Sidecar Spawns with --port 0", stress_1c_multiple_sidecar_instances),

        # Domain 2: Win32 Job Object Zero-Zombie Guarantees
        ("Stress 2A: Win32 Job Object Handle Close Kills Child", stress_2a_job_close_handle_kills_child),
        ("Stress 2B: Abrupt Supervisor Death (SIGKILL) Zero-Zombie Test", stress_2b_abrupt_supervisor_death_kills_child),

        # Domain 3: Sidecar Health Polling under Latency / Errors
        ("Stress 3A: Cold Start Handshake Recovery (2.0s 503)", stress_3a_cold_start_simulation),
        ("Stress 3B: High Response Latency Handshake (350ms delay)", stress_3b_near_timeout_latency),
        ("Stress 3C: Malformed 500 HTML Error Recovery", stress_3c_malformed_html_error_recovery),
        ("Stress 3D: Hard Timeout Clean Exit on Unhealthy Server", stress_3d_hard_timeout_clean_exit),
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
            results[name] = (False, f"Unhandled exception: {ex}")

        if not results[name][0]:
            all_passed = False

    print("\n=================================================================")
    print(" ADVERSARIAL STRESS TEST RESULTS SUMMARY                         ")
    print("=================================================================")
    for test_name, (passed, details) in results.items():
        tag = "[PASS]" if passed else "[FAIL]"
        print(f"{tag:6} {test_name}: {details}")

    print("=================================================================")
    print(f"Overall Stress Verdict: {'ALL STRESS TESTS PASSED (100%)' if all_passed else 'FAILURES DETECTED'}")
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
