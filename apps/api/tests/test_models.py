import io
import pytest
import trimesh
from fastapi.testclient import TestClient

from app.models.project import WorkingModel


def create_sample_stl_bytes(w=20.0, d=30.0, h=40.0) -> bytes:
    mesh = trimesh.creation.box(extents=[w, d, h])
    out = io.BytesIO()
    mesh.export(out, file_type="stl")
    return out.getvalue()


class TestModelEndpoints:
    def test_import_model_success(self, client: TestClient):
        # 1. Create a project
        proj_res = client.post("/projects", json={"name": "Test Statue Project", "project_type": "Statue"})
        assert proj_res.status_code == 201
        project_id = proj_res.json()["id"]

        # 2. Upload model
        stl_data = create_sample_stl_bytes(20.0, 30.0, 40.0)
        files = {"file": ("test_statue.stl", stl_data, "application/octet-stream")}
        import_res = client.post(f"/projects/{project_id}/models/import", files=files)
        assert import_res.status_code == 201
        data = import_res.json()

        assert data["id"].startswith("wm_")
        assert data["project_id"] == project_id
        assert data["filename"] == "test_statue.stl"
        assert data["file_format"] == "stl"
        assert data["triangle_count"] == 12
        assert data["vertex_count"] == 8
        assert data["is_watertight"] is True
        assert data["bounds"]["dimensions_mm"] == [20.0, 30.0, 40.0]

        # Validate schema
        WorkingModel.model_validate(data)

        # 3. Check project state includes source files, working models, and operations
        get_proj = client.get(f"/projects/{project_id}")
        assert get_proj.status_code == 200
        proj_data = get_proj.json()
        assert len(proj_data["source_files"]) == 1
        assert len(proj_data["working_models"]) == 1
        assert len(proj_data["operations"]) == 1
        assert proj_data["operations"][0]["operation_type"] == "IMPORT"

    def test_import_model_invalid_project(self, client: TestClient):
        stl_data = create_sample_stl_bytes()
        files = {"file": ("model.stl", stl_data, "application/octet-stream")}
        res = client.post("/projects/non_existent_project/models/import", files=files)
        assert res.status_code == 404

    def test_import_model_invalid_extension(self, client: TestClient):
        proj_res = client.post("/projects", json={"name": "Bad Ext Project", "project_type": "Other"})
        project_id = proj_res.json()["id"]

        files = {"file": ("model.exe", b"malicious executable payload", "application/octet-stream")}
        res = client.post(f"/projects/{project_id}/models/import", files=files)
        assert res.status_code == 400

    def test_get_model_metadata(self, client: TestClient):
        proj_res = client.post("/projects", json={"name": "Get Model Proj", "project_type": "Prop"})
        project_id = proj_res.json()["id"]

        stl_data = create_sample_stl_bytes()
        files = {"file": ("shield.stl", stl_data, "application/octet-stream")}
        import_res = client.post(f"/projects/{project_id}/models/import", files=files)
        model_id = import_res.json()["id"]

        # Test project-scoped GET
        get_res = client.get(f"/projects/{project_id}/models/{model_id}")
        assert get_res.status_code == 200
        assert get_res.json()["id"] == model_id

        # Test direct GET
        direct_res = client.get(f"/models/{model_id}")
        assert direct_res.status_code == 200
        assert direct_res.json()["id"] == model_id

    def test_analyze_model_endpoint(self, client: TestClient):
        proj_res = client.post("/projects", json={"name": "Analyze Proj", "project_type": "Mask"})
        project_id = proj_res.json()["id"]

        stl_data = create_sample_stl_bytes()
        files = {"file": ("mask.stl", stl_data, "application/octet-stream")}
        import_res = client.post(f"/projects/{project_id}/models/import", files=files)
        model_id = import_res.json()["id"]

        analyze_res = client.post(f"/projects/{project_id}/models/{model_id}/analyze")
        assert analyze_res.status_code == 200
        data = analyze_res.json()
        assert data["id"] == model_id
        assert data["is_watertight"] is True

    def test_scale_model_percentage(self, client: TestClient):
        proj_res = client.post("/projects", json={"name": "Scale Proj", "project_type": "Statue"})
        project_id = proj_res.json()["id"]

        stl_data = create_sample_stl_bytes(10.0, 10.0, 10.0)
        files = {"file": ("cube.stl", stl_data, "application/octet-stream")}
        import_res = client.post(f"/projects/{project_id}/models/import", files=files)
        model_id = import_res.json()["id"]

        scale_payload = {
            "uniform_scale_percent": 150.0,
            "preserve_aspect_ratio": True,
        }
        scale_res = client.post(f"/projects/{project_id}/models/{model_id}/scale", json=scale_payload)
        assert scale_res.status_code == 200
        scaled_data = scale_res.json()

        dims = scaled_data["bounds"]["dimensions_mm"]
        assert pytest.approx(dims[0], rel=1e-2) == 15.0
        assert pytest.approx(dims[1], rel=1e-2) == 15.0
        assert pytest.approx(dims[2], rel=1e-2) == 15.0
        assert scaled_data["transform"]["uniform_scale_percent"] == 150.0

        # Check operation was logged
        proj_check = client.get(f"/projects/{project_id}").json()
        op_types = [op["operation_type"] for op in proj_check["operations"]]
        assert "SCALE" in op_types

    def test_export_model_endpoint(self, client: TestClient):
        proj_res = client.post("/projects", json={"name": "Export Proj", "project_type": "Mechanical Part"})
        project_id = proj_res.json()["id"]

        stl_data = create_sample_stl_bytes()
        files = {"file": ("gear.stl", stl_data, "application/octet-stream")}
        import_res = client.post(f"/projects/{project_id}/models/import", files=files)
        model_id = import_res.json()["id"]

        # Export as OBJ
        export_payload = {"format": "obj", "filename": "custom_gear.obj"}
        export_res = client.post(f"/projects/{project_id}/models/{model_id}/export", json=export_payload)
        assert export_res.status_code == 200
        data = export_res.json()
        assert data["filename"] == "custom_gear.obj"
        assert "/models/exports/" in data["download_url"]

        # Download exported file
        dl_res = client.get(data["download_url"])
        assert dl_res.status_code == 200
        assert dl_res.content.startswith(b"#") or b"v " in dl_res.content

    def test_serve_model_file(self, client: TestClient):
        proj_res = client.post("/projects", json={"name": "Serve File Proj", "project_type": "Prop"})
        project_id = proj_res.json()["id"]

        stl_data = create_sample_stl_bytes()
        files = {"file": ("shield_render.stl", stl_data, "application/octet-stream")}
        import_res = client.post(f"/projects/{project_id}/models/import", files=files)
        model_id = import_res.json()["id"]

        file_res = client.get(f"/models/{model_id}/file")
        assert file_res.status_code == 200
        assert len(file_res.content) == len(stl_data)

        # Route via project
        file_res_proj = client.get(f"/projects/{project_id}/models/{model_id}/file")
        assert file_res_proj.status_code == 200

    def test_printability_evaluation(self, client: TestClient):
        # 1. Create project with selected printer Ender-3 (220 x 220 x 250)
        proj_res = client.post(
            "/projects",
            json={
                "name": "Printability Proj",
                "project_type": "Statue",
                "selected_printer_id": "printer_ender_3",
            },
        )
        project_id = proj_res.json()["id"]

        # 2. Upload model fitting well (50 x 50 x 50)
        stl_data = create_sample_stl_bytes(50.0, 50.0, 50.0)
        files = {"file": ("test_print.stl", stl_data, "application/octet-stream")}
        client.post(f"/projects/{project_id}/models/import", files=files)

        # 3. Check printability
        eval_res = client.get(f"/projects/{project_id}/printability")
        assert eval_res.status_code == 200
        data = eval_res.json()
        assert data["fits_build_volume"] is True
        assert data["printer_id"] == "printer_ender_3"
        assert len(data["findings"]) > 0

    def test_api_v1_parity_models(self, client: TestClient):
        proj_res = client.post(
            "/api/v1/projects",
            json={"name": "V1 Parity Model Proj", "project_type": "Other"},
        )
        project_id = proj_res.json()["id"]

        stl_data = create_sample_stl_bytes()
        files = {"file": ("v1_model.stl", stl_data, "application/octet-stream")}
        import_res = client.post(f"/api/v1/projects/{project_id}/models/import", files=files)
        assert import_res.status_code == 201
        model_id = import_res.json()["id"]

        get_res = client.get(f"/api/v1/projects/{project_id}/models/{model_id}")
        assert get_res.status_code == 200
        assert get_res.json()["id"] == model_id

    def test_rotate_model_endpoint(self, client: TestClient):
        # 1. Create project & import 20 x 30 x 40 model
        proj_res = client.post("/projects", json={"name": "Rotate Proj", "project_type": "Statue"})
        project_id = proj_res.json()["id"]

        stl_data = create_sample_stl_bytes(20.0, 30.0, 40.0)
        files = {"file": ("box.stl", stl_data, "application/octet-stream")}
        import_res = client.post(f"/projects/{project_id}/models/import", files=files)
        model_id = import_res.json()["id"]

        # 2. Rotate 90 deg around Z
        rotate_payload = {"rx_deg": 0.0, "ry_deg": 0.0, "rz_deg": 90.0}
        rot_res = client.post(f"/projects/{project_id}/models/{model_id}/rotate", json=rotate_payload)
        assert rot_res.status_code == 200
        data = rot_res.json()

        dims = data["bounds"]["dimensions_mm"]
        assert pytest.approx(dims[0], rel=1e-2) == 30.0
        assert pytest.approx(dims[1], rel=1e-2) == 20.0
        assert pytest.approx(dims[2], rel=1e-2) == 40.0
        assert data["transform"]["rotation_deg"][2] == 90.0

        # Check operation was recorded
        proj_check = client.get(f"/projects/{project_id}").json()
        op_types = [op["operation_type"] for op in proj_check["operations"]]
        assert "ROTATE" in op_types
        rotate_op = next(op for op in proj_check["operations"] if op["operation_type"] == "ROTATE")
        assert rotate_op["parameters"]["rz_deg"] == 90.0

    def test_center_model_endpoint(self, client: TestClient):
        proj_res = client.post("/projects", json={"name": "Center Proj", "project_type": "Prop"})
        project_id = proj_res.json()["id"]

        stl_data = create_sample_stl_bytes(20.0, 20.0, 20.0)
        files = {"file": ("cube.stl", stl_data, "application/octet-stream")}
        import_res = client.post(f"/projects/{project_id}/models/import", files=files)
        model_id = import_res.json()["id"]

        # Call center endpoint
        center_res = client.post(f"/projects/{project_id}/models/{model_id}/center")
        assert center_res.status_code == 200
        data = center_res.json()

        bounds_min = data["bounds"]["min"]
        bounds_max = data["bounds"]["max"]
        # Min Z should be 0.0
        assert pytest.approx(bounds_min[2], abs=1e-2) == 0.0
        # X and Y centered around 0.0
        center_x = (bounds_min[0] + bounds_max[0]) / 2.0
        center_y = (bounds_min[1] + bounds_max[1]) / 2.0
        assert pytest.approx(center_x, abs=1e-2) == 0.0
        assert pytest.approx(center_y, abs=1e-2) == 0.0

        # Check operation was recorded
        proj_check = client.get(f"/projects/{project_id}").json()
        op_types = [op["operation_type"] for op in proj_check["operations"]]
        assert "CENTER" in op_types

    def test_lay_flat_model_endpoint(self, client: TestClient):
        proj_res = client.post("/projects", json={"name": "LayFlat Proj", "project_type": "Mechanical Part"})
        project_id = proj_res.json()["id"]

        # 10 x 20 x 30 box - largest face is 20 x 30
        stl_data = create_sample_stl_bytes(10.0, 20.0, 30.0)
        files = {"file": ("part.stl", stl_data, "application/octet-stream")}
        import_res = client.post(f"/projects/{project_id}/models/import", files=files)
        model_id = import_res.json()["id"]

        # Rotate it first so it is standing upright on smallest face
        client.post(f"/projects/{project_id}/models/{model_id}/rotate", json={"rx_deg": 90.0, "ry_deg": 0.0, "rz_deg": 0.0})

        # Lay flat
        flat_res = client.post(f"/projects/{project_id}/models/{model_id}/lay_flat")
        assert flat_res.status_code == 200
        data = flat_res.json()

        # Height should be 10.0 and min Z should be 0.0
        assert pytest.approx(data["bounds"]["min"][2], abs=1e-2) == 0.0
        assert pytest.approx(data["bounds"]["dimensions_mm"][2], abs=1e-2) == 10.0

        # Check operation was recorded
        proj_check = client.get(f"/projects/{project_id}").json()
        op_types = [op["operation_type"] for op in proj_check["operations"]]
        assert "LAY_FLAT" in op_types

    def test_get_overhangs_endpoint(self, client: TestClient):
        proj_res = client.post("/projects", json={"name": "Overhang Proj", "project_type": "Statue"})
        project_id = proj_res.json()["id"]

        stl_data = create_sample_stl_bytes(20.0, 30.0, 40.0)
        files = {"file": ("statue.stl", stl_data, "application/octet-stream")}
        import_res = client.post(f"/projects/{project_id}/models/import", files=files)
        model_id = import_res.json()["id"]

        # GET overhang diagnostics
        overhang_res = client.get(f"/projects/{project_id}/models/{model_id}/overhangs?critical_angle_deg=45.0")
        assert overhang_res.status_code == 200
        data = overhang_res.json()

        assert data["model_id"] == model_id
        assert data["critical_angle_deg"] == 45.0
        assert data["overhang_percentage"] > 0
        assert data["requires_support"] is True
        assert data["total_face_count"] == 12
        assert data["overhang_face_count"] == 2

    def test_slice_model_endpoint(self, client: TestClient):
        proj_res = client.post("/projects", json={"name": "Slice Proj", "project_type": "Statue"})
        project_id = proj_res.json()["id"]

        # 20x20x40 model
        stl_data = create_sample_stl_bytes(20.0, 20.0, 40.0)
        files = {"file": ("statue_tall.stl", stl_data, "application/octet-stream")}
        import_res = client.post(f"/projects/{project_id}/models/import", files=files)
        model_id = import_res.json()["id"]

        # Slice at Z=0 (mid-height of [-20, 20])
        payload = {
            "plane_origin": [0.0, 0.0, 0.0],
            "plane_normal": [0.0, 0.0, 1.0],
            "cap_faces": True,
            "create_pegs": False,
        }
        slice_res = client.post(f"/projects/{project_id}/models/{model_id}/slice", json=payload)
        assert slice_res.status_code == 200
        data = slice_res.json()

        assert "top_model" in data
        assert "bottom_model" in data
        assert data["top_model"]["is_watertight"] is True
        assert data["bottom_model"]["is_watertight"] is True
        assert data["cut_area_cm2"] > 0

        # Verify project has updated working models list and operation logged
        proj_check = client.get(f"/projects/{project_id}").json()
        assert len(proj_check["working_models"]) == 3  # original + top + bottom
        op_types = [op["operation_type"] for op in proj_check["operations"]]
        assert "SLICE" in op_types

    def test_repair_model_endpoint(self, client: TestClient):
        proj_res = client.post("/projects", json={"name": "Repair Proj", "project_type": "Prop"})
        project_id = proj_res.json()["id"]

        # Create an open non-watertight box (remove top 2 faces)
        box = trimesh.creation.box(extents=[20.0, 20.0, 20.0])
        top_face_mask = box.face_normals[:, 2] > 0.9
        non_top_faces = box.faces[~top_face_mask]
        open_box = trimesh.Trimesh(vertices=box.vertices, faces=non_top_faces, process=False)
        out = io.BytesIO()
        open_box.export(out, file_type="stl")
        stl_data = out.getvalue()

        files = {"file": ("open_box.stl", stl_data, "application/octet-stream")}
        import_res = client.post(f"/projects/{project_id}/models/import", files=files)
        model_id = import_res.json()["id"]
        assert import_res.json()["is_watertight"] is False

        # POST /projects/{id}/models/{id}/repair
        repair_payload = {
            "fill_holes": True,
            "fix_normals": True,
            "remove_degenerate_faces": True,
            "weld_vertices": True,
            "weld_threshold_mm": 0.001,
        }
        repair_res = client.post(f"/projects/{project_id}/models/{model_id}/repair", json=repair_payload)
        assert repair_res.status_code == 200
        data = repair_res.json()

        assert "repaired_model" in data
        assert "report" in data
        assert data["repaired_model"]["is_watertight"] is True
        assert data["report"]["is_watertight_before"] is False
        assert data["report"]["is_watertight_after"] is True
        assert data["report"]["holes_filled"] >= 1
        assert data["report"]["volume_restored_cm3"] is not None

        # Verify operation log
        proj_check = client.get(f"/projects/{project_id}").json()
        op_types = [op["operation_type"] for op in proj_check["operations"]]
        assert "REPAIR" in op_types
