import uuid
from datetime import datetime, timezone
from typing import List, Optional
import aiosqlite

from app.models.printer import PrinterProfile, PrinterProfileCreatePayload


class PrinterRepository:
    def __init__(self, conn: aiosqlite.Connection):
        self.conn = conn

    async def list_all(self) -> List[PrinterProfile]:
        """Fetch all printer profiles sorted by manufacturer and model."""
        cursor = await self.conn.execute(
            """
            SELECT id, manufacturer, model, build_width_mm, build_depth_mm,
                   build_height_mm, nozzle_diameter_mm, notes, created_at
            FROM printer_profiles
            ORDER BY manufacturer ASC, model ASC
            """
        )
        rows = await cursor.fetchall()
        return [
            PrinterProfile(
                id=row["id"],
                manufacturer=row["manufacturer"],
                model=row["model"],
                build_width_mm=float(row["build_width_mm"]),
                build_depth_mm=float(row["build_depth_mm"]),
                build_height_mm=float(row["build_height_mm"]),
                nozzle_diameter_mm=float(row["nozzle_diameter_mm"]),
                notes=row["notes"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

    async def get_by_id(self, printer_id: str) -> Optional[PrinterProfile]:
        """Fetch a specific printer profile by ID."""
        cursor = await self.conn.execute(
            """
            SELECT id, manufacturer, model, build_width_mm, build_depth_mm,
                   build_height_mm, nozzle_diameter_mm, notes, created_at
            FROM printer_profiles
            WHERE id = ?
            """,
            (printer_id,),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return PrinterProfile(
            id=row["id"],
            manufacturer=row["manufacturer"],
            model=row["model"],
            build_width_mm=float(row["build_width_mm"]),
            build_depth_mm=float(row["build_depth_mm"]),
            build_height_mm=float(row["build_height_mm"]),
            nozzle_diameter_mm=float(row["nozzle_diameter_mm"]),
            notes=row["notes"],
            created_at=row["created_at"],
        )

    async def create(self, payload: PrinterProfileCreatePayload) -> PrinterProfile:
        """Create and persist a new printer profile."""
        printer_id = f"printer_{uuid.uuid4().hex[:12]}"
        now_utc = datetime.now(timezone.utc).isoformat()

        await self.conn.execute(
            """
            INSERT INTO printer_profiles (
                id, manufacturer, model, build_width_mm, build_depth_mm,
                build_height_mm, nozzle_diameter_mm, notes, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                printer_id,
                payload.manufacturer,
                payload.model,
                payload.build_width_mm,
                payload.build_depth_mm,
                payload.build_height_mm,
                payload.nozzle_diameter_mm,
                payload.notes,
                now_utc,
            ),
        )
        await self.conn.commit()

        return PrinterProfile(
            id=printer_id,
            manufacturer=payload.manufacturer,
            model=payload.model,
            build_width_mm=payload.build_width_mm,
            build_depth_mm=payload.build_depth_mm,
            build_height_mm=payload.build_height_mm,
            nozzle_diameter_mm=payload.nozzle_diameter_mm,
            notes=payload.notes,
            created_at=now_utc,
        )
