import io
import pytest
import trimesh
import numpy as np
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.mesh_service import mesh_service


@pytest.fixture
def cube_mesh():
    return trimesh.creation.box(extents=(20.0, 20.0, 20.0))


@pytest.fixture
def cube_stl_bytes(cube_mesh):
    out = io.BytesIO()
    cube_mesh.export(out, file_type="stl")
    return out.getvalue()


def test_hollow_mesh(cube_mesh):
    hollowed, vol_saved, drain_holes = mesh_service.hollow_mesh(
        mesh=cube_mesh,
        wall_thickness_mm=2.0,
        add_drain_holes=True,
        drain_hole_radius_mm=2.0,
        drain_hole_count=2,
    )
    assert hollowed is not None
    assert len(hollowed.faces) > len(cube_mesh.faces)
    assert vol_saved is not None
    assert vol_saved > 0.0


def test_arrange_models_on_bed():
    items = [
        {"model_id": "m1", "filename": "part1.stl", "dimensions": [40.0, 40.0, 20.0]},
        {"model_id": "m2", "filename": "part2.stl", "dimensions": [50.0, 30.0, 15.0]},
        {"model_id": "m3", "filename": "part3.stl", "dimensions": [25.0, 25.0, 25.0]},
    ]
    placements, all_fit = mesh_service.arrange_models_on_bed(
        models_data=items,
        bed_width_mm=220.0,
        bed_depth_mm=220.0,
        spacing_mm=5.0,
        bed_margin_mm=10.0,
    )
    assert all_fit is True
    assert len(placements) == 3
    for p in placements:
        assert "position_mm" in p
        assert len(p["position_mm"]) == 3
        # Check Z is 0.0
        assert p["position_mm"][2] == 0.0


def test_export_project_3mf(cube_mesh, tmp_path):
    import zipfile
    target_3mf = tmp_path / "test_bundle.3mf"
    models_data = [
        {
            "model_id": "cube1",
            "filename": "cube1.stl",
            "mesh": cube_mesh,
            "position_mm": [-25.0, 0.0, 0.0],
            "rotation_deg": [0.0, 0.0, 0.0],
            "scale_factors": [1.0, 1.0, 1.0],
        },
        {
            "model_id": "cube2",
            "filename": "cube2.stl",
            "mesh": cube_mesh,
            "position_mm": [25.0, 0.0, 0.0],
            "rotation_deg": [0.0, 45.0, 0.0],
            "scale_factors": [1.5, 1.5, 1.5],
        },
    ]

    out_file = mesh_service.export_project_3mf(
        models_data=models_data,
        destination=target_3mf,
        project_name="Test Project",
        printer_model="Bambu Lab X1-Carbon",
        filament_name="Bambu PLA Basic",
    )

    assert out_file.exists()
    assert out_file.stat().st_size > 0

    with zipfile.ZipFile(out_file, "r") as zf:
        file_list = zf.namelist()
        assert "[Content_Types].xml" in file_list
        assert "_rels/.rels" in file_list
        assert "3D/3dmodel.model" in file_list
        assert "Metadata/project_info.json" in file_list

        model_xml = zf.read("3D/3dmodel.model").decode("utf-8")
        assert 'name="cube1.stl"' in model_xml
        assert 'name="cube2.stl"' in model_xml
        assert '<item objectid="1"' in model_xml
        assert '<item objectid="2"' in model_xml


@pytest.mark.asyncio
async def test_full_cad_operations_api(cube_stl_bytes):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create project
        resp = await client.post(
            "/api/v1/projects",
            json={"name": "CAD Suite Project", "project_type": "Mechanical Part"},
        )
        assert resp.status_code == 201
        proj = resp.json()
        proj_id = proj["id"]

        # 2. Import model
        files = {"file": ("cube.stl", cube_stl_bytes, "model/stl")}
        resp = await client.post(f"/api/v1/projects/{proj_id}/models/import", files=files)
        assert resp.status_code == 201
        model = resp.json()
        model_id = model["id"]

        # 3. Duplicate model
        resp = await client.post(f"/api/v1/projects/{proj_id}/models/{model_id}/duplicate")
        assert resp.status_code == 201
        dup_model = resp.json()
        assert dup_model["id"] != model_id
        assert "_copy" in dup_model["filename"]

        # 4. Auto-arrange models on bed
        resp = await client.post(f"/api/v1/projects/{proj_id}/arrange", json={"spacing_mm": 5.0})
        assert resp.status_code == 200
        arrange_res = resp.json()
        assert arrange_res["models_arranged"] == 2
        assert arrange_res["all_fit"] is True

        # 5. Hollow model
        resp = await client.post(
            f"/api/v1/projects/{proj_id}/models/{model_id}/hollow",
            json={"wall_thickness_mm": 2.0, "add_drain_holes": True},
        )
        assert resp.status_code == 200
        hollow_res = resp.json()
        assert hollow_res["wall_thickness_mm"] == 2.0

        # 6. Planar Slice model
        resp = await client.post(
            f"/api/v1/projects/{proj_id}/models/{model_id}/slice",
            json={"plane_normal": [0.0, 0.0, 1.0], "cap_faces": True, "create_pegs": True},
        )
        assert resp.status_code == 200
        slice_res = resp.json()
        assert "top_model" in slice_res
        assert "bottom_model" in slice_res

        # 7. 3MF Project Container Export
        resp = await client.post(
            f"/api/v1/projects/{proj_id}/export_3mf",
            json={"filament_preset": "Bambu PLA Basic"},
        )
        assert resp.status_code == 200
        export_3mf_res = resp.json()
        assert export_3mf_res["filename"].endswith(".3mf")
        assert export_3mf_res["models_exported"] >= 1
        assert "download_url" in export_3mf_res

        # 8. Delete duplicated model
        resp = await client.delete(f"/api/v1/projects/{proj_id}/models/{dup_model['id']}")
        assert resp.status_code == 200
        assert resp.json()["model_id"] == dup_model["id"]

