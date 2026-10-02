import io
import pytest
import trimesh
import numpy as np
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.masksmith_service import masksmith_service
from app.services.figureforge_service import figureforge_service


@pytest.fixture
def test_cube():
    return trimesh.creation.box(extents=(30.0, 20.0, 40.0))


@pytest.fixture
def cube_stl_bytes(test_cube):
    out = io.BytesIO()
    test_cube.export(out, file_type="stl")
    return out.getvalue()


# ============================================================================
# MASKSMITH UNIT TESTS
# ============================================================================

def test_masksmith_analysis_and_scale(test_cube):
    analysis = masksmith_service.analyze_mask_fit(test_cube, model_id="test_model")
    assert analysis.inner_width_mm == 30.0
    assert analysis.inner_depth_mm == 20.0
    assert analysis.inner_height_mm == 40.0
    assert analysis.recommended_scale_male_pct > 100.0

    scaled_mesh, scale_factor = masksmith_service.scale_mask_fit(
        mesh=test_cube,
        target_preset="Adult Male (L/XL - 155mm)",
        padding_clearance_mm=8.0,
        uniform=True,
    )
    # Expected target width: 155 + 8 = 163mm
    assert pytest.approx(float(scaled_mesh.extents[0]), rel=1e-2) == 163.0
    assert scale_factor > 1.0


def test_masksmith_magnet_punch(test_cube):
    punched, positions, dia, depth = masksmith_service.punch_magnet_sockets(
        mesh=test_cube,
        magnet_preset="8x3mm (D:8mm, H:3mm)",
        placement_mode="perimeter_4_corner",
        margin_inset_mm=4.0,
    )
    assert punched is not None
    assert len(positions) == 4
    assert dia == 8.0
    assert depth == 3.0


def test_masksmith_strap_slots(test_cube):
    punched, positions, sw, st = masksmith_service.punch_strap_slots(
        mesh=test_cube,
        strap_preset="25mm (1in) Tactical Webbing",
        placement="temple_bilateral",
        inset_from_edge_mm=5.0,
    )
    assert punched is not None
    assert len(positions) == 2
    assert sw > 20.0
    assert st > 2.0


# ============================================================================
# FIGUREFORGE UNIT TESTS
# ============================================================================

def test_figureforge_com_analysis(test_cube):
    com = figureforge_service.analyze_center_of_mass(test_cube, model_id="test_figure")
    assert len(com.center_of_mass) == 3
    assert com.stability_status in ["STABLE", "MARGINAL", "TOPPLE_RISK"]
    assert com.tipping_angle_deg > 0.0
    assert com.recommended_plinth_diameter_mm > 30.0


def test_figureforge_plinth_generation():
    for shape in ["cylinder", "hexagon", "octagon", "stepped_round", "square_chamfered"]:
        plinth = figureforge_service.generate_plinth(
            shape=shape,
            diameter_mm=75.0,
            height_mm=12.0,
            add_figure_sockets=True,
            socket_diameter_mm=5.0,
            socket_depth_mm=6.0,
            socket_spacing_mm=20.0,
            add_nameplate_recess=True,
        )
        assert plinth is not None
        assert len(plinth.faces) > 0
        assert pytest.approx(float(plinth.bounds[0][2]), abs=1e-2) == 0.0


def test_figureforge_key_pegs(test_cube):
    pegged, positions, dia, length = figureforge_service.create_key_pegs(
        mesh=test_cube,
        peg_shape="cylinder",
        peg_diameter_mm=4.8,
        peg_length_mm=8.0,
        foot_offset_mm=8.0,
        dual_feet_pegs=True,
    )
    assert pegged is not None
    assert len(positions) == 2
    assert dia == 4.8
    assert length == 8.0
    # Peg extends below original base
    assert float(pegged.bounds[0][2]) < float(test_cube.bounds[0][2])


# ============================================================================
# END-TO-END STUDIOS API INTEGRATION TEST
# ============================================================================

def test_studios_api_endpoints(client, cube_stl_bytes):
    # 1. Create project
    resp = client.post(
        "/api/v1/projects",
        json={"name": "Cosplay & Collectibles Project", "project_type": "Mask"},
    )
    assert resp.status_code == 201
    proj = resp.json()
    proj_id = proj["id"]

    # 2. Import model
    files = {"file": ("mask_base.stl", cube_stl_bytes, "model/stl")}
    resp = client.post(f"/api/v1/projects/{proj_id}/models/import", files=files)
    assert resp.status_code == 201
    model = resp.json()
    model_id = model["id"]

    # 3. MaskSmith: Fit Analyze
    resp = client.post(f"/api/v1/projects/{proj_id}/models/{model_id}/masksmith/fit-analyze")
    assert resp.status_code == 200
    analysis = resp.json()
    assert "inner_width_mm" in analysis
    assert "recommended_scale_male_pct" in analysis

    # 4. MaskSmith: Auto-Scale
    resp = client.post(
        f"/api/v1/projects/{proj_id}/models/{model_id}/masksmith/auto-scale",
        json={"target_preset": "Adult Male (L/XL - 155mm)", "padding_clearance_mm": 8.0},
    )
    assert resp.status_code == 200
    scaled_model = resp.json()
    assert scaled_model["bounds"]["dimensions_mm"][0] > 100.0

    # 5. MaskSmith: Punch Magnets
    resp = client.post(
        f"/api/v1/projects/{proj_id}/models/{model_id}/masksmith/punch-magnets",
        json={"magnet_preset": "8x3mm (D:8mm, H:3mm)", "placement_mode": "perimeter_4_corner"},
    )
    assert resp.status_code == 200
    mag_res = resp.json()
    assert mag_res["sockets_punched"] == 4

    # 6. MaskSmith: Punch Strap Slots
    resp = client.post(
        f"/api/v1/projects/{proj_id}/models/{model_id}/masksmith/punch-strap-slots",
        json={"strap_preset": "25mm (1in) Tactical Webbing", "placement": "temple_bilateral"},
    )
    assert resp.status_code == 200
    strap_res = resp.json()
    assert strap_res["slots_punched"] == 2

    # 7. FigureForge: Center of Mass Analyze
    resp = client.post(f"/api/v1/projects/{proj_id}/models/{model_id}/figureforge/com-analyze")
    assert resp.status_code == 200
    com_res = resp.json()
    assert "stability_status" in com_res
    assert "center_of_mass" in com_res

    # 8. FigureForge: Generate Plinth
    resp = client.post(
        f"/api/v1/projects/{proj_id}/models/{model_id}/figureforge/generate-plinth",
        json={"shape": "stepped_round", "diameter_mm": 80.0, "height_mm": 15.0, "add_figure_sockets": True},
    )
    assert resp.status_code == 200
    plinth_res = resp.json()
    assert plinth_res["shape"] == "stepped_round"
    assert "plinth_model" in plinth_res

    # 9. FigureForge: Create Key Pegs
    resp = client.post(
        f"/api/v1/projects/{proj_id}/models/{model_id}/figureforge/create-key-pegs",
        json={"peg_shape": "cylinder", "peg_diameter_mm": 4.8, "peg_length_mm": 8.0, "dual_feet_pegs": True},
    )
    assert resp.status_code == 200
    peg_res = resp.json()
    assert peg_res["pegs_added_count"] == 2

