"""Unit and integration tests for Outlaw Forge CLI and PyInstaller sidecar configuration."""

import ast
import io
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch
import pytest

from app.cli import (
    configure_environment,
    get_default_desktop_dir,
    parse_args,
    resolve_port,
)
from app.core.config import settings
from app.db.database import get_db_path
from app.main import app, lifespan
from app.services.storage import StorageService


def test_parse_args_defaults():
    """Verify default CLI arguments."""
    args = parse_args([])
    assert args.host == "127.0.0.1"
    assert args.port == 8000
    assert args.storage_dir is None
    assert args.db_path is None
    assert args.handshake_file is None


def test_parse_args_custom_values():
    """Verify custom CLI argument parsing."""
    args = parse_args(
        [
            "--host",
            "0.0.0.0",
            "--port",
            "9050",
            "--storage-dir",
            "/tmp/custom_storage",
            "--db-path",
            "/tmp/custom.db",
            "--handshake-file",
            "/tmp/handshake.json",
        ]
    )
    assert args.host == "0.0.0.0"
    assert args.port == 9050
    assert args.storage_dir == "/tmp/custom_storage"
    assert args.db_path == "/tmp/custom.db"
    assert args.handshake_file == "/tmp/handshake.json"


def test_resolve_port_explicit():
    """Explicit ports should be returned directly without modification."""
    assert resolve_port(8000) == 8000
    assert resolve_port(9050) == 9050
    assert resolve_port(12345) == 12345


def test_resolve_port_ephemeral():
    """Port 0 should dynamically bind an ephemeral socket and return a free port."""
    port1 = resolve_port(0, host="127.0.0.1")
    assert isinstance(port1, int)
    assert 1024 <= port1 <= 65535

    port2 = resolve_port(0, host="127.0.0.1")
    assert isinstance(port2, int)
    assert 1024 <= port2 <= 65535


def test_cors_contains_tauri_origins():
    """Verify BACKEND_CORS_ORIGINS includes required Tauri desktop origins."""
    required_origins = [
        "tauri://localhost",
        "http://tauri.localhost",
        "https://tauri.localhost",
    ]
    for origin in required_origins:
        assert origin in settings.BACKEND_CORS_ORIGINS


def test_get_default_desktop_dir():
    """Verify default desktop directory resolution."""
    desktop_dir = get_default_desktop_dir()
    assert isinstance(desktop_dir, Path)
    assert "OutlawForge" in str(desktop_dir) or "outlaw-forge" in str(desktop_dir)


def test_frozen_path_resolution_db(tmp_path, monkeypatch):
    """Verify SQLite DB path resolves to APPDATA when running in frozen mode."""
    fake_appdata = tmp_path / "AppData" / "Roaming"
    fake_appdata.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("APPDATA", str(fake_appdata))
    monkeypatch.delenv("SQLITE_DB_PATH", raising=False)

    # 1. Standard development mode (sys.frozen is False)
    with patch.object(sys, "frozen", False, create=True):
        dev_path = get_db_path()
        assert "OutlawForge" not in str(dev_path)
        assert dev_path.name == "outlaw_forge.db"

    # 2. Frozen mode (sys.frozen is True)
    with patch.object(sys, "frozen", True, create=True):
        frozen_path = get_db_path()
        assert str(frozen_path).startswith(str(fake_appdata))
        assert "OutlawForge" in str(frozen_path)
        assert frozen_path.name == "outlaw_forge.db"

    # 3. Explicit absolute path override in frozen mode
    custom_abs_path = str(tmp_path / "override.db")
    with patch.object(sys, "frozen", True, create=True):
        custom_path = get_db_path(custom_abs_path)
        assert custom_path == Path(custom_abs_path).resolve()


def test_frozen_path_resolution_storage(tmp_path, monkeypatch):
    """Verify StorageService resolves base_dir to APPDATA when running in frozen mode."""
    fake_appdata = tmp_path / "AppData" / "Roaming"
    fake_appdata.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("APPDATA", str(fake_appdata))
    monkeypatch.delenv("STORAGE_BASE_DIR", raising=False)

    # 1. Standard development mode (sys.frozen is False)
    with patch.object(sys, "frozen", False, create=True):
        dev_storage = StorageService()
        assert "OutlawForge" not in str(dev_storage.base_dir)

    # 2. Frozen mode (sys.frozen is True)
    with patch.object(sys, "frozen", True, create=True):
        frozen_storage = StorageService()
        assert str(frozen_storage.base_dir).startswith(str(fake_appdata))
        assert "OutlawForge" in str(frozen_storage.base_dir)
        assert frozen_storage.original_dir.exists()
        assert frozen_storage.working_dir.exists()
        assert frozen_storage.exports_dir.exists()


def test_configure_environment_custom(tmp_path):
    """Verify configure_environment sets custom environment variables."""
    custom_storage = str(tmp_path / "custom_storage")
    custom_db = str(tmp_path / "custom.db")
    custom_hs = str(tmp_path / "hs.json")

    configure_environment(
        storage_dir=custom_storage,
        db_path=custom_db,
        handshake_file=custom_hs,
    )

    assert os.environ["STORAGE_BASE_DIR"] == str(Path(custom_storage).resolve())
    assert os.environ["SQLITE_DB_PATH"] == str(Path(custom_db).resolve())
    assert os.environ["HANDSHAKE_FILE"] == str(Path(custom_hs).resolve())


def test_configure_environment_frozen_defaults(tmp_path, monkeypatch):
    """Verify configure_environment defaults to APPDATA in frozen mode."""
    fake_appdata = tmp_path / "AppData" / "Roaming"
    fake_appdata.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("APPDATA", str(fake_appdata))
    monkeypatch.delenv("STORAGE_BASE_DIR", raising=False)
    monkeypatch.delenv("SQLITE_DB_PATH", raising=False)
    monkeypatch.delenv("HANDSHAKE_FILE", raising=False)

    with patch.object(sys, "frozen", True, create=True):
        configure_environment()

    assert "OutlawForge" in os.environ["STORAGE_BASE_DIR"]
    assert "OutlawForge" in os.environ["SQLITE_DB_PATH"]


@pytest.mark.asyncio
async def test_lifespan_handshake_emission(tmp_path, monkeypatch):
    """Verify that lifespan startup emits HEALTH_OK: PORT=<PORT> and writes handshake file."""
    handshake_file = tmp_path / "handshake.json"
    monkeypatch.setenv("HANDSHAKE_FILE", str(handshake_file))
    monkeypatch.setenv("PORT", "9876")

    app.state.port = 9876

    captured_stdout = io.StringIO()
    with patch("sys.stdout.write", side_effect=captured_stdout.write), patch(
        "sys.stdout.flush"
    ) as mock_flush:
        async with lifespan(app):
            # Assert stdout was flushed
            assert mock_flush.called
            output = captured_stdout.getvalue()
            assert "HEALTH_OK: PORT=9876\n" in output

    # Assert handshake file was written
    assert handshake_file.exists()
    content = json.loads(handshake_file.read_text(encoding="utf-8"))
    assert content["status"] == "healthy"
    assert content["port"] == 9876


def test_spec_file_validity_and_contents():
    """Verify outlaw_forge.spec exists, parses as valid Python AST, and contains required imports."""
    spec_path = Path(__file__).resolve().parent.parent / "outlaw_forge.spec"
    assert spec_path.exists(), f"PyInstaller spec not found at {spec_path}"

    spec_code = spec_path.read_text(encoding="utf-8")
    # Verify syntax validity
    parsed_ast = ast.parse(spec_code)
    assert parsed_ast is not None

    required_hidden_imports = [
        "uvicorn",
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        "aiosqlite",
        "trimesh",
        "manifold3d",
        "numpy",
        "scipy.spatial.transform._rotation_groups",
    ]

    for item in required_hidden_imports:
        assert item in spec_code, f"Required hidden import '{item}' missing from outlaw_forge.spec"

    # Verify --onedir COLLECT step
    assert "COLLECT(" in spec_code, "outlaw_forge.spec must define COLLECT for --onedir distribution"
    assert "name='outlaw-forge-api'" in spec_code or 'name="outlaw-forge-api"' in spec_code


def test_cli_direct_script_help():
    """Verify python apps/api/app/cli.py --help can be invoked directly as a script."""
    cli_path = Path(__file__).resolve().parent.parent / "app" / "cli.py"
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)

    res = subprocess.run(
        [sys.executable, str(cli_path), "--help"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=10,
        env=env,
    )
    assert res.returncode == 0
    assert "outlaw-forge-api" in res.stdout or "usage:" in res.stdout.lower()


def test_storage_service_dynamic_env_override(tmp_path, monkeypatch):
    """Verify StorageService dynamically honors os.environ['STORAGE_BASE_DIR'] even if settings was pre-cached."""
    custom_dir = tmp_path / "dynamic_storage_dir"
    monkeypatch.setenv("STORAGE_BASE_DIR", str(custom_dir))

    service = StorageService()
    assert service.base_dir == custom_dir.resolve()
    assert service.original_dir.exists()


def test_empty_appdata_resolution_no_cwd_leak(monkeypatch):
    """Verify APPDATA='' does not leak into current working directory in frozen mode."""
    monkeypatch.setenv("APPDATA", "")
    monkeypatch.delenv("SQLITE_DB_PATH", raising=False)
    monkeypatch.delenv("STORAGE_BASE_DIR", raising=False)

    with patch.object(sys, "frozen", True, create=True):
        db_path = get_db_path()
        storage = StorageService()

        cwd_path = Path.cwd().resolve()
        assert not str(db_path).startswith(str(cwd_path))
        assert not str(storage.base_dir).startswith(str(cwd_path))
        assert "OutlawForge" in str(db_path)
        assert "OutlawForge" in str(storage.base_dir)
