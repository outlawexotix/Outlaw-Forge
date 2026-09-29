import json
import pytest
from fastapi.testclient import TestClient
import aiosqlite

from app.models.project import Project


class TestProjectEndpoints:
    """Comprehensive test suite for project CRUD operations."""

    def test_list_projects_initially_empty(self, client: TestClient):
        """Test GET /projects on fresh database returns empty list."""
        response = client.get("/projects")
        assert response.status_code == 200
        assert response.json() == []

    def test_create_project_minimal(self, client: TestClient):
        """Test POST /projects with minimal required fields."""
        payload = {
            "name": "Spartan Helmet",
            "project_type": "Prop",
        }
        response = client.post("/projects", json=payload)
        assert response.status_code == 201
        data = response.json()

        assert data["id"].startswith("proj_")
        assert data["name"] == "Spartan Helmet"
        assert data["project_type"] == "Prop"
        assert data["description"] == ""
        assert data["notes"] == ""
        assert data["selected_printer_id"] is None
        assert data["units"] == "mm"
        assert data["source_files"] == []
        assert data["working_models"] == []
        assert data["operations"] == []
        assert data["created_at"] is not None
        assert data["updated_at"] is not None

        # Verify validation
        Project.model_validate(data)

    def test_create_project_full(self, client: TestClient):
        """Test POST /projects with all fields populated."""
        payload = {
            "name": "Gothic Gargoyle Statue",
            "description": "High detail cathedral gargoyle with open wings",
            "project_type": "Statue",
            "selected_printer_id": "printer_ender_3_s1",
            "notes": "Scale to 180mm height before slicing",
        }
        response = client.post("/projects", json=payload)
        assert response.status_code == 201
        data = response.json()

        assert data["name"] == payload["name"]
        assert data["description"] == payload["description"]
        assert data["project_type"] == "Statue"
        assert data["selected_printer_id"] == "printer_ender_3_s1"
        assert data["notes"] == payload["notes"]

    def test_create_project_invalid_type(self, client: TestClient):
        """Test POST /projects with unsupported project_type returns 422."""
        payload = {
            "name": "Invalid Project",
            "project_type": "InvalidCategoryType",
        }
        response = client.post("/projects", json=payload)
        assert response.status_code == 422

    def test_get_project_by_id(self, client: TestClient):
        """Test GET /projects/{id} retrieves existing project."""
        create_res = client.post(
            "/projects",
            json={"name": "Cyberpunk Visor", "project_type": "Mask", "description": "Cosplay prop"},
        )
        assert create_res.status_code == 201
        proj_id = create_res.json()["id"]

        get_res = client.get(f"/projects/{proj_id}")
        assert get_res.status_code == 200
        data = get_res.json()
        assert data["id"] == proj_id
        assert data["name"] == "Cyberpunk Visor"
        assert data["project_type"] == "Mask"

    def test_get_project_not_found(self, client: TestClient):
        """Test GET /projects/{id} with unknown ID returns 404."""
        response = client.get("/projects/non_existent_project_id")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_patch_project_metadata(self, client: TestClient):
        """Test PATCH /projects/{id} updates partial metadata and updated_at timestamp."""
        create_res = client.post(
            "/projects",
            json={"name": "Original Name", "project_type": "Prop"},
        )
        proj_id = create_res.json()["id"]
        original_updated_at = create_res.json()["updated_at"]

        patch_payload = {
            "name": "Updated Helmet Name",
            "description": "Added detailed description",
            "project_type": "Collectible Figure",
            "selected_printer_id": "printer_ender_3",
            "notes": "Updated slicing notes",
        }
        patch_res = client.patch(f"/projects/{proj_id}", json=patch_payload)
        assert patch_res.status_code == 200
        updated_data = patch_res.json()

        assert updated_data["name"] == "Updated Helmet Name"
        assert updated_data["description"] == "Added detailed description"
        assert updated_data["project_type"] == "Collectible Figure"
        assert updated_data["selected_printer_id"] == "printer_ender_3"
        assert updated_data["notes"] == "Updated slicing notes"
        assert updated_data["updated_at"] >= original_updated_at

    def test_patch_project_not_found(self, client: TestClient):
        """Test PATCH /projects/{id} with unknown ID returns 404."""
        response = client.patch(
            "/projects/non_existent_project_id",
            json={"name": "New Name"},
        )
        assert response.status_code == 404

    def test_delete_project_success(self, client: TestClient):
        """Test DELETE /projects/{id} removes the project."""
        create_res = client.post(
            "/projects",
            json={"name": "Temporary Test Project", "project_type": "Other"},
        )
        proj_id = create_res.json()["id"]

        del_res = client.delete(f"/projects/{proj_id}")
        assert del_res.status_code == 200
        del_data = del_res.json()
        assert del_data["success"] is True
        assert del_data["id"] == proj_id

        # Verify subsequent GET returns 404
        get_res = client.get(f"/projects/{proj_id}")
        assert get_res.status_code == 404

    def test_delete_project_not_found(self, client: TestClient):
        """Test DELETE /projects/{id} with unknown ID returns 404."""
        response = client.delete("/projects/non_existent_project_id")
        assert response.status_code == 404

    def test_api_v1_projects_parity(self, client: TestClient):
        """Test GET and POST on /api/v1/projects."""
        create_res = client.post(
            "/api/v1/projects",
            json={"name": "V1 Parity Check", "project_type": "Character"},
        )
        assert create_res.status_code == 201
        proj_id = create_res.json()["id"]

        list_res = client.get("/api/v1/projects")
        assert list_res.status_code == 200
        ids = [p["id"] for p in list_res.json()]
        assert proj_id in ids

    @pytest.mark.asyncio
    async def test_project_with_nested_entities(self, temp_db_path, client: TestClient):
        """Test project repository parsing with populated source files, models, and operations."""
        # Create a project first
        create_res = client.post(
            "/projects",
            json={"name": "Project With Models", "project_type": "Statue"},
        )
        proj_id = create_res.json()["id"]

        # Insert nested source_files, working_models, and operations directly via SQLite
        bounds_json = json.dumps({
            "min": [-50.0, -50.0, 0.0],
            "max": [50.0, 50.0, 150.0],
            "dimensions_mm": [100.0, 100.0, 150.0],
        })
        transform_json = json.dumps({
            "position_mm": [0.0, 0.0, 0.0],
            "rotation_deg": [0.0, 0.0, 0.0],
            "scale_factors": [1.0, 1.0, 1.0],
            "uniform_scale_percent": 100.0,
        })
        params_json = json.dumps({"scale": 1.5, "axis": "uniform"})

        async with aiosqlite.connect(temp_db_path) as conn:
            await conn.execute("PRAGMA foreign_keys = ON;")
            await conn.execute(
                """
                INSERT INTO source_files (
                    id, project_id, filename, file_format, file_size_bytes, storage_path, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                ("src_001", proj_id, "statue.stl", "stl", 1048576, "/storage/statue.stl", "2026-09-28T18:00:00Z"),
            )
            await conn.execute(
                """
                INSERT INTO working_models (
                    id, project_id, source_file_id, filename, file_format, storage_path,
                    units, bounds_json, triangle_count, vertex_count, surface_area_cm2,
                    volume_cm3, is_watertight, transform_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "wm_001",
                    proj_id,
                    "src_001",
                    "statue_working.stl",
                    "stl",
                    "/storage/statue_working.stl",
                    "mm",
                    bounds_json,
                    50000,
                    25002,
                    320.5,
                    450.2,
                    1,
                    transform_json,
                    "2026-09-28T18:05:00Z",
                    "2026-09-28T18:05:00Z",
                ),
            )
            await conn.execute(
                """
                INSERT INTO operations (
                    id, project_id, model_id, operation_type, timestamp,
                    parameters_json, resulting_state_ref, user_summary, success
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "op_001",
                    proj_id,
                    "wm_001",
                    "SCALE",
                    "2026-09-28T18:10:00Z",
                    params_json,
                    "wm_001",
                    "Scaled model uniformly to 150%",
                    1,
                ),
            )
            await conn.commit()

        # Fetch through API
        response = client.get(f"/projects/{proj_id}")
        assert response.status_code == 200
        data = response.json()

        assert len(data["source_files"]) == 1
        assert data["source_files"][0]["id"] == "src_001"
        assert data["source_files"][0]["filename"] == "statue.stl"

        assert len(data["working_models"]) == 1
        wm = data["working_models"][0]
        assert wm["id"] == "wm_001"
        assert wm["triangle_count"] == 50000
        assert wm["is_watertight"] is True
        assert wm["bounds"]["dimensions_mm"] == [100.0, 100.0, 150.0]
        assert wm["transform"]["uniform_scale_percent"] == 100.0

        assert len(data["operations"]) == 1
        op = data["operations"][0]
        assert op["id"] == "op_001"
        assert op["operation_type"] == "SCALE"
        assert op["parameters"] == {"scale": 1.5, "axis": "uniform"}
        assert op["success"] is True
