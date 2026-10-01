from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.api import api_router
from app.api.v1.endpoints import calibration, health, models, printers, projects
from app.core.config import settings
from app.db.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize SQLite database schema and seed data
    await init_db()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
    lifespan=lifespan,
)

# Set all CORS enabled origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=[str(origin).rstrip("/") for origin in settings.BACKEND_CORS_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Root-level endpoints for direct frontend/probe accessibility
app.include_router(health.router, prefix="/health", tags=["health"])
app.include_router(projects.router, prefix="/projects", tags=["projects"])
app.include_router(printers.router, prefix="/printers", tags=["printers"])
app.include_router(models.router, tags=["models"])
app.include_router(calibration.router, tags=["calibration", "advanced_cad"])

# Versioned API routes (/api/v1)
app.include_router(api_router, prefix=settings.API_V1_STR)



@app.get("/", tags=["root"])
async def root():
    return {
        "message": f"Welcome to {settings.APP_NAME} API",
        "version": settings.VERSION,
        "docs_url": f"{settings.API_V1_STR}/docs",
        "health_url": "/health",
        "projects_url": "/projects",
        "printers_url": "/printers",
    }
