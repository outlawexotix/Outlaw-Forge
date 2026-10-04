#!/usr/bin/env python3
"""Automated empirical test harness for Outlaw Forge Milestone M4:
Desktop Development and Build Automation Scripts (scripts/desktop-dev.ps1,
scripts/desktop-build.ps1, package.json scripts, and anti-slop typography).
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
DEV_SCRIPT_PATH = REPO_ROOT / "scripts" / "desktop-dev.ps1"
BUILD_SCRIPT_PATH = REPO_ROOT / "scripts" / "desktop-build.ps1"
PACKAGE_JSON_PATH = REPO_ROOT / "package.json"


def run_powershell_command(command: str) -> subprocess.CompletedProcess:
    """Execute a PowerShell command string and return the completed process."""
    return subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )


def run_powershell_file(args: List[str]) -> subprocess.CompletedProcess:
    """Execute a PowerShell script file with arguments."""
    cmd = ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File"] + args
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )


def test_1_script_files_exist() -> Tuple[bool, str]:
    """Verify that both PowerShell automation scripts and package.json exist."""
    print("\n--- Test 1: File Existence Verification ---")
    if not DEV_SCRIPT_PATH.exists():
        return False, f"Missing {DEV_SCRIPT_PATH}"
    print(f"  [PASS] Found {DEV_SCRIPT_PATH.relative_to(REPO_ROOT)}")

    if not BUILD_SCRIPT_PATH.exists():
        return False, f"Missing {BUILD_SCRIPT_PATH}"
    print(f"  [PASS] Found {BUILD_SCRIPT_PATH.relative_to(REPO_ROOT)}")

    if not PACKAGE_JSON_PATH.exists():
        return False, f"Missing {PACKAGE_JSON_PATH}"
    print(f"  [PASS] Found {PACKAGE_JSON_PATH.relative_to(REPO_ROOT)}")

    return True, "All required automation files exist."


def test_2_powershell_ast_syntax() -> Tuple[bool, str]:
    """Verify PowerShell syntax using [System.Management.Automation.Language.Parser]::ParseInput."""
    print("\n--- Test 2: PowerShell Language Parser Syntax Validation ---")
    scripts_to_test = [
        ("desktop-dev.ps1", DEV_SCRIPT_PATH),
        ("desktop-build.ps1", BUILD_SCRIPT_PATH),
    ]

    for name, path in scripts_to_test:
        ps_cmd = (
            f"$content = [System.IO.File]::ReadAllText('{path.as_posix()}'); "
            f"$tokens = $null; $errors = $null; "
            f"$ast = [System.Management.Automation.Language.Parser]::ParseInput($content, [ref]$tokens, [ref]$errors); "
            f"if ($errors.Count -gt 0) {{ "
            f"  $errors | ForEach-Object {{ Write-Error $_.Message }}; exit 1 "
            f"}} else {{ Write-Host 'SYNTAX_OK' }}"
        )
        proc = run_powershell_command(ps_cmd)
        if proc.returncode != 0 or "SYNTAX_OK" not in proc.stdout:
            err = proc.stderr.strip() or proc.stdout.strip()
            return False, f"PowerShell syntax validation failed for {name}: {err}"
        print(f"  [PASS] Syntax parse clean (0 errors) for {name}")

    return True, "Both scripts passed PowerShell AST parser syntax validation without errors."


def test_3_powershell_parameter_signatures() -> Tuple[bool, str]:
    """Verify parameter definitions in both scripts via PowerShell AST."""
    print("\n--- Test 3: PowerShell AST Parameter Signature Validation ---")

    # Check desktop-dev.ps1 parameters: Port, BackendOnly, SkipBackend, DryRun
    dev_cmd = (
        f"$content = [System.IO.File]::ReadAllText('{DEV_SCRIPT_PATH.as_posix()}'); "
        f"$t = $null; $e = $null; "
        f"$ast = [System.Management.Automation.Language.Parser]::ParseInput($content, [ref]$t, [ref]$e); "
        f"$ast.ParamBlock.Parameters | ForEach-Object {{ $_.Name.VariablePath.UserPath }}"
    )
    dev_proc = run_powershell_command(dev_cmd)
    if dev_proc.returncode != 0:
        return False, f"Failed to extract parameters from desktop-dev.ps1: {dev_proc.stderr}"

    dev_params = set(dev_proc.stdout.strip().splitlines())
    expected_dev = {"Port", "BackendOnly", "SkipBackend", "DryRun"}
    if not expected_dev.issubset(dev_params):
        return False, f"desktop-dev.ps1 missing expected parameters. Expected {expected_dev}, found {dev_params}"
    print(f"  [PASS] desktop-dev.ps1 parameters verified: {dev_params}")

    # Check desktop-build.ps1 parameters: SkipFrontend, SkipSidecar, SkipTauri, DryRun
    build_cmd = (
        f"$content = [System.IO.File]::ReadAllText('{BUILD_SCRIPT_PATH.as_posix()}'); "
        f"$t = $null; $e = $null; "
        f"$ast = [System.Management.Automation.Language.Parser]::ParseInput($content, [ref]$t, [ref]$e); "
        f"$ast.ParamBlock.Parameters | ForEach-Object {{ $_.Name.VariablePath.UserPath }}"
    )
    build_proc = run_powershell_command(build_cmd)
    if build_proc.returncode != 0:
        return False, f"Failed to extract parameters from desktop-build.ps1: {build_proc.stderr}"

    build_params = set(build_proc.stdout.strip().splitlines())
    expected_build = {"SkipFrontend", "SkipSidecar", "SkipTauri", "DryRun"}
    if not expected_build.issubset(build_params):
        return False, f"desktop-build.ps1 missing expected parameters. Expected {expected_build}, found {build_params}"
    print(f"  [PASS] desktop-build.ps1 parameters verified: {build_params}")

    return True, "Parameter signatures verified via PowerShell AST."


def test_4_desktop_dev_dry_run() -> Tuple[bool, str]:
    """Execute desktop-dev.ps1 with -DryRun and verify exit code 0 and stdout."""
    print("\n--- Test 4: desktop-dev.ps1 Dry-Run Execution ---")
    proc = run_powershell_file(["scripts/desktop-dev.ps1", "-DryRun"])
    if proc.returncode != 0:
        return False, f"desktop-dev.ps1 -DryRun failed with code {proc.returncode}: {proc.stderr}"

    output = proc.stdout
    required_phrases = [
        "Outlaw Forge Desktop Dev Launcher",
        "[DryRun] Port allocated:",
        "OUTLAW_FORGE_PORT =",
        "NEXT_PUBLIC_API_URL =",
        "TAURI_ENV_PLATFORM =",
        "[DryRun] Backend command:",
        "[DryRun] Health check polling target:",
        "[DryRun] Frontend command:",
        "[DryRun] Desktop dev launcher validation complete.",
    ]
    for phrase in required_phrases:
        if phrase not in output:
            return False, f"desktop-dev.ps1 -DryRun missing expected phrase '{phrase}' in stdout:\n{output}"

    print("  [PASS] desktop-dev.ps1 -DryRun succeeded with code 0 and full diagnostics output.")
    return True, "desktop-dev.ps1 dry run verified."


def test_5_desktop_dev_flags_dry_run() -> Tuple[bool, str]:
    """Execute desktop-dev.ps1 with custom port and flags in dry-run mode."""
    print("\n--- Test 5: desktop-dev.ps1 Flag Variations Dry-Run ---")
    proc = run_powershell_file(["scripts/desktop-dev.ps1", "-Port", "9876", "-BackendOnly", "-DryRun"])
    if proc.returncode != 0:
        return False, f"desktop-dev.ps1 -Port 9876 -BackendOnly -DryRun failed: {proc.stderr}"

    output = proc.stdout
    if "Port allocated: 9876" not in output:
        return False, f"Custom port 9876 not found in output: {output}"
    if "Standalone backend mode" not in output:
        return False, f"BackendOnly notice not found in output: {output}"

    skip_proc = run_powershell_file(["scripts/desktop-dev.ps1", "-SkipBackend", "-DryRun"])
    if skip_proc.returncode != 0:
        return False, f"desktop-dev.ps1 -SkipBackend -DryRun failed: {skip_proc.stderr}"
    if "Backend execution skipped" not in skip_proc.stdout:
        return False, f"SkipBackend notice not found in output: {skip_proc.stdout}"

    print("  [PASS] desktop-dev.ps1 custom port, BackendOnly, and SkipBackend dry-run verified.")
    return True, "desktop-dev.ps1 flag variations verified."


def test_6_desktop_build_dry_run() -> Tuple[bool, str]:
    """Execute desktop-build.ps1 with -DryRun and verify exit code 0 and diagnostics."""
    print("\n--- Test 6: desktop-build.ps1 Dry-Run Execution ---")
    proc = run_powershell_file(["scripts/desktop-build.ps1", "-DryRun"])
    if proc.returncode != 0:
        return False, f"desktop-build.ps1 -DryRun failed with code {proc.returncode}: {proc.stderr}"

    output = proc.stdout
    required_phrases = [
        "Outlaw Forge Desktop Production Build",
        "[DryRun] Validating workspace paths",
        "[OK] Frontend directory: apps/web",
        "[OK] PyInstaller specification: apps/api/outlaw_forge.spec",
        "[OK] Tauri shell directory: src-tauri",
        "[DryRun] Toolchain status:",
        "Node.js:",
        "npm:",
        "PyInstaller:",
        "Cargo / Rust:",
        "[DryRun] Planned build actions:",
        "Step 1 (Frontend):",
        "Step 2 (Sidecar):",
        "Step 3 (Tauri):",
        "[DryRun] Build pipeline validation complete.",
    ]
    for phrase in required_phrases:
        if phrase not in output:
            return False, f"desktop-build.ps1 -DryRun missing expected phrase '{phrase}' in stdout:\n{output}"

    print("  [PASS] desktop-build.ps1 -DryRun succeeded with code 0 and complete toolchain report.")
    return True, "desktop-build.ps1 dry run verified."


def test_7_desktop_build_skip_flags_dry_run() -> Tuple[bool, str]:
    """Execute desktop-build.ps1 with skip flags in dry-run mode."""
    print("\n--- Test 7: desktop-build.ps1 Skip Flags Dry-Run ---")
    proc = run_powershell_file([
        "scripts/desktop-build.ps1",
        "-SkipFrontend",
        "-SkipSidecar",
        "-SkipTauri",
        "-DryRun",
    ])
    if proc.returncode != 0:
        return False, f"desktop-build.ps1 with skip flags failed: {proc.stderr}"

    output = proc.stdout
    if "Step 1 (Frontend): Skipped" not in output:
        return False, f"SkipFrontend not reflected in output: {output}"
    if "Step 2 (Sidecar):  Skipped" not in output:
        return False, f"SkipSidecar not reflected in output: {output}"
    if "Step 3 (Tauri):    Skipped" not in output:
        return False, f"SkipTauri not reflected in output: {output}"

    print("  [PASS] desktop-build.ps1 skip flags dry-run verified.")
    return True, "desktop-build.ps1 skip flags verified."


def test_8_package_json_scripts() -> Tuple[bool, str]:
    """Verify root package.json defines desktop:dev and desktop:build."""
    print("\n--- Test 8: Root package.json Scripts Verification ---")
    with open(PACKAGE_JSON_PATH, "r", encoding="utf-8") as f:
        pkg = json.load(f)

    scripts = pkg.get("scripts", {})
    if "desktop:dev" not in scripts:
        return False, "package.json missing 'desktop:dev' script"
    if "desktop:build" not in scripts:
        return False, "package.json missing 'desktop:build' script"

    dev_cmd = scripts["desktop:dev"]
    build_cmd = scripts["desktop:build"]

    if "desktop-dev.ps1" not in dev_cmd:
        return False, f"'desktop:dev' does not invoke desktop-dev.ps1: {dev_cmd}"
    if "desktop-build.ps1" not in build_cmd:
        return False, f"'desktop:build' does not invoke desktop-build.ps1: {build_cmd}"

    if "-ExecutionPolicy Bypass" not in dev_cmd or "-ExecutionPolicy Bypass" not in build_cmd:
        return False, "Scripts must specify -ExecutionPolicy Bypass"

    print(f"  [PASS] desktop:dev -> {dev_cmd}")
    print(f"  [PASS] desktop:build -> {build_cmd}")
    return True, "package.json scripts verified."


def test_9_npm_script_dry_run() -> Tuple[bool, str]:
    """Execute npm run desktop:dev and desktop:build with dry-run parameters."""
    print("\n--- Test 9: NPM Script Invocation Dry-Run ---")
    dev_proc = subprocess.run(
        ["npm", "run", "desktop:dev", "--", "-DryRun"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        shell=True,
    )
    if dev_proc.returncode != 0:
        return False, f"npm run desktop:dev -- -DryRun failed: {dev_proc.stderr}"
    if "Desktop dev launcher validation complete" not in dev_proc.stdout:
        return False, f"npm run desktop:dev output missing completion marker: {dev_proc.stdout}"
    print("  [PASS] npm run desktop:dev -- -DryRun executed cleanly (exit code 0)")

    build_proc = subprocess.run(
        ["npm", "run", "desktop:build", "--", "-DryRun"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        shell=True,
    )
    if build_proc.returncode != 0:
        return False, f"npm run desktop:build -- -DryRun failed: {build_proc.stderr}"
    if "Build pipeline validation complete" not in build_proc.stdout:
        return False, f"npm run desktop:build output missing completion marker: {build_proc.stdout}"
    print("  [PASS] npm run desktop:build -- -DryRun executed cleanly (exit code 0)")

    return True, "NPM desktop scripts invocation verified."


def test_10_anti_slop_typography() -> Tuple[bool, str]:
    """Verify zero em-dashes and zero separator en-dashes across all M4 files."""
    print("\n--- Test 10: Anti-Slop Typography Verification ---")
    files_to_check = [
        DEV_SCRIPT_PATH,
        BUILD_SCRIPT_PATH,
        PACKAGE_JSON_PATH,
        Path(__file__).resolve(),
    ]

    em_dash = "\u2014"
    en_dash = "\u2013"

    for p in files_to_check:
        with open(p, "r", encoding="utf-8") as f:
            content = f.read()

        em_count = content.count(em_dash)
        en_count = content.count(en_dash)

        if em_count > 0 or en_count > 0:
            return False, (
                f"Typography violation in {p.name}: {em_count} em-dashes, "
                f"{en_count} en-dashes found. Replace with hyphens or colons."
            )
        print(f"  [PASS] {p.name}: 0 em-dashes, 0 en-dashes (clean)")

    return True, "All files conform to anti-slop typography standards."


def main() -> int:
    print("=" * 70)
    print("Outlaw Forge Milestone M4: Desktop Development & Build Automation")
    print("Empirical Verification Suite")
    print("=" * 70)

    tests = [
        ("Test 1: File Existence", test_1_script_files_exist),
        ("Test 2: PowerShell AST Syntax", test_2_powershell_ast_syntax),
        ("Test 3: PowerShell AST Parameters", test_3_powershell_parameter_signatures),
        ("Test 4: desktop-dev.ps1 Dry Run", test_4_desktop_dev_dry_run),
        ("Test 5: desktop-dev.ps1 Flags Dry Run", test_5_desktop_dev_flags_dry_run),
        ("Test 6: desktop-build.ps1 Dry Run", test_6_desktop_build_dry_run),
        ("Test 7: desktop-build.ps1 Skip Flags", test_7_desktop_build_skip_flags_dry_run),
        ("Test 8: package.json Desktop Scripts", test_8_package_json_scripts),
        ("Test 9: NPM Desktop Scripts Execution", test_9_npm_script_dry_run),
        ("Test 10: Anti-Slop Typography", test_10_anti_slop_typography),
    ]

    passed = 0
    total = len(tests)

    for name, test_fn in tests:
        try:
            ok, msg = test_fn()
            if ok:
                passed += 1
                print(f"[RESULT] {name}: PASS - {msg}")
            else:
                print(f"[RESULT] {name}: FAIL - {msg}")
        except Exception as e:
            print(f"[RESULT] {name}: ERROR - Exception: {e}")

    print("\n" + "=" * 70)
    print(f"M4 Automation Verification Summary: {passed}/{total} Passed ({passed/total*100:.1f}%)")
    print("=" * 70)

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
