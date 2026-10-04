"""
Unit and Integration Tests for Parametric 3D Infill & Lattice Generator (Milestone 1).
Verifies:
- All 4 infill patterns: Gyroid (TPMS), Honeycomb, Rectilinear, Cubic
- Watertightness and 2-manifold properties
- Density scaling (5% to 100%)
- Unit cell spacing in millimetres
- Volume reduction percentage calculations
- Solid mesh vs hollowed mesh workflows
- Dual-routed FastAPI endpoints:
  * POST /api/v1/projects/{project_id}/models/{model_id}/infill
  * POST /api/v1/models/{model_id}/infill
"""

import io
import pytest
import trimesh
import numpy as np
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.mesh import InfillPattern
from app.services.infill_service import infill_service


@pytest.fixture
def cube_20mm():
    """Standard 20mm test cube fixture."""
    return trimesh.creation.box(extents=(20.0, 20.0, 20.0))


@pytest.fixture
def sphere_30mm():
    """Standard 30mm diameter curved icosphere fixture."""
    return trimesh.creation.icosphere(subdivisions=2, radius=15.0)


@pytest.fixture
def cube_stl_bytes(cube_20mm):
    """STL binary bytes for cube_20mm."""
    out = io.BytesIO()
    cube_20mm.export(out, file_type="stl")
    return out.getvalue()


# ============================================================================
# Unit Tests: Procedural 3D Lattice Generation
# ============================================================================


def test_gyroid_tpms_infill_generation(cube_20mm):
    """Verify Gyroid TPMS generates watertight mesh with expected volume reduction."""
    result_mesh, vol_reduction = infill_service.generate_infill(
        mesh=cube_20mm,
        pattern=InfillPattern.GYROID,
        density=0.20,
        unit_cell_size_mm=10.0,
        wall_thickness_mm=2.0,
        hollow_first=True,
    )

    assert result_mesh is not None
    assert len(result_mesh.vertices) > 0
    assert len(result_mesh.faces) > 0
    assert result_mesh.is_watertight is True
    assert 20.0 <= vol_reduction <= 80.0
    # Bounding box should remain preserved within 20mm extents
    extents = result_mesh.extents
    assert np.allclose(extents, [20.0, 20.0, 20.0], atol=0.2)


def test_honeycomb_infill_generation(cube_20mm):
    """Verify Honeycomb hexagonal lattice generates watertight mesh."""
    result_mesh, vol_reduction = infill_service.generate_infill(
        mesh=cube_20mm,
        pattern=InfillPattern.HONEYCOMB,
        density=0.25,
        unit_cell_size_mm=8.0,
        wall_thickness_mm=2.0,
        hollow_first=True,
    )

    assert result_mesh is not None
    assert result_mesh.is_watertight is True
    assert vol_reduction > 10.0
    assert np.allclose(result_mesh.extents, [20.0, 20.0, 20.0], atol=0.2)


def test_rectilinear_infill_generation(cube_20mm):
    """Verify Rectilinear grid lattice generates watertight mesh."""
    result_mesh, vol_reduction = infill_service.generate_infill(
        mesh=cube_20mm,
        pattern=InfillPattern.RECTILINEAR,
        density=0.20,
        unit_cell_size_mm=10.0,
        wall_thickness_mm=2.0,
        hollow_first=True,
    )

    assert result_mesh is not None
    assert result_mesh.is_watertight is True
    assert vol_reduction > 10.0
    assert np.allclose(result_mesh.extents, [20.0, 20.0, 20.0], atol=0.2)


def test_cubic_infill_generation(cube_20mm):
    """Verify 3D Cubic orthogonal volumetric lattice generates watertight mesh."""
    result_mesh, vol_reduction = infill_service.generate_infill(
        mesh=cube_20mm,
        pattern=InfillPattern.CUBIC,
        density=0.20,
        unit_cell_size_mm=10.0,
        wall_thickness_mm=2.0,
        hollow_first=True,
    )

    assert result_mesh is not None
    assert result_mesh.is_watertight is True
    assert vol_reduction > 10.0
    assert np.allclose(result_mesh.extents, [20.0, 20.0, 20.0], atol=0.2)


# ============================================================================
# Parametric Scaling & Density Tests
# ============================================================================


def test_density_scaling_progression(cube_20mm):
    """Verify higher infill density yields lower volume reduction (higher final mass)."""
    _, red_10 = infill_service.generate_infill(
        mesh=cube_20mm,
        pattern=InfillPattern.RECTILINEAR,
        density=0.10,
        unit_cell_size_mm=10.0,
        hollow_first=True,
    )
    _, red_30 = infill_service.generate_infill(
        mesh=cube_20mm,
        pattern=InfillPattern.RECTILINEAR,
        density=0.30,
        unit_cell_size_mm=10.0,
        hollow_first=True,
    )
    _, red_60 = infill_service.generate_infill(
        mesh=cube_20mm,
        pattern=InfillPattern.RECTILINEAR,
        density=0.60,
        unit_cell_size_mm=10.0,
        hollow_first=True,
    )

    # Higher density leaves more internal material -> higher volume -> lower reduction %
    assert red_10 > red_30 > red_60


def test_solid_100_percent_density(cube_20mm):
    """Verify 100% density returns unchanged solid mesh with 0% reduction."""
    result_mesh, vol_reduction = infill_service.generate_infill(
        mesh=cube_20mm,
        pattern=InfillPattern.GYROID,
        density=1.0,
    )
    assert vol_reduction == 0.0
    assert np.isclose(result_mesh.volume, cube_20mm.volume, rtol=1e-3)


def test_unit_cell_size_variation(cube_20mm):
    """Verify varying unit cell spacing in mm operates deterministically."""
    mesh_5mm, _ = infill_service.generate_infill(
        mesh=cube_20mm,
        pattern=InfillPattern.HONEYCOMB,
        density=0.20,
        unit_cell_size_mm=5.0,
    )
    mesh_15mm, _ = infill_service.generate_infill(
        mesh=cube_20mm,
        pattern=InfillPattern.HONEYCOMB,
        density=0.20,
        unit_cell_size_mm=15.0,
    )

    assert mesh_5mm.is_watertight is True
    assert mesh_15mm.is_watertight is True
    # Smaller unit cells generate more internal cell walls and vertices
    assert len(mesh_5mm.vertices) > len(mesh_15mm.vertices)


def test_solid_infill_without_hollowing(cube_20mm):
    """Verify infilling directly into solid volume without shell (hollow_first=False)."""
    result_mesh, vol_reduction = infill_service.generate_infill(
        mesh=cube_20mm,
        pattern=InfillPattern.RECTILINEAR,
        density=0.25,
        unit_cell_size_mm=10.0,
        hollow_first=False,
    )

    assert result_mesh.is_watertight is True
    # Without outer shell, reduction should approach (1 - 0.25) = 75%
    assert 65.0 <= vol_reduction <= 85.0


def test_curved_geometry_infill(sphere_30mm):
    """Verify procedural infill on curved non-planar geometry (icosphere)."""
    result_mesh, vol_reduction = infill_service.generate_infill(
        mesh=sphere_30mm,
        pattern=InfillPattern.HONEYCOMB,
        density=0.20,
        unit_cell_size_mm=8.0,
        wall_thickness_mm=2.0,
        hollow_first=True,
    )

    assert result_mesh is not None
    assert result_mesh.is_watertight is True
    assert vol_reduction > 10.0


# ============================================================================
# Integration Tests: Dual-Routed API Endpoints
# ============================================================================


@pytest.mark.asyncio
async def test_api_generate_infill_project_endpoint(cube_stl_bytes):
    """Test POST /api/v1/projects/{project_id}/models/{model_id}/infill."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create project
        proj_resp = await client.post(
            "/api/v1/projects",
            json={"name": "Infill Test Project", "project_type": "Mechanical Part"},
        )
        assert proj_resp.status_code == 201
        proj_id = proj_resp.json()["id"]

        # 2. Import model
        files = {"file": ("test_cube.stl", cube_stl_bytes, "model/stl")}
        import_resp = await client.post(f"/api/v1/projects/{proj_id}/models/import", files=files)
        assert import_resp.status_code == 201
        model_id = import_resp.json()["id"]

        # 3. Request Gyroid infill via project route
        infill_payload = {
            "pattern": "gyroid",
            "density": 0.20,
            "unit_cell_size_mm": 10.0,
            "wall_thickness_mm": 2.0,
            "hollow_first": True,
        }
        resp = await client.post(
            f"/api/v1/projects/{proj_id}/models/{model_id}/infill",
            json=infill_payload,
        )
        assert resp.status_code == 200
        data = resp.json()

        assert data["success"] is True
        assert data["model_id"] == model_id
        assert data["infill_pattern"] == "gyroid"
        assert data["density"] == 0.20
        assert data["unit_cell_size_mm"] == 10.0
        assert data["wall_thickness_mm"] == 2.0
        assert data["volume_reduction_percent"] > 0.0
        assert data["vertex_count"] > 0
        assert data["triangle_count"] > 0
        assert "mesh_path" in data
        assert data["mesh_path"].startswith("working/")
        assert "bounding_box_mm" in data
        assert "width_mm" in data["bounding_box_mm"]

        # 4. Verify audit operation was recorded in project
        proj_get = await client.get(f"/api/v1/projects/{proj_id}")
        assert proj_get.status_code == 200
        ops = proj_get.json()["operations"]
        infill_ops = [op for op in ops if op["operation_type"] == "INFILL_GENERATE"]
        assert len(infill_ops) >= 1
        assert infill_ops[-1]["success"] is True


@pytest.mark.asyncio
async def test_api_generate_infill_direct_endpoint(cube_stl_bytes):
    """Test direct route POST /api/v1/models/{model_id}/infill."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create project & import model
        proj_resp = await client.post(
            "/api/v1/projects",
            json={"name": "Direct Infill Project", "project_type": "Mechanical Part"},
        )
        proj_id = proj_resp.json()["id"]

        files = {"file": ("direct_cube.stl", cube_stl_bytes, "model/stl")}
        import_resp = await client.post(f"/api/v1/projects/{proj_id}/models/import", files=files)
        model_id = import_resp.json()["id"]

        # 2. Call direct infill endpoint with Honeycomb pattern
        infill_payload = {
            "pattern": "honeycomb",
            "density": 0.30,
            "unit_cell_size_mm": 8.0,
            "wall_thickness_mm": 2.0,
            "hollow_first": True,
        }
        resp = await client.post(
            f"/api/v1/models/{model_id}/infill",
            json=infill_payload,
        )
        assert resp.status_code == 200
        data = resp.json()

        assert data["success"] is True
        assert data["infill_pattern"] == "honeycomb"
        assert data["density"] == 0.30
        assert data["volume_reduction_percent"] > 0.0


@pytest.mark.asyncio
async def test_api_generate_infill_not_found():
    """Verify 404 returned for non-existent model."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/models/non-existent-id/infill",
            json={"pattern": "gyroid", "density": 0.20},
        )
        assert resp.status_code == 404


# ============================================================================
# Unit & Integration Tests: Structural Rib Reinforcement & Drainage Channels
# ============================================================================


def test_reinforce_internal_ribs_generation(cube_20mm):
    """Verify parametric rib reinforcement generates valid watertight mesh with drainage hole."""
    result_mesh, rib_count, holes_count = infill_service.reinforce_internal_ribs(
        mesh=cube_20mm,
        rib_thickness_mm=1.5,
        rib_spacing_mm=8.0,
        rib_height_mm=3.0,
        drainage_hole_radius_mm=1.5,
        add_drainage_channel=True,
        drainage_axis="z",
        wall_thickness_mm=2.0,
    )

    assert result_mesh is not None
    assert len(result_mesh.vertices) > 0
    assert len(result_mesh.faces) > 0
    assert result_mesh.is_watertight is True
    assert rib_count >= 1
    assert holes_count == 1


@pytest.mark.asyncio
async def test_api_reinforce_ribs_endpoint(cube_stl_bytes):
    """Test API endpoint POST /api/v1/projects/{project_id}/models/{model_id}/reinforce_ribs."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        proj_resp = await client.post(
            "/api/v1/projects",
            json={"name": "Rib Project", "project_type": "Prop"},
        )
        proj_id = proj_resp.json()["id"]

        files = {"file": ("rib_cube.stl", cube_stl_bytes, "model/stl")}
        import_resp = await client.post(f"/api/v1/projects/{proj_id}/models/import", files=files)
        model_id = import_resp.json()["id"]

        rib_payload = {
            "rib_thickness_mm": 1.5,
            "rib_spacing_mm": 10.0,
            "rib_height_mm": 3.0,
            "drainage_hole_radius_mm": 2.0,
            "add_drainage_channel": True,
            "drainage_axis": "z",
            "wall_thickness_mm": 2.0,
        }
        resp = await client.post(
            f"/api/v1/projects/{proj_id}/models/{model_id}/reinforce_ribs",
            json=rib_payload,
        )
        assert resp.status_code == 200
        data = resp.json()

        assert data["success"] is True
        assert data["model_id"] == model_id
        assert data["rib_count"] >= 1
        assert data["drainage_holes_count"] == 1
        assert data["vertex_count"] > 0
        assert data["triangle_count"] > 0
        assert "mesh_path" in data

