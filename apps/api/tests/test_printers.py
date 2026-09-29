import pytest
from fastapi.testclient import TestClient
from app.models.printer import PrinterProfile


class TestPrinterEndpoints:
    """Comprehensive test suite for printer profiles API."""

    SEEDED_PRINTER_PROFILES = [
        {
            "id": "printer_ender_3",
            "manufacturer": "Creality",
            "model": "Ender-3",
            "build_width_mm": 220.0,
            "build_depth_mm": 220.0,
            "build_height_mm": 250.0,
            "nozzle_diameter_mm": 0.4,
        },
        {
            "id": "printer_ender_3_s1",
            "manufacturer": "Creality",
            "model": "Ender-3 S1",
            "build_width_mm": 220.0,
            "build_depth_mm": 220.0,
            "build_height_mm": 270.0,
            "nozzle_diameter_mm": 0.4,
        },
        {
            "id": "printer_bambu_x1c",
            "manufacturer": "Bambu Lab",
            "model": "X1-Carbon",
            "build_width_mm": 256.0,
            "build_depth_mm": 256.0,
            "build_height_mm": 256.0,
            "nozzle_diameter_mm": 0.4,
        },
        {
            "id": "printer_prusa_mk4",
            "manufacturer": "Prusa",
            "model": "Original Prusa MK4",
            "build_width_mm": 250.0,
            "build_depth_mm": 210.0,
            "build_height_mm": 220.0,
            "nozzle_diameter_mm": 0.4,
        },
        {
            "id": "printer_voron_2_4_350",
            "manufacturer": "Voron",
            "model": "Voron 2.4 350",
            "build_width_mm": 350.0,
            "build_depth_mm": 350.0,
            "build_height_mm": 350.0,
            "nozzle_diameter_mm": 0.4,
        },
        {
            "id": "printer_elegoo_neptune_4_pro",
            "manufacturer": "Elegoo",
            "model": "Neptune 4 Pro",
            "build_width_mm": 225.0,
            "build_depth_mm": 225.0,
            "build_height_mm": 265.0,
            "nozzle_diameter_mm": 0.4,
        },
    ]

    def test_list_printers_all_6_seeded_profiles(self, client: TestClient):
        """Test GET /printers returns all 6 default seeded printer profiles with valid schemas."""
        response = client.get("/printers")
        assert response.status_code == 200
        printers = response.json()
        assert len(printers) >= 6

        printer_map = {p["id"]: p for p in printers}
        for expected in self.SEEDED_PRINTER_PROFILES:
            pid = expected["id"]
            assert pid in printer_map, f"Seeded profile '{pid}' not found in /printers output"
            actual = printer_map[pid]
            assert actual["manufacturer"] == expected["manufacturer"]
            assert actual["model"] == expected["model"]
            assert pytest.approx(actual["build_width_mm"], rel=1e-3) == expected["build_width_mm"]
            assert pytest.approx(actual["build_depth_mm"], rel=1e-3) == expected["build_depth_mm"]
            assert pytest.approx(actual["build_height_mm"], rel=1e-3) == expected["build_height_mm"]
            assert pytest.approx(actual["nozzle_diameter_mm"], rel=1e-3) == expected["nozzle_diameter_mm"]

        # Validate each printer matches Pydantic schema
        for p in printers:
            validated = PrinterProfile.model_validate(p)
            assert validated.build_width_mm > 0
            assert validated.build_depth_mm > 0
            assert validated.build_height_mm > 0
            assert validated.nozzle_diameter_mm > 0

    def test_api_v1_list_printers_parity(self, client: TestClient):
        """Test GET /api/v1/printers endpoint parity with /printers."""
        res_root = client.get("/printers")
        res_v1 = client.get("/api/v1/printers")
        assert res_root.status_code == 200
        assert res_v1.status_code == 200
        assert res_root.json() == res_v1.json()

    @pytest.mark.parametrize(
        "expected",
        SEEDED_PRINTER_PROFILES,
        ids=[p["id"] for p in SEEDED_PRINTER_PROFILES],
    )
    def test_get_each_seeded_printer_by_id(self, client: TestClient, expected: dict):
        """Test GET /printers/{id} for each of the 6 seeded profiles."""
        response = client.get(f"/printers/{expected['id']}")
        assert response.status_code == 200
        data = response.json()

        assert data["id"] == expected["id"]
        assert data["manufacturer"] == expected["manufacturer"]
        assert data["model"] == expected["model"]
        assert pytest.approx(data["build_width_mm"], rel=1e-3) == expected["build_width_mm"]
        assert pytest.approx(data["build_depth_mm"], rel=1e-3) == expected["build_depth_mm"]
        assert pytest.approx(data["build_height_mm"], rel=1e-3) == expected["build_height_mm"]
        assert pytest.approx(data["nozzle_diameter_mm"], rel=1e-3) == expected["nozzle_diameter_mm"]

    def test_get_printer_not_found(self, client: TestClient):
        """Test GET /printers/{id} with non-existent ID returns 404."""
        response = client.get("/printers/non_existent_printer_id")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_create_custom_printer_with_custom_envelope(self, client: TestClient):
        """Test POST /printers creates a new custom profile with custom build envelope."""
        payload = {
            "manufacturer": "RatRig",
            "model": "V-Core 3.1 500",
            "build_width_mm": 500.0,
            "build_depth_mm": 500.0,
            "build_height_mm": 500.0,
            "nozzle_diameter_mm": 0.8,
            "notes": "Custom large-format CoreXY machine with triple lead screw auto-bed leveling",
        }
        response = client.post("/printers", json=payload)
        assert response.status_code == 201
        data = response.json()

        assert data["id"].startswith("printer_")
        assert data["manufacturer"] == "RatRig"
        assert data["model"] == "V-Core 3.1 500"
        assert data["build_width_mm"] == 500.0
        assert data["build_depth_mm"] == 500.0
        assert data["build_height_mm"] == 500.0
        assert data["nozzle_diameter_mm"] == 0.8
        assert data["notes"] == payload["notes"]
        assert data["created_at"] is not None

        # Verify profile is retrievable via GET /printers/{id}
        get_res = client.get(f"/printers/{data['id']}")
        assert get_res.status_code == 200
        reloaded = get_res.json()
        assert reloaded["id"] == data["id"]
        assert reloaded["model"] == "V-Core 3.1 500"
        assert reloaded["build_width_mm"] == 500.0

    @pytest.mark.parametrize(
        "invalid_payload",
        [
            {
                "manufacturer": "Custom Brand",
                "model": "Negative Width",
                "build_width_mm": -10.0,
                "build_depth_mm": 200.0,
                "build_height_mm": 200.0,
                "nozzle_diameter_mm": 0.4,
            },
            {
                "manufacturer": "Custom Brand",
                "model": "Zero Depth",
                "build_width_mm": 200.0,
                "build_depth_mm": 0.0,
                "build_height_mm": 200.0,
                "nozzle_diameter_mm": 0.4,
            },
            {
                "manufacturer": "Custom Brand",
                "model": "Negative Height",
                "build_width_mm": 200.0,
                "build_depth_mm": 200.0,
                "build_height_mm": -50.0,
                "nozzle_diameter_mm": 0.4,
            },
            {
                "manufacturer": "Custom Brand",
                "model": "Negative Nozzle",
                "build_width_mm": 200.0,
                "build_depth_mm": 200.0,
                "build_height_mm": 200.0,
                "nozzle_diameter_mm": -0.4,
            },
        ],
    )
    def test_create_printer_validation_failure(self, client: TestClient, invalid_payload: dict):
        """Test POST /printers with invalid or non-positive dimensions returns 422."""
        response = client.post("/printers", json=invalid_payload)
        assert response.status_code == 422
