"""Milestone M1 Empirical Stress Test Harness.

Executes comprehensive adversarial challenges for:
1. Storage paths & environment isolation (frozen vs non-frozen, APPDATA edge cases, path traversal, Windows sanitization)
2. PyInstaller spec validation (AST analysis, hidden imports, binaries, path independence)
3. CORS headers under Tauri and adversarial origins
4. Process lifecycle, port binding, and handshake resilience
"""

import ast
import asyncio
import io
import json
import os
import shutil
import socket
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

# Ensure apps/api is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "apps" / "api"))

from starlette.testclient import TestClient

results = []

def record(test_name: str, passed: bool, details: str):
    status = "PASS" if passed else "FAIL"
    results.append({"name": test_name, "status": status, "details": details})
    print(f"[{status}] {test_name}: {details}")


# =========================================================================
# DOMAIN 1: Storage Paths & Environment Isolation
# =========================================================================

def test_frozen_storage_custom_appdata():
    from app.services.storage import StorageService
    with tempfile.TemporaryDirectory() as td:
        fake_appdata = Path(td) / "Custom User" / "AppData" / "Roaming"
        with patch.dict(os.environ, {"APPDATA": str(fake_appdata)}), \
             patch.object(sys, "frozen", True, create=True):
            s = StorageService()
            expected = fake_appdata / "OutlawForge" / "data"
            passed = s.base_dir == expected.resolve() and s.original_dir.exists()
            record(
                "Frozen storage with custom APPDATA containing spaces",
                passed,
                f"Resolved base_dir: {s.base_dir} (expected: {expected.resolve()})"
            )

def test_frozen_storage_unset_appdata():
    from app.services.storage import StorageService
    from app.db.database import get_db_path
    from app.cli import get_default_desktop_dir

    env_copy = os.environ.copy()
    env_copy.pop("APPDATA", None)

    with patch.dict(os.environ, env_copy, clear=True), \
         patch.object(sys, "frozen", True, create=True):
        s = StorageService()
        db = get_db_path()
        cli_dir = get_default_desktop_dir()

        # Check if database, storage, and cli agree when APPDATA is unset
        db_parent = db.parent.parent  # ... / OutlawForge
        storage_parent = s.base_dir.parent  # ... / OutlawForge

        consistent = (db_parent == storage_parent)
        cli_consistent = (db_parent == cli_dir)

        record(
            "Unset APPDATA consistency between DB and StorageService",
            consistent,
            f"DB root: {db_parent}, Storage root: {storage_parent}"
        )
        record(
            "Unset APPDATA consistency between CLI default and DB/Storage",
            cli_consistent,
            f"CLI dir: {cli_dir}, DB/Storage root: {db_parent} (CLI uses AppData/Roaming fallback, DB uses ~ fallback)"
        )

def test_frozen_storage_empty_appdata():
    from app.services.storage import StorageService
    from app.db.database import get_db_path

    with patch.dict(os.environ, {"APPDATA": ""}), \
         patch.object(sys, "frozen", True, create=True):
        s = StorageService()
        db = get_db_path()
        # Path("") expands to current directory "."
        is_cwd_storage = (s.base_dir == (Path.cwd() / "OutlawForge" / "data").resolve())
        is_cwd_db = (db == (Path.cwd() / "OutlawForge" / "data" / "outlaw_forge.db").resolve())
        record(
            "Empty string APPDATA (APPDATA='') causes leak into CWD",
            not (is_cwd_storage or is_cwd_db),
            f"Storage resolved to {s.base_dir}, DB resolved to {db} (relative to CWD={Path.cwd()})"
        )

def test_storage_order_of_import_vulnerability():
    # Test if importing settings before configure_environment ignores --storage-dir
    import importlib
    import app.core.config as config_mod
    import app.services.storage as storage_mod
    from app.cli import configure_environment

    # Simulate settings already initialized with 'data'
    old_env = os.environ.get("STORAGE_BASE_DIR")
    try:
        with tempfile.TemporaryDirectory() as td:
            custom_dir = str(Path(td) / "cli_configured_dir")
            # If settings is already imported (normal in long-lived processes or when main imports config)
            configure_environment(storage_dir=custom_dir)
            # Recreate StorageService
            s = storage_mod.StorageService()
            passed = (s.base_dir == Path(custom_dir).resolve())
            record(
                "StorageService honors os.environ['STORAGE_BASE_DIR'] when settings is cached",
                passed,
                f"Resolved: {s.base_dir}, Expected: {Path(custom_dir).resolve()}"
            )
    finally:
        if old_env is not None:
            os.environ["STORAGE_BASE_DIR"] = old_env
        else:
            os.environ.pop("STORAGE_BASE_DIR", None)

def test_storage_path_traversal_and_sanitization():
    from app.services.storage import storage_service
    from fastapi import HTTPException

    # 1. Directory traversal attempt
    traversal_caught = False
    try:
        storage_service.resolve_path("../../etc/passwd")
    except HTTPException as e:
        traversal_caught = (e.status_code == 403)
    record("Path traversal '../../etc/passwd' blocked with 403", traversal_caught, "HTTP 403 returned")

    # 2. Filename sanitization
    # Test Windows reserved names and null bytes
    sanitized_nul = storage_service.sanitize_filename("model\x00_test.stl")
    passed_nul = "\x00" not in sanitized_nul
    record("Sanitize null bytes in filename", passed_nul, f"Result: '{sanitized_nul}'")

    sanitized_dots = storage_service.sanitize_filename("....//..//malicious.stl")
    passed_dots = not sanitized_dots.startswith("..") and "/" not in sanitized_dots and "\\" not in sanitized_dots
    record("Sanitize multiple dots and slashes", passed_dots, f"Result: '{sanitized_dots}'")


# =========================================================================
# DOMAIN 2: PyInstaller Spec Validation
# =========================================================================

def test_spec_file_deep_validation():
    spec_path = Path(__file__).resolve().parent.parent / "apps" / "api" / "outlaw_forge.spec"
    assert spec_path.exists()
    spec_code = spec_path.read_text(encoding="utf-8")

    tree = ast.parse(spec_code)
    record("PyInstaller spec AST parse validity", True, "Successfully parsed Python AST")

    # Check for critical hidden imports
    critical_imports = [
        "uvicorn", "uvicorn.protocols.http.h11_impl", "uvicorn.lifespan.on",
        "aiosqlite", "sqlite3",
        "manifold3d", "trimesh", "numpy", "scipy", "scipy.spatial.transform._rotation_groups",
        "shapely", "mapbox_earcut",
        "fastapi", "starlette", "pydantic", "pydantic_settings"
    ]
    missing = [m for m in critical_imports if f"'{m}'" not in spec_code and f'"{m}"' not in spec_code]
    record(
        "Critical hidden imports present in spec",
        len(missing) == 0,
        f"Missing: {missing}" if missing else f"All {len(critical_imports)} critical hidden imports confirmed"
    )

    # Check console=True on Windows
    has_console_true = "console=True" in spec_code
    record(
        "Spec sets console=True for Windows stdout pipe",
        has_console_true,
        "console=True is set in EXE()"
    )

    # Check COLLECT exists (--onedir)
    has_collect = "COLLECT(" in spec_code
    record(
        "Spec configures --onedir via COLLECT()",
        has_collect,
        "COLLECT() block present"
    )

    # Check spec relative path assumption
    uses_app_cli_rel = '["app/cli.py"]' in spec_code or "['app/cli.py']" in spec_code
    uses_specpath = "SPECPATH" in spec_code
    record(
        "Spec uses SPECPATH for location independence",
        uses_specpath,
        f"uses_specpath={uses_specpath}, relies on cwd being apps/api={uses_app_cli_rel}"
    )


# =========================================================================
# DOMAIN 3: CORS Headers Verification
# =========================================================================

def test_cors_matrix():
    from app.main import app
    client = TestClient(app)

    # 1. Allowed Tauri origins
    for origin in ["tauri://localhost", "http://tauri.localhost", "https://tauri.localhost"]:
        # Simple GET
        r = client.get("/health", headers={"Origin": origin})
        passed_get = (r.status_code == 200 and r.headers.get("access-control-allow-origin") == origin)
        record(f"CORS GET allowed for {origin}", passed_get, f"Status: {r.status_code}, ACAO: {r.headers.get('access-control-allow-origin')}")

        # Preflight OPTIONS
        r_opt = client.options("/health", headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type, authorization, x-custom"
        })
        passed_opt = (r_opt.status_code == 200 and r_opt.headers.get("access-control-allow-origin") == origin)
        record(f"CORS preflight allowed for {origin}", passed_opt, f"Status: {r_opt.status_code}, ACAO: {r_opt.headers.get('access-control-allow-origin')}")

    # 2. Adversarial origins
    disallowed = [
        "http://evil.com",
        "https://tauri.localhost.attacker.com",
        "http://attacker.com/tauri://localhost",
        "null",
        "http://localhost:8080"
    ]
    for origin in disallowed:
        r = client.get("/health", headers={"Origin": origin})
        # Disallowed origins must NOT receive an Access-Control-Allow-Origin matching the malicious origin
        acao = r.headers.get("access-control-allow-origin")
        passed = (acao != origin)
        record(f"CORS blocks disallowed origin {origin}", passed, f"ACAO: {acao}")


# =========================================================================
# DOMAIN 4: Port Resolution & Lifespan Handshake
# =========================================================================

def test_ephemeral_port_concurrency():
    from app.cli import resolve_port
    ports = [resolve_port(0) for _ in range(20)]
    all_valid = all(1024 <= p <= 65535 for p in ports)
    record("Ephemeral port 0 resolution returns valid ports", all_valid, f"Sample ports: {ports[:5]}")

def test_handshake_file_creation_and_flush():
    from app.main import app, lifespan
    with tempfile.TemporaryDirectory() as td:
        hs_path = Path(td) / "handshake.json"
        with patch.dict(os.environ, {"HANDSHAKE_FILE": str(hs_path), "PORT": "14567"}):
            app.state.port = 14567
            captured = io.StringIO()
            with patch("sys.stdout.write", side_effect=captured.write), patch("sys.stdout.flush") as mock_flush:
                async def run_lifespan():
                    async with lifespan(app):
                        pass
                asyncio.run(run_lifespan())
                
                stdout_ok = "HEALTH_OK: PORT=14567\n" in captured.getvalue()
                flush_called = mock_flush.called
                file_ok = hs_path.exists() and json.loads(hs_path.read_text()) == {"status": "healthy", "port": 14567}
                
                record(
                    "Lifespan stdout handshake and flush",
                    stdout_ok and flush_called,
                    f"stdout_ok={stdout_ok}, flush_called={flush_called}"
                )
                record(
                    "Lifespan HANDSHAKE_FILE JSON content",
                    file_ok,
                    f"file_exists={hs_path.exists()}"
                )


def main():
    print("=== STARTING ADVERSARIAL STRESS TEST HARNESS ===")
    test_frozen_storage_custom_appdata()
    test_frozen_storage_unset_appdata()
    test_frozen_storage_empty_appdata()
    test_storage_order_of_import_vulnerability()
    test_storage_path_traversal_and_sanitization()
    test_spec_file_deep_validation()
    test_cors_matrix()
    test_ephemeral_port_concurrency()
    test_handshake_file_creation_and_flush()
    print("=== SUMMARY OF FINDINGS ===")
    passes = sum(1 for r in results if r["status"] == "PASS")
    fails = sum(1 for r in results if r["status"] == "FAIL")
    print(f"Total: {len(results)} | Passed: {passes} | Failed: {fails}")
    return fails

if __name__ == "__main__":
    sys.exit(main())
