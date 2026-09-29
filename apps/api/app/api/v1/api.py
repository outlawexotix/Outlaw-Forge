from fastapi import APIRouter

from app.api.v1.endpoints import health, models, printers, projects

api_router = APIRouter()
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
api_router.include_router(printers.router, prefix="/printers", tags=["printers"])
api_router.include_router(models.router, tags=["models"])

