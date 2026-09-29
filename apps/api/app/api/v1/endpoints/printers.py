from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
import aiosqlite

from app.db.database import get_db
from app.models.printer import (
    PrinterProfile,
    PrinterProfileCreatePayload,
)
from app.repositories.printer_repo import PrinterRepository

router = APIRouter()


def get_repo(conn: aiosqlite.Connection = Depends(get_db)) -> PrinterRepository:
    return PrinterRepository(conn)


@router.get("", response_model=List[PrinterProfile], summary="List all printer profiles")
async def list_printers(repo: PrinterRepository = Depends(get_repo)) -> List[PrinterProfile]:
    """Retrieve all available 3D printer profiles."""
    return await repo.list_all()


@router.post("", response_model=PrinterProfile, status_code=status.HTTP_201_CREATED, summary="Create a printer profile")
async def create_printer(
    payload: PrinterProfileCreatePayload,
    repo: PrinterRepository = Depends(get_repo),
) -> PrinterProfile:
    """Create a new 3D printer profile."""
    return await repo.create(payload)


@router.get("/{printer_id}", response_model=PrinterProfile, summary="Get printer profile by ID")
async def get_printer(
    printer_id: str,
    repo: PrinterRepository = Depends(get_repo),
) -> PrinterProfile:
    """Retrieve a specific printer profile by ID."""
    printer = await repo.get_by_id(printer_id)
    if not printer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Printer profile with ID '{printer_id}' not found",
        )
    return printer
