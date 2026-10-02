from fastapi import APIRouter

from app.api.v1.endpoints import calibration, health, models, printers, projects, studios

api_router = APIRouter()
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
api_router.include_router(printers.router, prefix="/printers", tags=["printers"])
api_router.include_router(models.router, tags=["models"])
api_router.include_router(calibration.router, tags=["calibration", "advanced_cad"])
api_router.include_router(studios.router, tags=["studios", "masksmith", "figureforge"])



