#!/usr/bin/env python3
"""Adversarial Verification Suite for Milestone M3 Shell Config, Capabilities, and Native Menus.

Empirical Challenger 2 (teamwork_preview_challenger_m3_2):
1. Verifies src-tauri/tauri.conf.json:
   - Window size: default 1440x900, min 1024x700.
   - Dark theme & background color #0B0F17.
   - frontendDist: ../apps/web/out.
   - OS file associations: .stl, .obj, .3mf with role 'Editor'.
   - Plugins: dialog, shell, process, fs.
2. Verifies src-tauri/capabilities/default.json:
   - Target window: ['main'].
   - Granular permissions: dialog, shell, process, fs, core.
   - Rejects overly permissive broad grants (e.g. shell:allow-execute).
3. Verifies src-tauri/src/lib.rs:
   - CAD Menu accelerators & event emission:
     - outlaw-forge:menu-import (Ctrl+O)
     - outlaw-forge:menu-save (Ctrl+S)
     - outlaw-forge:menu-export (Ctrl+E)
     - outlaw-forge:menu-undo (Ctrl+Z)
     - outlaw-forge:menu-redo (Ctrl+Y)
     - outlaw-forge:menu-center-bed (Ctrl+Space)
     - outlaw-forge:menu-wireframe (W)
     - outlaw-forge:menu-reset-camera (R)
     - outlaw-forge:menu-about (No accelerator)
   - Menu items: Exit (Alt+F4), Toggle Fullscreen (F11).
4. Zero em-dash (\\u2014) or separator en-dash (\\u2013) across configuration strings,
   menu labels, and user-facing UI copy.
"""

import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
TAURI_CONF = REPO_ROOT / "src-tauri" / "tauri.conf.json"
CAPABILITIES = REPO_ROOT / "src-tauri" / "capabilities" / "default.json"
LIB_RS = REPO_ROOT / "src-tauri" / "src" / "lib.rs"
MAIN_RS = REPO_ROOT / "src-tauri" / "src" / "main.rs"
CARGO_TOML = REPO_ROOT / "src-tauri" / "Cargo.toml"


def check_tauri_conf() -> Tuple[bool, str]:
    if not TAURI_CONF.exists():
        return False, f"Missing {TAURI_CONF}"

    try:
        conf = json.loads(TAURI_CONF.read_text(encoding="utf-8"))
    except Exception as e:
        return False, f"Invalid JSON in tauri.conf.json: {e}"

    # Build section
    build = conf.get("build", {})
    if build.get("frontendDist") != "../apps/web/out":
        return False, f"frontendDist mismatch: {build.get('frontendDist')}"
    if build.get("devUrl") != "http://localhost:3000":
        return False, f"devUrl mismatch: {build.get('devUrl')}"

    # Window bounds & theme
    windows = conf.get("app", {}).get("windows", [])
    if not windows:
        return False, "No windows found in app.windows"
    win = windows[0]
    if win.get("width") != 1440 or win.get("height") != 900:
        return False, f"Window size mismatch: {win.get('width')}x{win.get('height')} (expected 1440x900)"
    if win.get("minWidth") != 1024 or win.get("minHeight") != 700:
        return False, f"Window min size mismatch: {win.get('minWidth')}x{win.get('minHeight')} (expected 1024x700)"
    if win.get("theme") != "Dark":
        return False, f"Theme mismatch: {win.get('theme')}"
    if win.get("backgroundColor") != "#0B0F17":
        return False, f"backgroundColor mismatch: {win.get('backgroundColor')}"

    # File associations
    assocs = conf.get("bundle", {}).get("fileAssociations", [])
    ext_map = {}
    for a in assocs:
        for ext in a.get("ext", []):
            ext_map[ext.lower()] = a

    required_exts = ["stl", "obj", "3mf"]
    for ext in required_exts:
        if ext not in ext_map:
            return False, f"Missing file association for .{ext}"
        if ext_map[ext].get("role") != "Editor":
            return False, f"File association .{ext} role is not 'Editor'"

    # Plugins
    plugins = conf.get("plugins", {})
    for p in ["dialog", "shell", "process", "fs"]:
        if p not in plugins:
            return False, f"Missing plugin '{p}' in tauri.conf.json"

    return True, "Window bounds (1440x900, min 1024x700), dark theme (#0B0F17), frontendDist, file associations, and plugins verified"


def check_capabilities() -> Tuple[bool, str]:
    if not CAPABILITIES.exists():
        return False, f"Missing {CAPABILITIES}"

    try:
        cap = json.loads(CAPABILITIES.read_text(encoding="utf-8"))
    except Exception as e:
        return False, f"Invalid JSON in capabilities/default.json: {e}"

    windows = cap.get("windows", [])
    if "main" not in windows:
        return False, f"'main' window not targeted in capabilities: {windows}"

    perms = set(cap.get("permissions", []))
    required_perms = {
        "core:default",
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
    missing = required_perms - perms
    if missing:
        return False, f"Missing required capabilities: {sorted(list(missing))}"

    # Adversarial check: Ensure shell:allow-execute is NOT present (least privilege security principle)
    if "shell:allow-execute" in perms:
        return False, "Security violation: Overly permissive 'shell:allow-execute' found in default capability"

    return True, f"Target window 'main' and all {len(required_perms)} granular permissions verified without over-privilege"


def check_menus_and_events() -> Tuple[bool, str]:
    if not LIB_RS.exists():
        return False, f"Missing {LIB_RS}"

    content = LIB_RS.read_text(encoding="utf-8")

    # Required CAD menu items, accelerators, and events
    required_bindings = [
        ("menu-import", "Ctrl+O", "outlaw-forge:menu-import"),
        ("menu-save", "Ctrl+S", "outlaw-forge:menu-save"),
        ("menu-export", "Ctrl+E", "outlaw-forge:menu-export"),
        ("menu-undo", "Ctrl+Z", "outlaw-forge:menu-undo"),
        ("menu-redo", "Ctrl+Y", "outlaw-forge:menu-redo"),
        ("menu-center-bed", "Ctrl+Space", "outlaw-forge:menu-center-bed"),
        ("menu-wireframe", "W", "outlaw-forge:menu-wireframe"),
        ("menu-reset-camera", "R", "outlaw-forge:menu-reset-camera"),
        ("menu-about", None, "outlaw-forge:menu-about"),
    ]

    for item_id, acc, event in required_bindings:
        # Check MenuItem construction
        if item_id not in content:
            return False, f"Menu item '{item_id}' not found in src/lib.rs"
        if acc:
            pattern = rf'MenuItem::with_id\(\s*app,\s*"{item_id}",\s*"[^"]*",\s*true,\s*Some\("{re.escape(acc)}"\)\)'
            if not re.search(pattern, content):
                return False, f"MenuItem '{item_id}' missing expected accelerator '{acc}'"

        # Check event emission in on_menu_event
        event_pattern = rf'"{item_id}"\s*=>\s*\{{[^}}]*emit\("{re.escape(event)}"'
        if not re.search(event_pattern, content):
            return False, f"Menu event handler for '{item_id}' does not emit '{event}'"

    # Verify standard window controls
    if '"menu-exit"' not in content or 'Alt+F4' not in content:
        return False, "Exit menu item with Alt+F4 not found"
    if '"menu-fullscreen"' not in content or 'F11' not in content:
        return False, "Fullscreen menu item with F11 not found"

    return True, "All 9 CAD menu accelerators, item IDs, and event emissions strictly verified"


def check_anti_slop_copy() -> Tuple[bool, str]:
    em_dash = "\u2014"
    en_dash = "\u2013"

    files_to_scan = [
        TAURI_CONF,
        CAPABILITIES,
        LIB_RS,
        MAIN_RS,
        CARGO_TOML,
    ]

    violations = []
    for f in files_to_scan:
        text = f.read_text(encoding="utf-8")
        for idx, line in enumerate(text.splitlines(), 1):
            s = line.strip()
            if s.startswith(("//", "/*", "*", "#")):
                continue
            if em_dash in line:
                violations.append(f"{f.name}:{idx} [em-dash]: {s}")
            if en_dash in line:
                violations.append(f"{f.name}:{idx} [en-dash]: {s}")

    if violations:
        return False, f"Anti-slop typography violations found: {violations}"

    return True, "Zero em-dashes or separator en-dashes found across all shell configuration and source files"


def main():
    print("=================================================================")
    print(" Challenger 2: Milestone M3 Shell Config & Menu Verifier         ")
    print("=================================================================")

    tests = [
        ("tauri.conf.json Shell Configuration", check_tauri_conf),
        ("capabilities/default.json Granular Permissions", check_capabilities),
        ("src-tauri/src/lib.rs Native CAD Menus & Event Emission", check_menus_and_events),
        ("Anti-Slop Typography Rule Compliance", check_anti_slop_copy),
    ]

    all_passed = True
    for name, fn in tests:
        passed, msg = fn()
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{status:6} {name}: {msg}")
        if not passed:
            all_passed = False

    print("=================================================================")
    print(f"Challenger 2 Verdict: {'APPROVE' if all_passed else 'REQUEST_CHANGES'}")
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
