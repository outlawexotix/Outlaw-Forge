import datetime
import pytest
from httpx import ASGITransport, AsyncClient
from fastapi.testclient import TestClient

from app.main import app
from app.models.health import HealthStatusResponse


@pytest.fixture
def client():
    """Synchronous test client fixture for standard HTTP verification."""
    return TestClient(app)


class TestHealthEndpoints:
    """Comprehensive test suite for Outlaw Forge health and diagnostics endpoints."""

    def test_root_endpoint_status_and_schema(self, client: TestClient):
        """Test GET / returns 200 OK and expected API discovery metadata."""
        response = client.get("/")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/json")
        data = response.json()
        assert "message" in data
        assert "Outlaw Forge" in data["message"]
        assert "version" in data
        assert "docs_url" in data
        assert "health_url" in data
        assert data["health_url"] == "/health"

    def test_health_endpoint(self, client: TestClient):
        """Test GET /health returns 200 and passes complete schema validation."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/json")

        payload = response.json()
        # Validate through Pydantic model
        health_model = HealthStatusResponse.model_validate(payload)
        assert health_model.status in ["healthy", "degraded", "unhealthy"]
        assert health_model.app_name == "Outlaw Forge"
        assert health_model.version == "0.1.0"
        assert health_model.environment in ["development", "staging", "production", "test"]
        assert health_model.services.database in ["connected", "disconnected"]
        assert health_model.services.mesh_engine in ["ready", "unavailable"]
        assert len(health_model.system.platform) > 0
        assert len(health_model.system.python_version) > 0

        # Validate timestamp format (ISO 8601 UTC)
        parsed_time = datetime.datetime.fromisoformat(health_model.timestamp)
        assert parsed_time is not None

    def test_api_v1_health_endpoint(self, client: TestClient):
        """Test GET /api/v1/health returns 200 and identical contract parity."""
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/json")

        payload = response.json()
        health_model = HealthStatusResponse.model_validate(payload)
        assert health_model.status == "healthy"
        assert health_model.app_name == "Outlaw Forge"
        assert health_model.services.database == "connected"
        assert health_model.services.mesh_engine == "ready"

    def test_cors_headers_on_health(self, client: TestClient):
        """Verify CORS headers for authorized origins on health check."""
        origin = "http://localhost:3000"
        headers = {
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
        }
        # Preflight OPTIONS request
        options_response = client.options("/health", headers=headers)
        assert options_response.status_code == 200
        assert options_response.headers.get("access-control-allow-origin") == origin

        # Simple GET request with Origin
        get_response = client.get("/health", headers={"Origin": origin})
        assert get_response.status_code == 200
        assert get_response.headers.get("access-control-allow-origin") == origin

    def test_health_method_not_allowed(self, client: TestClient):
        """Verify unsupported HTTP methods return 405 Method Not Allowed."""
        post_res = client.post("/health", json={"dummy": "data"})
        assert post_res.status_code == 405

        put_res = client.put("/health", json={"dummy": "data"})
        assert put_res.status_code == 405

        delete_res = client.delete("/health")
        assert delete_res.status_code == 405

    def test_v1_health_method_not_allowed(self, client: TestClient):
        """Verify unsupported HTTP methods on /api/v1/health return 405."""
        post_res = client.post("/api/v1/health", json={})
        assert post_res.status_code == 405

        delete_res = client.delete("/api/v1/health")
        assert delete_res.status_code == 405
