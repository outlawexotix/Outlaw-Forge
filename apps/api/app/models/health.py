from typing import Literal
from pydantic import BaseModel, Field


class ServicesHealth(BaseModel):
    database: Literal["connected", "disconnected"] = Field(
        ..., description="Database connection status"
    )
    mesh_engine: Literal["ready", "unavailable"] = Field(
        ..., description="Mesh processing engine status"
    )


class SystemInfo(BaseModel):
    platform: str = Field(..., description="Operating system platform details")
    python_version: str = Field(..., description="Python runtime version")


class HealthStatusResponse(BaseModel):
    status: Literal["healthy", "degraded", "unhealthy"] = Field(
        ..., description="Overall backend health status"
    )
    version: str = Field(..., description="Backend application version")
    app_name: str = Field(..., description="Application name")
    environment: str = Field(..., description="Current running environment")
    services: ServicesHealth = Field(..., description="Status of backend services")
    system: SystemInfo = Field(..., description="Host system and runtime information")
    timestamp: str = Field(..., description="ISO 8601 UTC timestamp")
