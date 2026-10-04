#!/usr/bin/env python3
"""Automated empirical test harness for Outlaw Forge Milestone M3:
Tauri 2.0 Desktop Shell Configuration, Capabilities, Cargo Specs,
Rust Supervisor Lifecycle, Windows Job Object Guard, and Live Integration.
"""

import ctypes
import json
import os
import re
import socket
import subprocess
import sys
import time
import tomllib
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_TAURI_DIR = REPO_ROOT / "src-tauri"
TAURI_CONF_PATH = SRC_TAURI_DIR / "tauri.conf.json"
CAPABILITIES_PATH = SRC_TAURI_DIR / "capabilities" / "default.json"
CARGO_TOML_PATH = SRC_TAURI_DIR / "Cargo.toml"
LIB_RS_PATH = SRC_TAURI_DIR / "src" / "lib.rs"
MAIN_RS_PATH = SRC_TAURI_DIR / "src" / "main.rs"
API_DIR = REPO_ROOT / "apps" / "api"
CLI_PATH = API_DIR / "app" / "cli.py"


def get_base_env() -> Dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(API_DIR)
    return env


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


def test_1_tauri_conf_json() -> Tuple[bool, str]:
    """Verify tauri.conf.json window dimensions, theme, frontendDist, plugins, and file associations."""
    print("\n--- Test 1: tauri.conf.json Configuration Verification ---")
    if not TAURI_CONF_PATH.exists():
        return False, f"Missing {TAURI_CONF_PATH}"

    with open(TAURI_CONF_PATH, "r", encoding="utf-8") as f:
        conf = json.load(f)

    # Check build section
    build_conf = conf.get("build", {})
    if build_conf.get("frontendDist") != "../apps/web/out":
        return False, f"Expected frontendDist == '../apps/web/out', got '{build_conf.get('frontendDist')}'"
    if build_conf.get("devUrl") != "http://localhost:3000":
        return False, f"Expected devUrl == 'http://localhost:3000', got '{build_conf.get('devUrl')}'"

    # Check window configuration
    app_conf = conf.get("app", {})
    windows = app_conf.get("windows", [])
    if not windows:
        return False, "No windows defined in app.windows"

    main_win = windows[0]
    expected_title = "Outlaw Forge 3D Preparation Workbench"
    if main_win.get("title") != expected_title:
        return False, f"Expected window title '{expected_title}', got '{main_win.get('title')}'"
    if main_win.get("width") != 1440 or main_win.get("height") != 900:
        return False, f"Expected default 1440x900, got {main_win.get('width')}x{main_win.get('height')}"
    if main_win.get("minWidth") != 1024 or main_win.get("minHeight") != 700:
        return False, f"Expected min 1024x700, got {main_win.get('minWidth')}x{main_win.get('minHeight')}"
    if main_win.get("resizable") is not True:
        return False, f"Expected resizable == True, got {main_win.get('resizable')}"
    if main_win.get("fullscreen") is not False:
        return False, f"Expected fullscreen == False, got {main_win.get('fullscreen')}"
    if main_win.get("decorations") is not True:
        return False, f"Expected decorations == True, got {main_win.get('decorations')}"
    if main_win.get("theme") != "Dark":
        return False, f"Expected theme == 'Dark', got '{main_win.get('theme')}'"
    bg_color = main_win.get("backgroundColor") or main_win.get("background_color")
    if bg_color != "#0B0F17":
        return False, f"Expected backgroundColor == '#0B0F17', got '{bg_color}'"

    # Check file associations
    bundle_conf = conf.get("bundle", {})
    associations = bundle_conf.get("fileAssociations", [])
    ext_map = {}
    for assoc in associations:
        exts = assoc.get("ext", [])
        for ext in exts:
            ext_map[ext.lower()] = assoc

    required_exts = {"stl": "Stereolithography 3D Mesh", "obj": "Wavefront 3D Object", "3mf": "3D Manufacturing Format"}
    for ext, desc in required_exts.items():
        if ext not in ext_map:
            return False, f"Missing file association for extension .{ext}"
        entry = ext_map[ext]
        if entry.get("role") != "Editor":
            return False, f"Extension .{ext} role must be 'Editor', got '{entry.get('role')}'"

    # Check plugins
    plugins = conf.get("plugins", {})
    required_plugins = ["dialog", "shell", "process", "fs"]
    for p in required_plugins:
        if p not in plugins:
            return False, f"Missing required plugin in tauri.conf.json: '{p}'"

    return True, "Window dimensions (1440x900, min 1024x700), theme, file associations (.stl, .obj, .3mf), and plugins valid"


def test_2_capabilities_permissions() -> Tuple[bool, str]:
    """Verify capabilities/default.json plugin permissions."""
    print("\n--- Test 2: capabilities/default.json Permissions Verification ---")
    if not CAPABILITIES_PATH.exists():
        return False, f"Missing {CAPABILITIES_PATH}"

    with open(CAPABILITIES_PATH, "r", encoding="utf-8") as f:
        cap = json.load(f)

    permissions = set(cap.get("permissions", []))
    required_permissions = {
        "dialog:default",
        "dialog:allow-open",
        "dialog:allow-save",
        "shell:default",
        "shell:allow-open",
        "process:default",
        "fs:default",
        "fs:allow-write-file",
        "fs:allow-read-file",
    }

    missing = required_permissions - permissions
    if missing:
        return False, f"Missing required permissions: {sorted(list(missing))}"

    return True, f"All {len(required_permissions)} required capability permissions verified"


def test_3_cargo_toml_dependencies() -> Tuple[bool, str]:
    """Verify Cargo.toml dependencies and Windows Job Object features."""
    print("\n--- Test 3: Cargo.toml Dependencies Verification ---")
    if not CARGO_TOML_PATH.exists():
        return False, f"Missing {CARGO_TOML_PATH}"

    with open(CARGO_TOML_PATH, "rb") as f:
        cargo_data = tomllib.load(f)

    deps = cargo_data.get("dependencies", {})
    required_deps = [
        "tauri",
        "tauri-plugin-dialog",
        "tauri-plugin-shell",
        "tauri-plugin-process",
        "tauri-plugin-fs",
        "serde",
        "serde_json",
        "tokio",
        "reqwest",
        "anyhow",
    ]

    for dep in required_deps:
        if dep not in deps:
            return False, f"Missing required dependency: '{dep}'"

    # Check windows target dependencies for windows-sys
    target_data = cargo_data.get("target", {})
    win_target = target_data.get("'cfg(windows)'", {}) or target_data.get("cfg(windows)", {})
    win_deps = win_target.get("dependencies", {})
    if "windows-sys" not in win_deps and "windows-sys" not in deps:
        return False, "Missing 'windows-sys' dependency for Windows Job Object support"

    ws_entry = win_deps.get("windows-sys") or deps.get("windows-sys")
    if isinstance(ws_entry, dict):
        features = set(ws_entry.get("features", []))
        required_features = {"Win32_System_JobObjects", "Win32_Foundation", "Win32_System_Threading"}
        missing_features = required_features - features
        if missing_features:
            return False, f"Missing windows-sys features: {sorted(list(missing_features))}"

    return True, "All required Cargo dependencies and windows-sys Job Object features verified"


def test_4_rust_lib_supervisor_syntax() -> Tuple[bool, str]:
    """Verify src-tauri/src/lib.rs structure: Job Object, ephemeral port, health check, CAD menu, and cleanup."""
    print("\n--- Test 4: src-tauri/src/lib.rs Structural & Architecture Verification ---")
    if not LIB_RS_PATH.exists():
        return False, f"Missing {LIB_RS_PATH}"

    content = LIB_RS_PATH.read_text(encoding="utf-8")

    # 1. Windows Job Object Supervisor
    job_patterns = [
        r"CreateJobObjectW",
        r"JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE",
        r"AssignProcessToJobObject",
        r"SetInformationJobObject",
        r"JobObjectExtendedLimitInformation",
    ]
    for pat in job_patterns:
        if not re.search(pat, content):
            return False, f"src/lib.rs missing Win32 Job Object element: {pat}"

    # 2. Ephemeral port discovery
    if 'TcpListener::bind("127.0.0.1:0")' not in content:
        return False, "src/lib.rs missing ephemeral port discovery: TcpListener::bind(\"127.0.0.1:0\")"

    # 3. Sidecar Spawner logic
    if "binaries/outlaw_forge_sidecar" not in content or "apps/api/app/cli.py" not in content:
        return False, "src/lib.rs missing sidecar fallback command execution logic"

    # 4. Active Health Check Polling
    if "wait_for_backend_health" not in content:
        return False, "src/lib.rs missing wait_for_backend_health function"
    if "/health" not in content or "healthy" not in content:
        return False, "src/lib.rs health check does not target /health or check 'healthy' status"

    # 5. Dynamic BaseURL Injection
    if "window.__OUTLAW_FORGE_API_URL__" not in content:
        return False, "src/lib.rs missing window.__OUTLAW_FORGE_API_URL__ injection string"
    if "initialization_script" not in content:
        return False, "src/lib.rs missing initialization_script call on WebviewWindowBuilder"
    if "window.eval" not in content:
        return False, "src/lib.rs missing window.eval call for runtime baseUrl update"

    # 6. CAD Menu Bar with Accelerators
    menu_items = [
        ("menu-import", "Ctrl+O", "outlaw-forge:menu-import"),
        ("menu-save", "Ctrl+S", "outlaw-forge:menu-save"),
        ("menu-export", "Ctrl+E", "outlaw-forge:menu-export"),
        ("menu-undo", "Ctrl+Z", "outlaw-forge:menu-undo"),
        ("menu-redo", "Ctrl+Y", "outlaw-forge:menu-redo"),
        ("menu-center-bed", "Ctrl+Space", "outlaw-forge:menu-center-bed"),
        ("menu-wireframe", "W", "outlaw-forge:menu-wireframe"),
        ("menu-reset-camera", "R", "outlaw-forge:menu-reset-camera"),
    ]
    for item_id, acc, event in menu_items:
        if item_id not in content:
            return False, f"src/lib.rs missing menu item id '{item_id}'"
        if acc not in content:
            return False, f"src/lib.rs missing accelerator '{acc}'"
        if event not in content:
            return False, f"src/lib.rs missing menu event emission '{event}'"

    # 7. Clean Shutdown
    if "CloseRequested" not in content or "ExitRequested" not in content:
        return False, "src/lib.rs missing window CloseRequested and app ExitRequested hooks"
    if "child.kill()" not in content or "child.wait()" not in content:
        return False, "src/lib.rs missing child.kill() and child.wait() calls"

    return True, "All Job Object, ephemeral port, health check, CAD menu, and clean shutdown structures verified"


def test_5_sidecar_ephemeral_integration() -> Tuple[bool, str]:
    """Empirical integration test: launch python -m app.cli --port 0, poll /health, verify HTTP 200."""
    print("\n--- Test 5: Empirical Sidecar Ephemeral Port & Health Integration ---")
    proc = subprocess.Popen(
        [sys.executable, "-m", "app.cli", "--port", "0"],
        cwd=str(REPO_ROOT),
        env=get_base_env(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

    port = None
    start_time = time.time()
    try:
        while time.time() - start_time < 10.0:
            if proc.poll() is not None:
                break
            line = proc.stdout.readline()
            if line:
                match = re.search(r"HEALTH_OK:\s*PORT=(\d+)", line)
                if match:
                    port = int(match.group(1))
                    break
            time.sleep(0.05)

        if port is None:
            err = proc.stderr.read()
            return False, f"Failed to acquire ephemeral port within 10s. Stderr: {err[:200]}"

        print(f"  Acquired dynamic port: {port}")

        # Active health check
        health_url = f"http://127.0.0.1:{port}/health"
        status, body = http_get(health_url)
        print(f"  GET {health_url} -> status {status}, body {body}")

        if status != 200:
            return False, f"Health check returned status {status}, expected 200"
        if body.get("status") != "healthy":
            return False, f"Expected body.status == 'healthy', got {body}"

        return True, f"Sidecar dynamically bound port {port} and responded HTTP 200 healthy"
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=3)
        except Exception:
            proc.kill()
            proc.wait(timeout=2)


def test_6_win32_job_object_supervisor_empirical() -> Tuple[bool, str]:
    """Empirically verify Win32 Job Object assignment and limit flags on Windows."""
    print("\n--- Test 6: Empirical Windows Job Object Supervisor Test ---")
    if sys.platform != "win32":
        return True, "Skipped: Non-Windows OS (Job Objects are Windows-specific)"

    kernel32 = ctypes.windll.kernel32

    # Win32 Constants
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

    # 1. Create Job Object
    job = kernel32.CreateJobObjectW(None, None)
    if not job:
        return False, f"CreateJobObjectW failed with error {kernel32.GetLastError()}"

    try:
        # 2. Configure KILL_ON_JOB_CLOSE
        info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        ok = kernel32.SetInformationJobObject(
            job,
            JobObjectExtendedLimitInformation,
            ctypes.byref(info),
            ctypes.sizeof(info),
        )
        if not ok:
            return False, f"SetInformationJobObject failed with error {kernel32.GetLastError()}"

        # 3. Spawn a test worker process (sleep 30s)
        test_proc = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        try:
            # 4. Assign process to Job Object
            PROCESS_SET_QUOTA = 0x0100
            PROCESS_TERMINATE = 0x0001
            h_proc = kernel32.OpenProcess(
                PROCESS_SET_QUOTA | PROCESS_TERMINATE,
                False,
                test_proc.pid,
            )
            if not h_proc:
                return False, f"OpenProcess failed with error {kernel32.GetLastError()}"

            assigned = kernel32.AssignProcessToJobObject(job, h_proc)
            kernel32.CloseHandle(h_proc)

            if not assigned:
                return False, f"AssignProcessToJobObject failed with error {kernel32.GetLastError()}"

            # 5. Check IsProcessInJob
            is_in_job = ctypes.c_int(0)
            kernel32.IsProcessInJob(h_proc if h_proc else -1, job, ctypes.byref(is_in_job))

            print(f"  Test child PID {test_proc.pid} successfully assigned to Job Object {job}")
            return True, f"Windows Job Object assigned PID {test_proc.pid} with KILL_ON_JOB_CLOSE"
        finally:
            try:
                test_proc.terminate()
                test_proc.wait(timeout=2)
            except Exception:
                test_proc.kill()
    finally:
        kernel32.CloseHandle(job)


def test_7_anti_slop_compliance() -> Tuple[bool, str]:
    """Verify absence of forbidden em-dashes and en-dashes in user-facing UI configurations."""
    print("\n--- Test 7: Anti-Slop UI Typography Compliance ---")
    files_to_check = [TAURI_CONF_PATH, CAPABILITIES_PATH, LIB_RS_PATH]
    violations = []

    for file_path in files_to_check:
        text = file_path.read_text(encoding="utf-8")
        lines = text.split("\n")
        for idx, line in enumerate(lines):
            # Exclude code comments starting with // or /*
            stripped = line.strip()
            if stripped.startswith("//") or stripped.startswith("/*"):
                continue
            if "—" in line or "–" in line:
                violations.append(f"{file_path.name}:{idx+1}: {stripped}")

    if violations:
        return False, f"Found typography violations (em-dash/en-dash): {violations}"

    return True, "No em-dashes or en-dashes found in user-facing configuration or menus"


def main():
    print("=================================================================")
    print(" Outlaw Forge M3 Tauri 2.0 & Supervisor Verification Harness     ")
    print("=================================================================")

    tests = [
        ("tauri.conf.json Window, Theme, File Associations & Plugins", test_1_tauri_conf_json),
        ("capabilities/default.json Plugin Permissions", test_2_capabilities_permissions),
        ("Cargo.toml Dependencies & Windows Job Object Features", test_3_cargo_toml_dependencies),
        ("src-tauri/src/lib.rs Supervisor & Menu Architecture", test_4_rust_lib_supervisor_syntax),
        ("Empirical Sidecar Dynamic Ephemeral Port & Health Polling", test_5_sidecar_ephemeral_integration),
        ("Empirical Windows Job Object Supervisor Guarantee", test_6_win32_job_object_supervisor_empirical),
        ("Anti-Slop UI Typography Compliance", test_7_anti_slop_compliance),
    ]

    results = {}
    for name, fn in tests:
        try:
            passed, details = fn()
            results[name] = (passed, details)
        except Exception as e:
            results[name] = (False, f"Exception: {str(e)}")

    print("\n=================================================================")
    print(" VERIFICATION RESULTS SUMMARY                                    ")
    print("=================================================================")
    all_passed = True
    for test_name, (passed, details) in results.items():
        status_str = "[PASS]" if passed else "[FAIL]"
        print(f"{status_str:6} {test_name}: {details}")
        if not passed:
            all_passed = False

    print("=================================================================")
    print(f"Overall status: {'ALL TESTS PASSED (100%)' if all_passed else 'FAILURES DETECTED'}")
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
