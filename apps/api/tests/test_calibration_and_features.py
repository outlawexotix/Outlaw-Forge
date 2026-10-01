import pytest
from fastapi.testclient import TestClient
import trimesh

from app.services.adhesion_service import adhesion_service
from app.services.arrangement_service import arrangement_service
from app.services.calibration_service import calibration_service
from app.services.filament_service import filament_service
from app.services.layer_height_service import layer_height_service
from app.services.orientation_service import orientation_service
from app.models.calibration import (
    AdaptiveLayerPayload,
    AutoArrangePayload,
    AutoOrientPayload,
    CalibrationGeneratePayload,
    CostEstimationPayload,
    MouseEarPayload,
)


@pytest.fixture
def cube_mesh() -> trimesh.Trimesh:
    return trimesh.creation.box(extents=[20.0, 20.0, 20.0])


# --- Unit Tests: Calibration Artifact Service ---

def test_calibration_temp_tower():
    mesh, notes = calibration_service.generate_temp_tower(start_temp=220, end_temp=190, temp_step=10)
    assert mesh is not None
    assert len(mesh.faces) > 0
    assert len(notes) >= 3
    # 4 tiers (220, 210, 200, 190) + 3mm base = ~35mm
    assert mesh.extents[2] > 30.0


def test_calibration_flow_rate():
    mesh, notes = calibration_service.generate_flow_rate_swatches(start_pct=-10, end_pct=10, step_pct=5)
    assert mesh is not None
    assert mesh.extents[0] > 40.0
    assert len(notes) >= 2


def test_calibration_retraction_tower():
    mesh, notes = calibration_service.generate_retraction_tower(start_mm=1, end_mm=4, step_mm=1)
    assert mesh is not None
    assert mesh.extents[0] >= 20.0
    assert mesh.extents[2] > 20.0


def test_calibration_tolerance_gauge():
    mesh, notes = calibration_service.generate_tolerance_gauge(min_gap=0.1, max_gap=0.4, step_gap=0.1)
    assert mesh is not None
    assert len(mesh.vertices) > 100


def test_calibration_overhang_benchmark():
    mesh, notes = calibration_service.generate_overhang_benchmark()
    assert mesh is not None
    assert mesh.extents[0] > 40.0


def test_calibration_cube_v2():
    mesh, notes = calibration_service.generate_calibration_cube(size=20.0)
    assert mesh is not None
    assert abs(mesh.extents[0] - 20.0) < 2.0
    assert abs(mesh.extents[1] - 20.0) < 2.0


# --- Unit Tests: Auto-Orient Service ---

def test_auto_orient_cube(cube_mesh):
    payload = AutoOrientPayload(overhang_weight=1.0, height_weight=0.3, bed_contact_weight=0.5)
    oriented_mesh, rot_deg, orig_oh, opt_oh, reduction_pct = orientation_service.auto_orient(
        cube_mesh, payload
    )
    assert oriented_mesh is not None
    assert len(rot_deg) == 3
    assert opt_oh <= orig_oh + 1e-4


# --- Unit Tests: Mouse-Ear Brim Service ---

def test_mouse_ear_brim(cube_mesh):
    payload = MouseEarPayload(radius_mm=6.0, thickness_mm=0.2, auto_detect_corners=True)
    mod_mesh, ears_count, ear_pos, msg = adhesion_service.generate_mouse_ears(cube_mesh, payload)
    assert mod_mesh is not None
    assert ears_count >= 4
    assert len(ear_pos) >= 4
    assert "mouse-ear" in msg


# --- Unit Tests: Adaptive Layer Height Service ---

def test_adaptive_layer_height(cube_mesh):
    payload = AdaptiveLayerPayload(min_layer_height_mm=0.08, max_layer_height_mm=0.28, nominal_layer_height_mm=0.20)
    res = layer_height_service.compute_adaptive_profile(cube_mesh, "test-id", payload)
    assert res.total_layers_adaptive > 0
    assert res.total_layers_nominal > 0
    assert len(res.layer_curve) > 0


# --- Unit Tests: Filament & Cost Calculator ---

def test_filament_service_list():
    filaments = filament_service.list_filaments()
    assert len(filaments) >= 7
    pla = next((f for f in filaments if f.material == "PLA"), None)
    assert pla is not None
    assert pla.density_g_cm3 > 1.0


def test_filament_cost_estimate(cube_mesh):
    payload = CostEstimationPayload(filament_id="generic_pla", infill_percentage=20.0)
    res = filament_service.estimate_cost(cube_mesh, "cube-1", payload)
    assert res.estimated_mass_grams > 0.0
    assert res.estimated_filament_length_meters > 0.0
    assert res.estimated_material_cost_usd > 0.0


# --- Integration Tests: REST Endpoints ---

def test_api_calibration_workflow(client: TestClient):
    # 1. Create project
    proj_resp = client.post("/projects", json={"name": "Orca Calibration Test", "project_type": "Other"})
    assert proj_resp.status_code == 201
    proj_id = proj_resp.json()["id"]

    # 2. Generate calibration Temp Tower
    cal_payload = {
        "calibration_type": "temp_tower",
        "start_temp_c": 210,
        "end_temp_c": 190,
        "temp_step_c": 10,
    }
    cal_resp = client.post(f"/projects/{proj_id}/calibration/generate", json=cal_payload)
    assert cal_resp.status_code == 201
    cal_data = cal_resp.json()
    assert cal_data["calibration_type"] == "temp_tower"
    model_id = cal_data["model"]["id"]

    # 3. Test Auto-Orient endpoint
    orient_resp = client.post(f"/projects/{proj_id}/models/{model_id}/auto_orient", json={})
    assert orient_resp.status_code == 200
    orient_data = orient_resp.json()
    assert "optimal_rotation_deg" in orient_data

    # 4. Test Mouse-Ears endpoint
    ear_resp = client.post(
        f"/projects/{proj_id}/models/{model_id}/mouse_ears",
        json={"radius_mm": 5.0, "thickness_mm": 0.2},
    )
    assert ear_resp.status_code == 200
    assert ear_resp.json()["ears_added_count"] >= 4

    # 5. Test Adaptive Layers endpoint
    layer_resp = client.post(f"/projects/{proj_id}/models/{model_id}/adaptive_layers", json={})
    assert layer_resp.status_code == 200
    assert layer_resp.json()["total_layers_adaptive"] > 0

    # 6. Test Cost Estimation endpoint
    cost_resp = client.post(
        f"/projects/{proj_id}/models/{model_id}/estimate_cost",
        json={"filament_id": "generic_pla", "infill_percentage": 15.0},
    )
    assert cost_resp.status_code == 200
    assert cost_resp.json()["estimated_mass_grams"] > 0

    # 7. Test Filament library endpoint
    fil_resp = client.get(f"/projects/{proj_id}/filaments")
    assert fil_resp.status_code == 200
    assert len(fil_resp.json()) >= 7

    # 8. Test Auto-Arrange endpoint
    arrange_resp = client.post(f"/projects/{proj_id}/auto_arrange", json={"spacing_mm": 8.0})
    assert arrange_resp.status_code == 200
    assert len(arrange_resp.json()["arranged_models"]) >= 1
