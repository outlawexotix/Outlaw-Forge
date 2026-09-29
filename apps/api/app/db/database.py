import os
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncGenerator, Optional
import aiosqlite

from app.core.config import settings


def get_db_path(custom_path: Optional[str] = None) -> Path:
    """Resolve the SQLite database path ensuring parent directory exists."""
    path_str = custom_path or os.getenv("SQLITE_DB_PATH", settings.SQLITE_DB_PATH)
    path = Path(path_str)
    if not path.is_absolute():
        curr = Path(__file__).resolve().parent
        while curr.parent != curr:
            if (curr / "apps").exists() and (curr / "packages").exists():
                break
            curr = curr.parent
        repo_root = curr
        path = (repo_root / path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


async def get_db(custom_path: Optional[str] = None) -> AsyncGenerator[aiosqlite.Connection, None]:
    """Yield an async SQLite connection configured with Row factory and foreign keys enabled."""
    db_file = get_db_path(custom_path)
    async with aiosqlite.connect(str(db_file)) as conn:
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA foreign_keys = ON;")
        yield conn


async def init_db(custom_path: Optional[str] = None) -> None:
    """Initialize database schema and seed default printer profiles if missing."""
    db_file = get_db_path(custom_path)
    async with aiosqlite.connect(str(db_file)) as conn:
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA foreign_keys = ON;")

        # 1. Projects table
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                project_type TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                thumbnail_url TEXT,
                selected_printer_id TEXT,
                units TEXT DEFAULT 'mm',
                notes TEXT
            );
            """
        )

        # 2. Source files table
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS source_files (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                filename TEXT NOT NULL,
                file_format TEXT NOT NULL,
                file_size_bytes INTEGER NOT NULL,
                storage_path TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            );
            """
        )

        # 3. Working models table
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS working_models (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                source_file_id TEXT NOT NULL,
                filename TEXT NOT NULL,
                file_format TEXT NOT NULL,
                storage_path TEXT NOT NULL,
                units TEXT DEFAULT 'mm',
                bounds_json TEXT NOT NULL,
                triangle_count INTEGER NOT NULL,
                vertex_count INTEGER NOT NULL,
                surface_area_cm2 REAL NOT NULL,
                volume_cm3 REAL,
                is_watertight INTEGER NOT NULL,
                transform_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            );
            """
        )

        # 4. Printer profiles table
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS printer_profiles (
                id TEXT PRIMARY KEY,
                manufacturer TEXT NOT NULL,
                model TEXT NOT NULL,
                build_width_mm REAL NOT NULL,
                build_depth_mm REAL NOT NULL,
                build_height_mm REAL NOT NULL,
                nozzle_diameter_mm REAL NOT NULL,
                notes TEXT,
                created_at TEXT NOT NULL
            );
            """
        )

        # 5. Operations table
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS operations (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                model_id TEXT,
                operation_type TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                parameters_json TEXT NOT NULL,
                resulting_state_ref TEXT,
                user_summary TEXT NOT NULL,
                success INTEGER NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            );
            """
        )

        # Seed default printer profiles if not existing
        now_utc = datetime.now(timezone.utc).isoformat()
        default_printers = [
            (
                "printer_ender_3",
                "Creality",
                "Ender-3",
                220.0,
                220.0,
                250.0,
                0.4,
                "Standard Creality Ender-3 profile",
                now_utc,
            ),
            (
                "printer_ender_3_s1",
                "Creality",
                "Ender-3 S1",
                220.0,
                220.0,
                270.0,
                0.4,
                "Creality Ender-3 S1 profile with direct drive and CR-Touch",
                now_utc,
            ),
            (
                "printer_bambu_x1c",
                "Bambu Lab",
                "X1-Carbon",
                256.0,
                256.0,
                256.0,
                0.4,
                "Bambu Lab X1-Carbon high-speed CoreXY 3D printer",
                now_utc,
            ),
            (
                "printer_prusa_mk4",
                "Prusa",
                "Original Prusa MK4",
                250.0,
                210.0,
                220.0,
                0.4,
                "Original Prusa MK4 with Nextruder and 32-bit architecture",
                now_utc,
            ),
            (
                "printer_voron_2_4_350",
                "Voron",
                "Voron 2.4 350",
                350.0,
                350.0,
                350.0,
                0.4,
                "Voron 2.4 350 CoreXY 3D printer",
                now_utc,
            ),
            (
                "printer_elegoo_neptune_4_pro",
                "Elegoo",
                "Neptune 4 Pro",
                225.0,
                225.0,
                265.0,
                0.4,
                "Elegoo Neptune 4 Pro high-speed FDM 3D printer",
                now_utc,
            ),
        ]

        for printer in default_printers:
            # Check if profile already exists by (manufacturer, model) or id
            cursor = await conn.execute(
                "SELECT id FROM printer_profiles WHERE id = ? OR (manufacturer = ? AND model = ?)",
                (printer[0], printer[1], printer[2]),
            )
            existing = await cursor.fetchone()
            if not existing:
                await conn.execute(
                    """
                    INSERT INTO printer_profiles (
                        id, manufacturer, model, build_width_mm, build_depth_mm,
                        build_height_mm, nozzle_diameter_mm, notes, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    printer,
                )

        await conn.commit()
