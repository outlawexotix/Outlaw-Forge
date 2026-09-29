import os
from pathlib import Path
import tempfile
from typing import AsyncGenerator
import aiosqlite
import pytest
import trimesh
from fastapi.testclient import TestClient

from app.db.database import get_db, init_db
from app.main import app
from app.models.printer import PrinterProfile


@pytest.fixture
def temp_db_path():
    """Create a temporary SQLite database file for isolated testing."""
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
def client(temp_db_path):
    """Provide a TestClient with a fresh isolated SQLite database."""
    async def override_get_db() -> AsyncGenerator[aiosqlite.Connection, None]:
        async with aiosqlite.connect(temp_db_path) as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute("PRAGMA foreign_keys = ON;")
            yield conn

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        import asyncio
        asyncio.run(init_db(temp_db_path))
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    """Return path to test fixtures directory and ensure standard test meshes exist."""
    fixtures_path = Path(__file__).parent / "fixtures"
    fixtures_path.mkdir(parents=True, exist_ok=True)

    cube_20 = fixtures_path / "cube_20mm.stl"
    if not cube_20.exists():
        mesh_20 = trimesh.creation.box(extents=(20.0, 20.0, 20.0))
        mesh_20.export(str(cube_20))

    cube_300 = fixtures_path / "cube_300mm.stl"
    if not cube_300.exists():
        mesh_300 = trimesh.creation.box(extents=(300.0, 300.0, 300.0))
        mesh_300.export(str(cube_300))

    return fixtures_path


@pytest.fixture
def cube_20mm_path(fixtures_dir: Path) -> Path:
    return fixtures_dir / "cube_20mm.stl"


@pytest.fixture
def cube_300mm_path(fixtures_dir: Path) -> Path:
    return fixtures_dir / "cube_300mm.stl"


@pytest.fixture
def cube_20mm_mesh(cube_20mm_path: Path) -> trimesh.Trimesh:
    return trimesh.load(str(cube_20mm_path))


@pytest.fixture
def cube_300mm_mesh(cube_300mm_path: Path) -> trimesh.Trimesh:
    return trimesh.load(str(cube_300mm_path))


@pytest.fixture
def ender3_profile() -> PrinterProfile:
    return PrinterProfile(
        id="ender-3-standard",
        manufacturer="Creality",
        model="Ender-3",
        build_width_mm=220.0,
        build_depth_mm=220.0,
        build_height_mm=250.0,
        nozzle_diameter_mm=0.4,
        notes="Standard Creality Ender-3 profile",
    )


@pytest.fixture
def ender3_s1_profile() -> PrinterProfile:
    return PrinterProfile(
        id="ender-3-s1",
        manufacturer="Creality",
        model="Ender-3 S1",
        build_width_mm=220.0,
        build_depth_mm=220.0,
        build_height_mm=270.0,
        nozzle_diameter_mm=0.4,
        notes="Creality Ender-3 S1 profile",
    )
