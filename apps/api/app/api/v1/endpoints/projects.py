from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
import aiosqlite

from app.db.database import get_db
from app.models.project import (
    Project,
    ProjectCreatePayload,
    ProjectDeleteResponse,
    ProjectUpdatePayload,
)
from app.repositories.project_repo import ProjectRepository

router = APIRouter()


def get_repo(conn: aiosqlite.Connection = Depends(get_db)) -> ProjectRepository:
    return ProjectRepository(conn)


@router.get("", response_model=List[Project], summary="List all projects")
async def list_projects(repo: ProjectRepository = Depends(get_repo)) -> List[Project]:
    """Retrieve all projects ordered by last update time."""
    return await repo.list_all()


@router.post("", response_model=Project, status_code=status.HTTP_201_CREATED, summary="Create a new project")
async def create_project(
    payload: ProjectCreatePayload,
    repo: ProjectRepository = Depends(get_repo),
) -> Project:
    """Create a new 3D model project."""
    return await repo.create(payload)


@router.get("/{project_id}", response_model=Project, summary="Get project by ID")
async def get_project(
    project_id: str,
    repo: ProjectRepository = Depends(get_repo),
) -> Project:
    """Retrieve a specific project and all its associated models and operations."""
    project = await repo.get_by_id(project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID '{project_id}' not found",
        )
    return project


@router.patch("/{project_id}", response_model=Project, summary="Update project metadata")
async def update_project(
    project_id: str,
    payload: ProjectUpdatePayload,
    repo: ProjectRepository = Depends(get_repo),
) -> Project:
    """Update fields on an existing project."""
    updated = await repo.update(project_id, payload)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID '{project_id}' not found",
        )
    return updated


@router.delete("/{project_id}", response_model=ProjectDeleteResponse, summary="Delete a project")
async def delete_project(
    project_id: str,
    repo: ProjectRepository = Depends(get_repo),
) -> ProjectDeleteResponse:
    """Delete a project and cascade remove associated models/operations."""
    deleted = await repo.delete(project_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID '{project_id}' not found",
        )
    return ProjectDeleteResponse(success=True, id=project_id)
