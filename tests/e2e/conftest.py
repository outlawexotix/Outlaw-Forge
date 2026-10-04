"""
conftest.py — End-to-End Test Fixtures & Harness for Outlaw Forge Phase 10
========================================================================
Provides isolated database instances, TestClient configuration,
geometric sample meshes, and helper orchestration utilities for
the 4-Tier E2E test suite.
"""

import io
import os
import sys
import tempfile
from pathlib import Path
from typing import AsyncGenerator, Dict, Tuple

import aiosqlite
import pytest
import trimesh
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Ensure apps/api is on sys.path for direct imports
API_ROOT = Path(__file__).resolve().parent.parent.parent / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.db.database import get_db, init_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture
def temp_db_file():
    """Create a temporary SQLite database file for isolated test execution."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        temp_path = f.name

    os.environ["SQLITE_DB_PATH"] = temp_path
    yield temp_path

    if os.path.exists(temp_path):
        try:
            os.remove(temp_path)
        except OSError:
            pass


@pytest.fixture
def e2e_client(temp_db_file) -> TestClient:
    """Provide a TestClient with a fresh isolated SQLite database and schema."""
    async def override_get_db() -> AsyncGenerator[aiosqlite.Connection, None]:
        async with aiosqlite.connect(temp_db_file) as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute("PRAGMA foreign_keys = ON;")
            yield conn

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        import asyncio
        asyncio.run(init_db(temp_db_file))
        yield client

    app.dependency_overrides.clear()


@pytest.fixture(scope="session")
def cube_20mm_bytes() -> bytes:
    """Generate 20x20x20 mm solid calibration cube STL."""
    mesh = trimesh.creation.box(extents=(20.0, 20.0, 20.0))
    buf = io.BytesIO()
    mesh.export(buf, file_type="stl")
    return buf.getvalue()


@pytest.fixture(scope="session")
def cylinder_30mm_bytes() -> bytes:
    """Generate 30 mm height, 10 mm radius cylinder STL."""
    mesh = trimesh.creation.cylinder(radius=10.0, height=30.0)
    buf = io.BytesIO()
    mesh.export(buf, file_type="stl")
    return buf.getvalue()


@pytest.fixture(scope="session")
def thin_plate_bytes() -> bytes:
    """Generate extreme aspect-ratio 100x100x1 mm flat sheet STL."""
    mesh = trimesh.creation.box(extents=(100.0, 100.0, 1.0))
    buf = io.BytesIO()
    mesh.export(buf, file_type="stl")
    return buf.getvalue()


@pytest.fixture(scope="session")
def tall_needle_bytes() -> bytes:
    """Generate extreme aspect-ratio 1x1x100 mm slender needle STL."""
    mesh = trimesh.creation.box(extents=(1.0, 1.0, 100.0))
    buf = io.BytesIO()
    mesh.export(buf, file_type="stl")
    return buf.getvalue()


@pytest.fixture(scope="session")
def micro_cube_bytes() -> bytes:
    """Generate 1.0x1.0x1.0 mm micro cube STL."""
    mesh = trimesh.creation.box(extents=(1.0, 1.0, 1.0))
    buf = io.BytesIO()
    mesh.export(buf, file_type="stl")
    return buf.getvalue()


def create_e2e_project(client: TestClient, name: str = "Phase 10 E2E Project") -> str:
    """Helper: Create an isolated project and return project_id."""
    resp = client.post(
        "/projects",
        json={
            "name": name,
            "description": "E2E verification project for Phase 10",
            "project_type": "Mechanical Part",
            "selected_printer_id": "printer_ender_3",
        },
    )
    assert resp.status_code == 201, f"Failed to create project: {resp.text}"
    return resp.json()["id"]


def import_e2e_model(
    client: TestClient, project_id: str, stl_bytes: bytes, filename: str = "test_mesh.stl"
) -> Dict:
    """Helper: Import an STL mesh into a project and return working model dict."""
    files = {"file": (filename, stl_bytes, "application/octet-stream")}
    resp = client.post(f"/projects/{project_id}/models/import", files=files)
    assert resp.status_code == 201, f"Failed to import model: {resp.text}"
    return resp.json()


def is_route_available(fastapi_app: FastAPI, path_suffix: str, method: str = "POST") -> bool:
    """Inspect FastAPI route table to check whether an endpoint is registered."""
    try:
        from fastapi import routing
        for rc in routing.iter_route_contexts(fastapi_app.routes):
            if hasattr(rc, "path") and hasattr(rc, "methods"):
                if path_suffix in rc.path and method.upper() in rc.methods:
                    return True
    except Exception:
        pass
    for route in fastapi_app.routes:
        if hasattr(route, "path") and hasattr(route, "methods"):
            if path_suffix in route.path and method.upper() in route.methods:
                return True
    return False


def check_or_skip_endpoint(fastapi_app: FastAPI, path_suffix: str, milestone_label: str = "M1"):
    """Pytest helper: Skip test cleanly if the feature endpoint is not yet mounted."""
    if not is_route_available(fastapi_app, path_suffix):
        pytest.skip(
            f"Endpoint containing '{path_suffix}' is not yet registered in FastAPI router ({milestone_label} in progress)"
        )
