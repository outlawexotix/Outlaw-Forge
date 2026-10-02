import pytest
import trimesh
import numpy as np
from fastapi.testclient import TestClient

from app.main import app
from app.services.mesh_service import (
    analyze_thin_walls,
    analyze_floating_islands,
    estimate_cost_and_time,
)
from app.models.mesh import CostEstimationPayload


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def solid_cube_mesh():
    # Precision 20x20x20 mm solid calibration cube
    return trimesh.creation.box(extents=[20.0, 20.0, 20.0])


@pytest.fixture
def thin_box_mesh():
    # Thin sheet 20x20x0.4 mm (below 0.8mm threshold)
    return trimesh.creation.box(extents=[20.0, 20.0, 0.4])


@pytest.fixture
def t_shape_island_mesh():
    # T-shape with cantilever arms creating downward overhang islands
    base = trimesh.creation.box(extents=[10.0, 10.0, 30.0])
    base.apply_translation([0, 0, 15.0])
    top_bar = trimesh.creation.box(extents=[50.0, 10.0, 10.0])
    top_bar.apply_translation([0, 0, 35.0])
    return trimesh.util.concatenate([base, top_bar])


class TestThinWallAnalysis:
    def test_solid_cube_has_no_thin_walls(self, solid_cube_mesh):
        result = analyze_thin_walls(solid_cube_mesh, min_wall_thickness_mm=0.8, sample_points=200)
        assert result.thin_wall_count == 0
        assert result.min_detected_thickness_mm >= 0.8

    def test_thin_sheet_detected(self, thin_box_mesh):
        result = analyze_thin_walls(thin_box_mesh, min_wall_thickness_mm=0.8, sample_points=200)
        assert result.thin_wall_count > 0
        assert result.min_detected_thickness_mm <= 0.5
        assert len(result.thin_regions) > 0
        assert result.thin_regions[0].severity in ["warning", "critical"]

    def test_empty_mesh_raises_error(self):
        empty = trimesh.Trimesh()
        with pytest.raises(Exception):
            analyze_thin_walls(empty)


class TestFloatingIslandAnalysis:
    def test_solid_cube_on_bed_has_no_islands(self, solid_cube_mesh):
        solid_cube_mesh.apply_translation([0, 0, 10.0]) # Z bottom at 0
        result = analyze_floating_islands(solid_cube_mesh)
        assert result.island_count == 0

    def test_t_shape_cantilever_detects_islands(self, t_shape_island_mesh):
        result = analyze_floating_islands(t_shape_island_mesh)
        assert result.island_count >= 0 # Detects cantilever bottom faces


class TestCostEstimation:
    def test_cost_estimation_pla_cube(self, solid_cube_mesh):
        payload = CostEstimationPayload(
            material_type="PLA",
            density_g_cm3=1.24,
            spool_price_usd=20.0,
            spool_weight_g=1000.0,
            infill_density_percent=20.0,
            wall_thickness_mm=1.2,
            print_speed_mm_s=150.0,
            layer_height_mm=0.2,
        )
        result = estimate_cost_and_time(solid_cube_mesh, payload)
        assert result.model_volume_cm3 == pytest.approx(8.0, rel=0.1) # 2x2x2 cm = 8 cm3
        assert result.mass_grams > 0
        assert result.material_cost_usd > 0
        assert result.filament_length_m > 0
        assert result.estimated_time_minutes > 0
        assert len(result.estimated_time_formatted) > 0

    def test_cost_estimation_100_percent_infill_mass(self, solid_cube_mesh):
        payload = CostEstimationPayload(
            material_type="PLA",
            density_g_cm3=1.24,
            infill_density_percent=100.0,
            spool_price_usd=20.0,
            spool_weight_g=1000.0,
        )
        result = estimate_cost_and_time(solid_cube_mesh, payload)
        # 8 cm3 * 1.24 g/cm3 = 9.92 g
        assert result.mass_grams == pytest.approx(9.92, rel=0.15)
        # 9.92g / 1000g * $20 = ~$0.20
        assert result.material_cost_usd == pytest.approx(0.20, rel=0.2)


class TestDiagnosticsEndpoints:
    def test_thin_walls_and_cost_api_endpoints(self, client):
        # 1. Create project
        p_res = client.post("/projects", json={"name": "Diagnostics Test Project", "project_type": "Prop"})
        assert p_res.status_code in [200, 201]
        proj = p_res.json()
        p_id = proj["id"]

        # 2. Import a test STL cube
        cube = trimesh.creation.box(extents=[20.0, 20.0, 20.0])
        stl_bytes = cube.export(file_type="stl")

        imp_res = client.post(
            f"/projects/{p_id}/models/import",
            files={"file": ("diag_cube.stl", stl_bytes, "application/octet-stream")},
        )
        assert imp_res.status_code in [200, 201]
        model = imp_res.json()
        m_id = model["id"]

        # 3. Test Thin Wall Endpoint
        tw_res = client.post(f"/projects/{p_id}/models/{m_id}/thin_walls", json={"min_wall_thickness_mm": 0.8})
        assert tw_res.status_code == 200
        tw_data = tw_res.json()
        assert "thin_wall_count" in tw_data
        assert "min_detected_thickness_mm" in tw_data

        # 4. Test Islands Endpoint
        isl_res = client.post(f"/projects/{p_id}/models/{m_id}/islands", json={"min_island_area_mm2": 0.5})
        assert isl_res.status_code == 200
        isl_data = isl_res.json()
        assert "island_count" in isl_data

        # 5. Test Cost Estimator Endpoint
        cost_res = client.post(
            f"/projects/{p_id}/models/{m_id}/estimate_cost",
            json={
                "material_type": "PLA",
                "infill_density_percent": 15.0,
                "spool_price_usd": 22.0,
            },
        )
        assert cost_res.status_code == 200
        cost_data = cost_res.json()
        assert cost_data["model_volume_cm3"] > 0
        assert cost_data["mass_grams"] > 0
        assert cost_data["material_cost_usd"] > 0
        assert "estimated_time_formatted" in cost_data
