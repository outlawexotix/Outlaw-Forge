import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import aiosqlite

from app.models.project import (
    MeshBounds,
    MeshTransform,
    OperationRecord,
    Project,
    ProjectCreatePayload,
    ProjectUpdatePayload,
    SourceFile,
    WorkingModel,
)


class ProjectRepository:
    def __init__(self, conn: aiosqlite.Connection):
        self.conn = conn

    async def _fetch_source_files(self, project_id: str) -> List[SourceFile]:
        cursor = await self.conn.execute(
            """
            SELECT id, project_id, filename, file_format, file_size_bytes, storage_path, created_at
            FROM source_files
            WHERE project_id = ?
            ORDER BY created_at ASC
            """,
            (project_id,),
        )
        rows = await cursor.fetchall()
        return [
            SourceFile(
                id=row["id"],
                project_id=row["project_id"],
                filename=row["filename"],
                file_format=row["file_format"],
                file_size_bytes=int(row["file_size_bytes"]),
                storage_path=row["storage_path"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

    async def _fetch_working_models(self, project_id: str) -> List[WorkingModel]:
        cursor = await self.conn.execute(
            """
            SELECT id, project_id, source_file_id, filename, file_format, storage_path,
                   units, bounds_json, triangle_count, vertex_count, surface_area_cm2,
                   volume_cm3, is_watertight, transform_json, created_at, updated_at
            FROM working_models
            WHERE project_id = ?
            ORDER BY created_at ASC
            """,
            (project_id,),
        )
        rows = await cursor.fetchall()
        models = []
        for row in rows:
            bounds_raw = json.loads(row["bounds_json"]) if isinstance(row["bounds_json"], str) else row["bounds_json"]
            transform_raw = json.loads(row["transform_json"]) if isinstance(row["transform_json"], str) else row["transform_json"]
            models.append(
                WorkingModel(
                    id=row["id"],
                    project_id=row["project_id"],
                    source_file_id=row["source_file_id"],
                    filename=row["filename"],
                    file_format=row["file_format"],
                    storage_path=row["storage_path"],
                    units=row["units"] or "mm",
                    bounds=MeshBounds(**bounds_raw),
                    triangle_count=int(row["triangle_count"]),
                    vertex_count=int(row["vertex_count"]),
                    surface_area_cm2=float(row["surface_area_cm2"]),
                    volume_cm3=float(row["volume_cm3"]) if row["volume_cm3"] is not None else None,
                    is_watertight=bool(row["is_watertight"]),
                    transform=MeshTransform(**transform_raw),
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
            )
        return models

    async def _fetch_operations(self, project_id: str) -> List[OperationRecord]:
        cursor = await self.conn.execute(
            """
            SELECT id, project_id, model_id, operation_type, timestamp,
                   parameters_json, resulting_state_ref, user_summary, success
            FROM operations
            WHERE project_id = ?
            ORDER BY timestamp ASC
            """,
            (project_id,),
        )
        rows = await cursor.fetchall()
        operations = []
        for row in rows:
            params = json.loads(row["parameters_json"]) if isinstance(row["parameters_json"], str) else row["parameters_json"]
            operations.append(
                OperationRecord(
                    id=row["id"],
                    project_id=row["project_id"],
                    model_id=row["model_id"],
                    operation_type=row["operation_type"],
                    timestamp=row["timestamp"],
                    parameters=params or {},
                    resulting_state_ref=row["resulting_state_ref"],
                    user_summary=row["user_summary"],
                    success=bool(row["success"]),
                )
            )
        return operations

    async def list_all(self) -> List[Project]:
        """Fetch all projects ordered by updated_at descending with nested entities."""
        cursor = await self.conn.execute(
            """
            SELECT id, name, description, project_type, created_at, updated_at,
                   thumbnail_url, selected_printer_id, units, notes
            FROM projects
            ORDER BY updated_at DESC
            """
        )
        rows = await cursor.fetchall()
        projects: List[Project] = []
        for row in rows:
            project_id = row["id"]
            source_files = await self._fetch_source_files(project_id)
            working_models = await self._fetch_working_models(project_id)
            operations = await self._fetch_operations(project_id)

            projects.append(
                Project(
                    id=row["id"],
                    name=row["name"],
                    description=row["description"] or "",
                    project_type=row["project_type"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    thumbnail_url=row["thumbnail_url"],
                    selected_printer_id=row["selected_printer_id"],
                    units=row["units"] or "mm",
                    notes=row["notes"] or "",
                    source_files=source_files,
                    working_models=working_models,
                    operations=operations,
                )
            )
        return projects

    async def get_by_id(self, project_id: str) -> Optional[Project]:
        """Fetch a specific project by ID including nested entities."""
        cursor = await self.conn.execute(
            """
            SELECT id, name, description, project_type, created_at, updated_at,
                   thumbnail_url, selected_printer_id, units, notes
            FROM projects
            WHERE id = ?
            """,
            (project_id,),
        )
        row = await cursor.fetchone()
        if not row:
            return None

        source_files = await self._fetch_source_files(project_id)
        working_models = await self._fetch_working_models(project_id)
        operations = await self._fetch_operations(project_id)

        return Project(
            id=row["id"],
            name=row["name"],
            description=row["description"] or "",
            project_type=row["project_type"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            thumbnail_url=row["thumbnail_url"],
            selected_printer_id=row["selected_printer_id"],
            units=row["units"] or "mm",
            notes=row["notes"] or "",
            source_files=source_files,
            working_models=working_models,
            operations=operations,
        )

    async def create(self, payload: ProjectCreatePayload) -> Project:
        """Create and persist a new project."""
        project_id = f"proj_{uuid.uuid4().hex[:12]}"
        now_utc = datetime.now(timezone.utc).isoformat()
        description = payload.description or ""
        notes = payload.notes or ""

        await self.conn.execute(
            """
            INSERT INTO projects (
                id, name, description, project_type, created_at, updated_at,
                thumbnail_url, selected_printer_id, units, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                payload.name,
                description,
                payload.project_type,
                now_utc,
                now_utc,
                None,
                payload.selected_printer_id,
                "mm",
                notes,
            ),
        )
        await self.conn.commit()

        return Project(
            id=project_id,
            name=payload.name,
            description=description,
            project_type=payload.project_type,
            created_at=now_utc,
            updated_at=now_utc,
            thumbnail_url=None,
            selected_printer_id=payload.selected_printer_id,
            units="mm",
            notes=notes,
            source_files=[],
            working_models=[],
            operations=[],
        )

    async def update(self, project_id: str, payload: ProjectUpdatePayload) -> Optional[Project]:
        """Update fields of an existing project and return the updated entity."""
        existing = await self.get_by_id(project_id)
        if not existing:
            return None

        update_dict: Dict[str, Any] = payload.model_dump(exclude_unset=True)
        if not update_dict:
            return existing

        now_utc = datetime.now(timezone.utc).isoformat()
        update_dict["updated_at"] = now_utc

        set_clauses = [f"{key} = ?" for key in update_dict.keys()]
        values = list(update_dict.values()) + [project_id]

        query = f"UPDATE projects SET {', '.join(set_clauses)} WHERE id = ?"
        await self.conn.execute(query, values)
        await self.conn.commit()

        return await self.get_by_id(project_id)

    async def delete(self, project_id: str) -> bool:
        """Delete a project by ID."""
        cursor = await self.conn.execute(
            "DELETE FROM projects WHERE id = ?",
            (project_id,),
        )
        await self.conn.commit()
        return cursor.rowcount > 0

    async def add_source_file(
        self,
        project_id: str,
        filename: str,
        file_format: str,
        file_size_bytes: int,
        storage_path: str,
    ) -> SourceFile:
        """Add a source file entry for a project."""
        src_id = f"src_{uuid.uuid4().hex[:12]}"
        now_utc = datetime.now(timezone.utc).isoformat()
        storage_path_str = str(storage_path)

        await self.conn.execute(
            """
            INSERT INTO source_files (
                id, project_id, filename, file_format, file_size_bytes, storage_path, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (src_id, project_id, filename, file_format, file_size_bytes, storage_path_str, now_utc),
        )
        await self.conn.commit()

        return SourceFile(
            id=src_id,
            project_id=project_id,
            filename=filename,
            file_format=file_format,
            file_size_bytes=file_size_bytes,
            storage_path=storage_path_str,
            created_at=now_utc,
        )

    async def add_working_model(
        self,
        project_id: str,
        source_file_id: str,
        filename: str,
        file_format: str,
        storage_path: str,
        bounds: MeshBounds,
        triangle_count: int,
        vertex_count: int,
        surface_area_cm2: float,
        volume_cm3: Optional[float],
        is_watertight: bool,
        transform: MeshTransform,
    ) -> WorkingModel:
        """Add a working model entry for a project."""
        model_id = f"wm_{uuid.uuid4().hex[:12]}"
        now_utc = datetime.now(timezone.utc).isoformat()
        storage_path_str = str(storage_path)

        bounds_json = json.dumps(bounds.model_dump())
        transform_json = json.dumps(transform.model_dump())


        await self.conn.execute(
            """
            INSERT INTO working_models (
                id, project_id, source_file_id, filename, file_format, storage_path,
                units, bounds_json, triangle_count, vertex_count, surface_area_cm2,
                volume_cm3, is_watertight, transform_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                model_id,
                project_id,
                source_file_id,
                filename,
                file_format,
                storage_path_str,
                "mm",

                bounds_json,
                triangle_count,
                vertex_count,
                surface_area_cm2,
                volume_cm3,
                1 if is_watertight else 0,
                transform_json,
                now_utc,
                now_utc,
            ),
        )

        # Also update project's updated_at timestamp
        await self.conn.execute(
            "UPDATE projects SET updated_at = ? WHERE id = ?",
            (now_utc, project_id),
        )
        await self.conn.commit()

        return WorkingModel(
            id=model_id,
            project_id=project_id,
            source_file_id=source_file_id,
            filename=filename,
            file_format=file_format,
            storage_path=storage_path_str,
            units="mm",

            bounds=bounds,
            triangle_count=triangle_count,
            vertex_count=vertex_count,
            surface_area_cm2=surface_area_cm2,
            volume_cm3=volume_cm3,
            is_watertight=is_watertight,
            transform=transform,
            created_at=now_utc,
            updated_at=now_utc,
        )

    async def get_working_model(self, model_id: str) -> Optional[WorkingModel]:
        """Fetch a working model by ID."""
        cursor = await self.conn.execute(
            """
            SELECT id, project_id, source_file_id, filename, file_format, storage_path,
                   units, bounds_json, triangle_count, vertex_count, surface_area_cm2,
                   volume_cm3, is_watertight, transform_json, created_at, updated_at
            FROM working_models
            WHERE id = ?
            """,
            (model_id,),
        )
        row = await cursor.fetchone()
        if not row:
            return None

        bounds_raw = json.loads(row["bounds_json"]) if isinstance(row["bounds_json"], str) else row["bounds_json"]
        transform_raw = json.loads(row["transform_json"]) if isinstance(row["transform_json"], str) else row["transform_json"]

        return WorkingModel(
            id=row["id"],
            project_id=row["project_id"],
            source_file_id=row["source_file_id"],
            filename=row["filename"],
            file_format=row["file_format"],
            storage_path=row["storage_path"],
            units=row["units"] or "mm",
            bounds=MeshBounds(**bounds_raw),
            triangle_count=int(row["triangle_count"]),
            vertex_count=int(row["vertex_count"]),
            surface_area_cm2=float(row["surface_area_cm2"]),
            volume_cm3=float(row["volume_cm3"]) if row["volume_cm3"] is not None else None,
            is_watertight=bool(row["is_watertight"]),
            transform=MeshTransform(**transform_raw),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    async def get_working_model_for_project(self, project_id: str, model_id: str) -> Optional[WorkingModel]:
        """Fetch a working model belonging to a specific project."""
        model = await self.get_working_model(model_id)
        if model and model.project_id == project_id:
            return model
        return None

    async def update_working_model(
        self,
        model_id: str,
        storage_path: Optional[str] = None,
        filename: Optional[str] = None,
        bounds: Optional[MeshBounds] = None,
        triangle_count: Optional[int] = None,
        vertex_count: Optional[int] = None,
        surface_area_cm2: Optional[float] = None,
        volume_cm3: Optional[float] = None,
        is_watertight: Optional[bool] = None,
        transform: Optional[MeshTransform] = None,
    ) -> Optional[WorkingModel]:
        """Update working model attributes (e.g. after scaling or re-analysis)."""
        existing = await self.get_working_model(model_id)
        if not existing:
            return None

        now_utc = datetime.now(timezone.utc).isoformat()
        updates = {"updated_at": now_utc}

        if storage_path is not None:
            updates["storage_path"] = storage_path
        if filename is not None:
            updates["filename"] = filename
        if bounds is not None:
            updates["bounds_json"] = json.dumps(bounds.model_dump())
        if triangle_count is not None:
            updates["triangle_count"] = triangle_count
        if vertex_count is not None:
            updates["vertex_count"] = vertex_count
        if surface_area_cm2 is not None:
            updates["surface_area_cm2"] = surface_area_cm2
        if volume_cm3 is not None:
            updates["volume_cm3"] = volume_cm3
        if is_watertight is not None:
            updates["is_watertight"] = 1 if is_watertight else 0
        if transform is not None:
            updates["transform_json"] = json.dumps(transform.model_dump())

        set_clauses = [f"{k} = ?" for k in updates.keys()]
        values = list(updates.values()) + [model_id]

        await self.conn.execute(
            f"UPDATE working_models SET {', '.join(set_clauses)} WHERE id = ?",
            values,
        )

        # Update project updated_at
        await self.conn.execute(
            "UPDATE projects SET updated_at = ? WHERE id = ?",
            (now_utc, existing.project_id),
        )
        await self.conn.commit()

        return await self.get_working_model(model_id)

    async def record_operation(
        self,
        project_id: str,
        operation_type: str,
        user_summary: str,
        model_id: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
        resulting_state_ref: Optional[str] = None,
        success: bool = True,
    ) -> OperationRecord:
        """Record an operation log entry."""
        op_id = f"op_{uuid.uuid4().hex[:12]}"
        now_utc = datetime.now(timezone.utc).isoformat()
        params = parameters or {}
        params_json = json.dumps(params)

        await self.conn.execute(
            """
            INSERT INTO operations (
                id, project_id, model_id, operation_type, timestamp,
                parameters_json, resulting_state_ref, user_summary, success
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                op_id,
                project_id,
                model_id,
                operation_type,
                now_utc,
                params_json,
                resulting_state_ref or model_id,
                user_summary,
                1 if success else 0,
            ),
        )
        await self.conn.commit()

        return OperationRecord(
            id=op_id,
            project_id=project_id,
            model_id=model_id,
            operation_type=operation_type,  # type: ignore
            timestamp=now_utc,
            parameters=params,
            resulting_state_ref=resulting_state_ref or model_id,
            user_summary=user_summary,
            success=success,
        )

    async def delete_working_model(self, model_id: str) -> bool:
        """Delete a working model from database."""
        cursor = await self.conn.execute(
            "DELETE FROM working_models WHERE id = ?",
            (model_id,),
        )
        await self.conn.commit()
        return cursor.rowcount > 0


