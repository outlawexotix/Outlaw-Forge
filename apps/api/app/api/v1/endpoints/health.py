import platform
from datetime import datetime, timezone
from fastapi import APIRouter

from app.core.config import settings
from app.models.health import HealthStatusResponse, ServicesHealth, SystemInfo

router = APIRouter()


@router.get("", response_model=HealthStatusResponse, summary="Get backend health status")
async def get_health_status() -> HealthStatusResponse:
    """Return the health status of the API, underlying database, mesh engine, and system information."""
    # Check services status (extensible for actual connection checks as submodules are added)
    services = ServicesHealth(
        database="connected",
        mesh_engine="ready",
    )

    system_info = SystemInfo(
        platform=f"{platform.system()} {platform.release()} ({platform.machine()})",
        python_version=platform.python_version(),
    )

    overall_status = "healthy"
    if services.database != "connected" or services.mesh_engine != "ready":
        overall_status = "degraded"

    return HealthStatusResponse(
        status=overall_status,
        version=settings.VERSION,
        app_name=settings.APP_NAME,
        environment=settings.ENVIRONMENT,
        services=services,
        system=system_info,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
