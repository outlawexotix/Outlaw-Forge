#!/usr/bin/env python3
"""Outlaw Forge Milestone M5: Full End-to-End Master Verification Harness.

Comprehensive test suite verifying all Phase 12 layers:
- Layer 1: Backend Architecture and CLI (pytest 259+ tests, M1 challenger 27/27)
- Layer 2: Frontend Static Export and Contracts (eslint clean, Next.js static export)
- Layer 3: Tauri Desktop Shell and Process Supervisor (M3 supervisor 7/7, lifecycle stress 9/9)
- Layer 4: Build and Dev Automation Scripts (M4 automation 10/10, desktop:dev and desktop:build dry runs)
- Layer 5: Anti-Slop Global Typography Audit (zero em-dashes and zero en-dashes across all Phase 12 files)
"""

import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent


def get_base_env() -> Dict[str, str]:
    """Return environment dictionary with PYTHONPATH set to apps/api."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT / "apps" / "api")
    return env


# =====================================================================
# LAYER 1: BACKEND ARCHITECTURE & CLI
# =====================================================================

def verify_layer1_backend_pytest() -> Tuple[bool, str]:
    """Layer 1A: Execute pytest across apps/api/tests and assert >= 259 passed."""
    print("\n--- Layer 1A: Backend Architecture Pytest Suite ---")
    cmd = [sys.executable, "-m", "pytest", "apps/api/tests"]
    t0 = time.perf_counter()
    proc = subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        env=get_base_env(),
        timeout=300,
    )
    dt = time.perf_counter() - t0

    if proc.returncode != 0:
        return False, f"pytest failed with code {proc.returncode}:\n{proc.stdout}\n{proc.stderr}"

    match = re.search(r"(\d+)\s+passed", proc.stdout)
    if not match:
        return False, f"Could not parse passed count from pytest output:\n{proc.stdout}"

    passed_count = int(match.group(1))
    if passed_count < 259:
        return False, f"Expected at least 259 passed tests, but got {passed_count}"

    print(f"  [PASS] Pytest passed {passed_count} tests in {dt:.2f}s (code {proc.returncode})")
    return True, f"Pytest passed {passed_count} tests (expected >= 259)"


def verify_layer1_m1_challenger() -> Tuple[bool, str]:
    """Layer 1B: Execute M1 adversarial stress test harness (27/27 assertions)."""
    print("\n--- Layer 1B: M1 Adversarial Stress Test Suite ---")
    script_path = REPO_ROOT / "tests" / "stress_test_m1_challenger.py"
    if not script_path.exists():
        return False, f"Missing script: {script_path}"

    cmd = [sys.executable, str(script_path)]
    t0 = time.perf_counter()
    proc = subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        env=get_base_env(),
        timeout=120,
    )
    dt = time.perf_counter() - t0

    if proc.returncode != 0:
        return False, f"M1 stress test failed with code {proc.returncode}:\n{proc.stdout}\n{proc.stderr}"

    if "Total: 27 | Passed: 27 | Failed: 0" not in proc.stdout:
        return False, f"Expected 'Total: 27 | Passed: 27 | Failed: 0' in output:\n{proc.stdout}"

    print(f"  [PASS] M1 challenger verified 27/27 tests passed in {dt:.2f}s")
    return True, "M1 challenger stress test passed 27/27 tests"


# =====================================================================
# LAYER 2: FRONTEND STATIC EXPORT & CONTRACTS
# =====================================================================

def verify_layer2_frontend_lint() -> Tuple[bool, str]:
    """Layer 2A: Run ESLint across apps/web and assert 0 errors."""
    print("\n--- Layer 2A: Frontend ESLint Validation ---")
    t0 = time.perf_counter()
    proc = subprocess.run(
        ["npm", "run", "lint", "--workspace=apps/web"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        shell=True,
        timeout=120,
    )
    dt = time.perf_counter() - t0

    if proc.returncode != 0:
        return False, f"Frontend lint failed with code {proc.returncode}:\n{proc.stdout}\n{proc.stderr}"

    print(f"  [PASS] ESLint passed cleanly with 0 errors in {dt:.2f}s")
    return True, "Frontend lint passed cleanly with 0 errors"


def verify_layer2_static_export_build() -> Tuple[bool, str]:
    """Layer 2B: Build Next.js static export with OUTPUT_EXPORT=true and assert out/index.html."""
    print("\n--- Layer 2B: Frontend Static Export Build ---")
    out_dir = REPO_ROOT / "apps" / "web" / "out"
    next_cache = REPO_ROOT / "apps" / "web" / ".next"
    index_html = out_dir / "index.html"

    # Pre-clean stale outputs to prevent false positives and Windows lock races
    subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            "Remove-Item -Recurse -Force apps/web/out, apps/web/.next -ErrorAction SilentlyContinue",
        ],
        cwd=str(REPO_ROOT),
        check=False,
    )

    build_env = os.environ.copy()
    build_env["OUTPUT_EXPORT"] = "true"
    build_env["TAURI_ENV_PLATFORM"] = "windows"

    t0 = time.perf_counter()
    proc = subprocess.run(
        ["npm", "run", "build", "--workspace=apps/web"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        env=build_env,
        shell=True,
        timeout=180,
    )
    dt = time.perf_counter() - t0

    if proc.returncode != 0:
        return False, f"Next.js build failed with code {proc.returncode}:\n{proc.stdout}\n{proc.stderr}"

    if not index_html.exists():
        return False, f"Export index.html was not created at {index_html}"

    size_bytes = index_html.stat().st_size
    if size_bytes == 0:
        return False, f"Export index.html is empty (0 bytes) at {index_html}"

    print(f"  [PASS] Static export created {index_html.relative_to(REPO_ROOT)} ({size_bytes:,} bytes) in {dt:.2f}s")
    return True, f"Next.js static export generated index.html ({size_bytes} bytes)"


# =====================================================================
# LAYER 3: TAURI DESKTOP SHELL & PROCESS SUPERVISOR
# =====================================================================

def verify_layer3_supervisor() -> Tuple[bool, str]:
    """Layer 3A: Execute verify_m3_supervisor.py (7/7 tests pass)."""
    print("\n--- Layer 3A: Tauri Shell & Process Supervisor Suite ---")
    script_path = REPO_ROOT / "tests" / "verify_m3_supervisor.py"
    if not script_path.exists():
        return False, f"Missing script: {script_path}"

    cmd = [sys.executable, str(script_path)]
    t0 = time.perf_counter()
    proc = subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        env=get_base_env(),
        timeout=120,
    )
    dt = time.perf_counter() - t0

    if proc.returncode != 0:
        return False, f"M3 supervisor verification failed with code {proc.returncode}:\n{proc.stdout}\n{proc.stderr}"

    if "ALL TESTS PASSED (100%)" not in proc.stdout:
        return False, f"Expected 100% pass marker in supervisor output:\n{proc.stdout}"

    print(f"  [PASS] M3 supervisor verified 7/7 tests passed in {dt:.2f}s")
    return True, "M3 supervisor verified 7/7 tests passed"


def verify_layer3_lifecycle_stress() -> Tuple[bool, str]:
    """Layer 3B: Execute stress_m3_lifecycle.py (9/9 tests pass)."""
    print("\n--- Layer 3B: Process Lifecycle & Zero-Zombie Stress Suite ---")
    script_path = REPO_ROOT / "tests" / "stress_m3_lifecycle.py"
    if not script_path.exists():
        return False, f"Missing script: {script_path}"

    cmd = [sys.executable, str(script_path)]
    t0 = time.perf_counter()
    proc = subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        env=get_base_env(),
        timeout=180,
    )
    dt = time.perf_counter() - t0

    if proc.returncode != 0:
        return False, f"M3 lifecycle stress test failed with code {proc.returncode}:\n{proc.stdout}\n{proc.stderr}"

    if "ALL STRESS TESTS PASSED (100%)" not in proc.stdout:
        return False, f"Expected 100% pass marker in lifecycle stress output:\n{proc.stdout}"

    print(f"  [PASS] M3 lifecycle stress suite verified 9/9 tests passed in {dt:.2f}s")
    return True, "M3 lifecycle stress suite passed 9/9 tests (500 ports & Win32 Job Object)"


# =====================================================================
# LAYER 4: BUILD & DEV AUTOMATION SCRIPTS
# =====================================================================

def verify_layer4_automation_suite() -> Tuple[bool, str]:
    """Layer 4A: Execute verify_m4_automation.py (10/10 tests pass)."""
    print("\n--- Layer 4A: Desktop Automation Scripts Suite ---")
    script_path = REPO_ROOT / "tests" / "verify_m4_automation.py"
    if not script_path.exists():
        return False, f"Missing script: {script_path}"

    cmd = [sys.executable, str(script_path)]
    t0 = time.perf_counter()
    proc = subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        env=get_base_env(),
        timeout=120,
    )
    dt = time.perf_counter() - t0

    if proc.returncode != 0:
        return False, f"M4 automation verification failed with code {proc.returncode}:\n{proc.stdout}\n{proc.stderr}"

    if "10/10 Passed (100.0%)" not in proc.stdout:
        return False, f"Expected 10/10 Passed in automation output:\n{proc.stdout}"

    print(f"  [PASS] M4 automation suite verified 10/10 tests passed in {dt:.2f}s")
    return True, "M4 automation suite verified 10/10 tests passed"


def verify_layer4_desktop_dev_dry_run() -> Tuple[bool, str]:
    """Layer 4B: Run npm run desktop:dev -- -DryRun and assert exit code 0."""
    print("\n--- Layer 4B: desktop:dev Dry Run Execution ---")
    t0 = time.perf_counter()
    proc = subprocess.run(
        ["npm", "run", "desktop:dev", "--", "-DryRun"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        shell=True,
        timeout=60,
    )
    dt = time.perf_counter() - t0

    if proc.returncode != 0:
        return False, f"npm run desktop:dev -- -DryRun failed with code {proc.returncode}:\n{proc.stderr}"

    if "Desktop dev launcher validation complete" not in proc.stdout:
        return False, f"desktop:dev output missing completion marker:\n{proc.stdout}"

    print(f"  [PASS] npm run desktop:dev -- -DryRun completed in {dt:.2f}s (code 0)")
    return True, "desktop:dev dry run completed with code 0"


def verify_layer4_desktop_build_dry_run() -> Tuple[bool, str]:
    """Layer 4C: Run npm run desktop:build -- -DryRun and assert exit code 0."""
    print("\n--- Layer 4C: desktop:build Dry Run Execution ---")
    t0 = time.perf_counter()
    proc = subprocess.run(
        ["npm", "run", "desktop:build", "--", "-DryRun"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        shell=True,
        timeout=60,
    )
    dt = time.perf_counter() - t0

    if proc.returncode != 0:
        return False, f"npm run desktop:build -- -DryRun failed with code {proc.returncode}:\n{proc.stderr}"

    if "Build pipeline validation complete" not in proc.stdout:
        return False, f"desktop:build output missing completion marker:\n{proc.stdout}"

    print(f"  [PASS] npm run desktop:build -- -DryRun completed in {dt:.2f}s (code 0)")
    return True, "desktop:build dry run completed with code 0"


# =====================================================================
# LAYER 5: ANTI-SLOP GLOBAL TYPOGRAPHY AUDIT
# =====================================================================

def verify_layer5_typography_audit() -> Tuple[bool, str]:
    """Layer 5: Scan all newly added/modified Phase 12 files for em-dashes and en-dashes."""
    print("\n--- Layer 5: Anti-Slop Global Typography Audit ---")
    files_to_check = [
        REPO_ROOT / "apps" / "api" / "app" / "cli.py",
        REPO_ROOT / "apps" / "api" / "outlaw_forge.spec",
        REPO_ROOT / "apps" / "web" / "next.config.mjs",
        REPO_ROOT / "apps" / "web" / "src" / "lib" / "api-client.ts",
        REPO_ROOT / "apps" / "web" / "src" / "lib" / "native-dialog.ts",
        REPO_ROOT / "src-tauri" / "tauri.conf.json",
        REPO_ROOT / "src-tauri" / "capabilities" / "default.json",
        REPO_ROOT / "src-tauri" / "src" / "lib.rs",
        REPO_ROOT / "src-tauri" / "src" / "main.rs",
        REPO_ROOT / "scripts" / "desktop-dev.ps1",
        REPO_ROOT / "scripts" / "desktop-build.ps1",
        REPO_ROOT / "package.json",
        Path(__file__).resolve(),
    ]

    em_dash = "\u2014"
    en_dash = "\u2013"
    violations: List[str] = []

    for file_path in files_to_check:
        if not file_path.exists():
            violations.append(f"Missing expected file: {file_path.relative_to(REPO_ROOT)}")
            continue

        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception as e:
            violations.append(f"Error reading {file_path.name}: {e}")
            continue

        em_count = content.count(em_dash)
        en_count = content.count(en_dash)

        if em_count > 0 or en_count > 0:
            rel = file_path.relative_to(REPO_ROOT)
            violations.append(
                f"{rel}: {em_count} em-dashes, {en_count} en-dashes found"
            )
        else:
            print(f"  [PASS] {file_path.relative_to(REPO_ROOT)}: 0 violations")

    if violations:
        return False, f"Typography violations found:\n" + "\n".join(violations)

    print(f"  [PASS] All {len(files_to_check)} Phase 12 files verified 100% clean of em/en dashes")
    return True, f"All {len(files_to_check)} Phase 12 files conform to zero em-dash typography standards"


# =====================================================================
# MASTER HARNESS RUNNER
# =====================================================================

def main() -> int:
    print("=" * 75)
    print("Outlaw Forge Milestone M5: Full End-to-End Master Verification Battery")
    print("=" * 75)

    test_battery = [
        ("Layer 1A: Backend Architecture Pytest", verify_layer1_backend_pytest),
        ("Layer 1B: M1 Adversarial Stress Suite", verify_layer1_m1_challenger),
        ("Layer 2A: Frontend ESLint Validation", verify_layer2_frontend_lint),
        ("Layer 2B: Frontend Static Export Build", verify_layer2_static_export_build),
        ("Layer 3A: Tauri Shell & Supervisor", verify_layer3_supervisor),
        ("Layer 3B: Process Lifecycle & Zero-Zombie Stress", verify_layer3_lifecycle_stress),
        ("Layer 4A: Desktop Automation Scripts Suite", verify_layer4_automation_suite),
        ("Layer 4B: desktop:dev Dry Run Execution", verify_layer4_desktop_dev_dry_run),
        ("Layer 4C: desktop:build Dry Run Execution", verify_layer4_desktop_build_dry_run),
        ("Layer 5: Anti-Slop Global Typography Audit", verify_layer5_typography_audit),
    ]

    total_tests = len(test_battery)
    passed_tests = 0
    t_start = time.perf_counter()

    for name, test_func in test_battery:
        try:
            passed, message = test_func()
            if passed:
                passed_tests += 1
                print(f"[RESULT] {name}: PASS - {message}")
            else:
                print(f"[RESULT] {name}: FAIL - {message}")
        except Exception as err:
            print(f"[RESULT] {name}: ERROR - Unexpected exception: {err}")

    total_elapsed = time.perf_counter() - t_start
    pass_pct = (passed_tests / total_tests) * 100.0

    print("\n" + "=" * 75)
    print(f"Milestone M5 Master Verification Summary:")
    print(f"  Tests Passed: {passed_tests}/{total_tests} ({pass_pct:.1f}%)")
    print(f"  Total Duration: {total_elapsed:.2f}s")
    print("=" * 75)

    if passed_tests == total_tests:
        print("\nALL PHASE 12 LAYERS FULLY VERIFIED AND PASSING.")
        return 0
    else:
        print(f"\nVERIFICATION FAILED: {total_tests - passed_tests} test(s) failed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
