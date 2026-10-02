import os
import uuid
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
import aiosqlite

from app.db.database import get_db
from app.models.mesh import (
    ArrangeItemPlacement,
    ArrangeProjectPayload,
    ArrangeProjectResult,
    ExportModelPayload,
    ExportModelResponse,
    ExportProject3MFPayload,
    ExportProject3MFResponse,
    HollowModelPayload,
    HollowModelResult,
    OverhangAnalysisResult,
    RepairModelPayload,
    RepairModelResult,
    RotateModelPayload,
    ScaleModelPayload,
    SliceModelPayload,
    SliceModelResult,
)
from app.models.printer import PrinterProfile
from app.models.project import (
    PrintabilityAnalysis,
    Project,
    WorkingModel,
)
from app.repositories.printer_repo import PrinterRepository
from app.repositories.project_repo import ProjectRepository
from app.services.mesh_service import mesh_service
from app.services.printability_service import printability_service
from app.services.storage import storage_service

router = APIRouter()


def get_project_repo(conn: aiosqlite.Connection = Depends(get_db)) -> ProjectRepository:
    return ProjectRepository(conn)


def get_printer_repo(conn: aiosqlite.Connection = Depends(get_db)) -> PrinterRepository:
    return PrinterRepository(conn)


def get_media_type_for_format(file_format: str) -> str:
    fmt = file_format.lower().lstrip(".")
    if fmt == "stl":
        return "model/stl"
    elif fmt == "obj":
        return "model/obj"
    elif fmt == "glb":
        return "model/gltf-binary"
    elif fmt == "gltf":
        return "model/gltf+json"
    return "application/octet-stream"


# --- Project Model Endpoints ---


@router.post(
    "/projects/{project_id}/models/import",
    response_model=WorkingModel,
    status_code=status.HTTP_201_CREATED,
    summary="Import 3D model into project",
)
async def import_model(
    project_id: str,
    file: UploadFile = File(...),
    project_repo: ProjectRepository = Depends(get_project_repo),
) -> WorkingModel:
    """
    Upload and import a 3D model (.stl, .obj, .glb, .gltf) into a project.
    Stores immutable original file, performs computational geometry analysis,
    creates working copy, and logs the IMPORT operation.
    """
    project = await project_repo.get_by_id(project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID '{project_id}' not found",
        )

    filename = file.filename or "model.stl"
    file_bytes = await file.read()

    # 1. Validate extension and size, then save original immutably
    orig_path, orig_rel_path, sanitized_name, file_size = storage_service.save_original(
        file_bytes=file_bytes,
        filename=filename,
    )
    ext = storage_service.validate_extension(sanitized_name)

    # 2. Parse and analyze 3D geometry with Trimesh
    mesh = mesh_service.load_mesh(orig_path)
    analysis = mesh_service.analyze_mesh(mesh)

    # 3. Create initial working copy
    working_path, working_rel_path = storage_service.save_working(
        file_bytes=file_bytes,
        filename=sanitized_name,
    )

    # 4. Insert SourceFile record
    source_file = await project_repo.add_source_file(
        project_id=project_id,
        filename=sanitized_name,
        file_format=ext,
        file_size_bytes=file_size,
        storage_path=orig_rel_path,
    )

    # 5. Insert WorkingModel record
    from app.models.project import MeshTransform
    initial_transform = MeshTransform(
        position_mm=[0.0, 0.0, 0.0],
        rotation_deg=[0.0, 0.0, 0.0],
        scale_factors=[1.0, 1.0, 1.0],
        uniform_scale_percent=100.0,
    )

    working_model = await project_repo.add_working_model(
        project_id=project_id,
        source_file_id=source_file.id,
        filename=sanitized_name,
        file_format=ext,
        storage_path=working_rel_path,
        bounds=analysis.bounds,
        triangle_count=analysis.triangle_count,
        vertex_count=analysis.vertex_count,
        surface_area_cm2=analysis.surface_area_cm2,
        volume_cm3=analysis.volume_cm3,
        is_watertight=analysis.is_watertight,
        transform=initial_transform,
    )

    # 6. Log IMPORT operation
    await project_repo.record_operation(
        project_id=project_id,
        model_id=working_model.id,
        operation_type="IMPORT",
        parameters={
            "original_filename": filename,
            "sanitized_filename": sanitized_name,
            "format": ext,
            "file_size_bytes": file_size,
            "triangle_count": analysis.triangle_count,
        },
        user_summary=f"Imported 3D model '{sanitized_name}' ({analysis.triangle_count:,} triangles)",
        resulting_state_ref=working_model.id,
        success=True,
    )

    return working_model


@router.get(
    "/projects/{project_id}/models/{model_id}",
    response_model=WorkingModel,
    summary="Get working model metadata in project",
)
async def get_project_model(
    project_id: str,
    model_id: str,
    project_repo: ProjectRepository = Depends(get_project_repo),
) -> WorkingModel:
    """Retrieve metadata and bounds for a specific working model in a project."""
    model = await project_repo.get_working_model_for_project(project_id, model_id)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model '{model_id}' not found in project '{project_id}'",
        )
    return model


@router.post(
    "/projects/{project_id}/models/{model_id}/analyze",
    response_model=WorkingModel,
    summary="Re-analyze working model geometry",
)
async def analyze_model(
    project_id: str,
    model_id: str,
    project_repo: ProjectRepository = Depends(get_project_repo),
) -> WorkingModel:
    """Perform re-analysis of geometry bounds, surface area, and watertightness."""
    model = await project_repo.get_working_model_for_project(project_id, model_id)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model '{model_id}' not found in project '{project_id}'",
        )

    resolved_path = storage_service.resolve_path(model.storage_path)
    mesh = mesh_service.load_mesh(resolved_path)
    analysis = mesh_service.analyze_mesh(mesh)

    updated_model = await project_repo.update_working_model(
        model_id=model_id,
        bounds=analysis.bounds,
        triangle_count=analysis.triangle_count,
        vertex_count=analysis.vertex_count,
        surface_area_cm2=analysis.surface_area_cm2,
        volume_cm3=analysis.volume_cm3,
        is_watertight=analysis.is_watertight,
    )
    if not updated_model:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update model analysis records.",
        )
    return updated_model


@router.post(
    "/projects/{project_id}/models/{model_id}/scale",
    response_model=WorkingModel,
    summary="Scale working model",
)
async def scale_model(
    project_id: str,
    model_id: str,
    payload: ScaleModelPayload,
    project_repo: ProjectRepository = Depends(get_project_repo),
) -> WorkingModel:
    """
    Scale a model by percentage or target dimensions, save transformed geometry
    in data/working/, update database metadata, and log the SCALE operation.
    """
    model = await project_repo.get_working_model_for_project(project_id, model_id)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model '{model_id}' not found in project '{project_id}'",
        )

    resolved_path = storage_service.resolve_path(model.storage_path)
    mesh = mesh_service.load_mesh(resolved_path)

    # Transform mesh
    scaled_mesh, transform = mesh_service.scale_mesh_with_transform(
        mesh=mesh,
        payload_or_percent=payload,
    )

    # Re-analyze transformed mesh
    analysis = mesh_service.analyze_mesh(scaled_mesh)

    # Export scaled mesh to new working file
    scaled_filename = f"scaled_{model.filename}"
    file_uuid = uuid.uuid4().hex[:12]
    new_working_filename = f"{file_uuid}_{storage_service.sanitize_filename(scaled_filename)}"
    new_working_path = (storage_service.working_dir / new_working_filename).resolve()
    storage_service.validate_safe_path(new_working_path)

    mesh_service.export_mesh(scaled_mesh, new_working_path, format=model.file_format)
    relative_storage_path = f"working/{new_working_filename}"

    # Update working model in DB
    updated_model = await project_repo.update_working_model(
        model_id=model_id,
        storage_path=relative_storage_path,
        bounds=analysis.bounds,
        triangle_count=analysis.triangle_count,
        vertex_count=analysis.vertex_count,
        surface_area_cm2=analysis.surface_area_cm2,
        volume_cm3=analysis.volume_cm3,
        is_watertight=analysis.is_watertight,
        transform=transform,
    )

    if not updated_model:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update working model in database.",
        )

    # Log SCALE operation
    user_summary = (
        f"Scaled model to {transform.uniform_scale_percent:.1f}% uniform"
        if payload.uniform_scale_percent is not None
        else f"Scaled model to dimensions {analysis.bounds.dimensions_mm}"
    )

    await project_repo.record_operation(
        project_id=project_id,
        model_id=model_id,
        operation_type="SCALE",
        parameters=payload.model_dump(),
        user_summary=user_summary,
        resulting_state_ref=model_id,
        success=True,
    )

    return updated_model


@router.post(
    "/projects/{project_id}/models/{model_id}/rotate",
    response_model=WorkingModel,
    summary="Rotate working model",
)
@router.post(
    "/models/{model_id}/rotate",
    response_model=WorkingModel,
    summary="Rotate working model direct",
)
async def rotate_model(
    model_id: str,
    payload: RotateModelPayload,
    project_id: Optional[str] = None,
    project_repo: ProjectRepository = Depends(get_project_repo),
) -> WorkingModel:
    """
    Rotate model by Euler degrees (X, Y, Z), save working revision,
    update database metadata, and log OPERATION 'ROTATE'.
    """
    if project_id:
        model = await project_repo.get_working_model_for_project(project_id, model_id)
    else:
        model = await project_repo.get_working_model(model_id)

    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model '{model_id}' not found",
        )

    resolved_path = storage_service.resolve_path(model.storage_path)
    mesh = mesh_service.load_mesh(resolved_path)

    rx = payload.x
    ry = payload.y
    rz = payload.z

    rotated_mesh = mesh_service.rotate_mesh(mesh, rx_deg=rx, ry_deg=ry, rz_deg=rz)
    analysis = mesh_service.analyze_mesh(rotated_mesh)

    rotated_filename = f"rotated_{model.filename}"
    file_uuid = uuid.uuid4().hex[:12]
    new_working_filename = f"{file_uuid}_{storage_service.sanitize_filename(rotated_filename)}"
    new_working_path = (storage_service.working_dir / new_working_filename).resolve()
    storage_service.validate_safe_path(new_working_path)

    mesh_service.export_mesh(rotated_mesh, new_working_path, format=model.file_format)
    relative_storage_path = f"working/{new_working_filename}"

    from app.models.project import MeshTransform
    new_transform = MeshTransform(
        position_mm=model.transform.position_mm,
        rotation_deg=[
            round((model.transform.rotation_deg[0] + rx) % 360, 4),
            round((model.transform.rotation_deg[1] + ry) % 360, 4),
            round((model.transform.rotation_deg[2] + rz) % 360, 4),
        ],
        scale_factors=model.transform.scale_factors,
        uniform_scale_percent=model.transform.uniform_scale_percent,
    )

    updated_model = await project_repo.update_working_model(
        model_id=model_id,
        storage_path=relative_storage_path,
        bounds=analysis.bounds,
        triangle_count=analysis.triangle_count,
        vertex_count=analysis.vertex_count,
        surface_area_cm2=analysis.surface_area_cm2,
        volume_cm3=analysis.volume_cm3,
        is_watertight=analysis.is_watertight,
        transform=new_transform,
    )

    if not updated_model:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update working model in database.",
        )

    await project_repo.record_operation(
        project_id=model.project_id,
        model_id=model_id,
        operation_type="ROTATE",
        parameters={"rx_deg": rx, "ry_deg": ry, "rz_deg": rz},
        user_summary=f"Rotated model by X:{rx}°, Y:{ry}°, Z:{rz}°",
        resulting_state_ref=model_id,
        success=True,
    )

    return updated_model


@router.post(
    "/projects/{project_id}/models/{model_id}/center",
    response_model=WorkingModel,
    summary="Center working model on bed",
)
@router.post(
    "/models/{model_id}/center",
    response_model=WorkingModel,
    summary="Center working model direct",
)
async def center_model(
    model_id: str,
    project_id: Optional[str] = None,
    project_repo: ProjectRepository = Depends(get_project_repo),
) -> WorkingModel:
    """
    Center model at (0,0) in X,Y and align bottom to Z=0 on bed, save working revision,
    update database metadata, and log OPERATION 'CENTER'.
    """
    if project_id:
        model = await project_repo.get_working_model_for_project(project_id, model_id)
    else:
        model = await project_repo.get_working_model(model_id)

    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model '{model_id}' not found",
        )

    resolved_path = storage_service.resolve_path(model.storage_path)
    mesh = mesh_service.load_mesh(resolved_path)

    centered_mesh = mesh_service.center_mesh_on_bed(mesh)
    analysis = mesh_service.analyze_mesh(centered_mesh)

    centered_filename = f"centered_{model.filename}"
    file_uuid = uuid.uuid4().hex[:12]
    new_working_filename = f"{file_uuid}_{storage_service.sanitize_filename(centered_filename)}"
    new_working_path = (storage_service.working_dir / new_working_filename).resolve()
    storage_service.validate_safe_path(new_working_path)

    mesh_service.export_mesh(centered_mesh, new_working_path, format=model.file_format)
    relative_storage_path = f"working/{new_working_filename}"

    from app.models.project import MeshTransform
    new_transform = MeshTransform(
        position_mm=[0.0, 0.0, 0.0],
        rotation_deg=model.transform.rotation_deg,
        scale_factors=model.transform.scale_factors,
        uniform_scale_percent=model.transform.uniform_scale_percent,
    )

    updated_model = await project_repo.update_working_model(
        model_id=model_id,
        storage_path=relative_storage_path,
        bounds=analysis.bounds,
        triangle_count=analysis.triangle_count,
        vertex_count=analysis.vertex_count,
        surface_area_cm2=analysis.surface_area_cm2,
        volume_cm3=analysis.volume_cm3,
        is_watertight=analysis.is_watertight,
        transform=new_transform,
    )

    if not updated_model:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update working model in database.",
        )

    await project_repo.record_operation(
        project_id=model.project_id,
        model_id=model_id,
        operation_type="CENTER",
        parameters={"centered": True, "position_mm": [0.0, 0.0, 0.0]},
        user_summary="Centered model on build bed at (0, 0, 0)",
        resulting_state_ref=model_id,
        success=True,
    )

    return updated_model


@router.post(
    "/projects/{project_id}/models/{model_id}/lay_flat",
    response_model=WorkingModel,
    summary="Lay working model flat on bed",
)
@router.post(
    "/models/{model_id}/lay_flat",
    response_model=WorkingModel,
    summary="Lay working model flat direct",
)
async def lay_flat_model(
    model_id: str,
    project_id: Optional[str] = None,
    project_repo: ProjectRepository = Depends(get_project_repo),
) -> WorkingModel:
    """
    Auto-orient model to its largest flat base on build plate, save working revision,
    update database metadata, and log OPERATION 'LAY_FLAT'.
    """
    if project_id:
        model = await project_repo.get_working_model_for_project(project_id, model_id)
    else:
        model = await project_repo.get_working_model(model_id)

    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model '{model_id}' not found",
        )

    resolved_path = storage_service.resolve_path(model.storage_path)
    mesh = mesh_service.load_mesh(resolved_path)

    flat_mesh = mesh_service.lay_flat_mesh(mesh)
    analysis = mesh_service.analyze_mesh(flat_mesh)

    flat_filename = f"flat_{model.filename}"
    file_uuid = uuid.uuid4().hex[:12]
    new_working_filename = f"{file_uuid}_{storage_service.sanitize_filename(flat_filename)}"
    new_working_path = (storage_service.working_dir / new_working_filename).resolve()
    storage_service.validate_safe_path(new_working_path)

    mesh_service.export_mesh(flat_mesh, new_working_path, format=model.file_format)
    relative_storage_path = f"working/{new_working_filename}"

    from app.models.project import MeshTransform
    new_transform = MeshTransform(
        position_mm=[0.0, 0.0, 0.0],
        rotation_deg=model.transform.rotation_deg,
        scale_factors=model.transform.scale_factors,
        uniform_scale_percent=model.transform.uniform_scale_percent,
    )

    updated_model = await project_repo.update_working_model(
        model_id=model_id,
        storage_path=relative_storage_path,
        bounds=analysis.bounds,
        triangle_count=analysis.triangle_count,
        vertex_count=analysis.vertex_count,
        surface_area_cm2=analysis.surface_area_cm2,
        volume_cm3=analysis.volume_cm3,
        is_watertight=analysis.is_watertight,
        transform=new_transform,
    )

    if not updated_model:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update working model in database.",
        )

    await project_repo.record_operation(
        project_id=model.project_id,
        model_id=model_id,
        operation_type="LAY_FLAT",
        parameters={"lay_flat": True},
        user_summary="Auto-oriented model to flat base on build plate",
        resulting_state_ref=model_id,
        success=True,
    )

    return updated_model


@router.get(
    "/projects/{project_id}/models/{model_id}/overhangs",
    response_model=OverhangAnalysisResult,
    summary="Get model overhang diagnostics",
)
@router.get(
    "/models/{model_id}/overhangs",
    response_model=OverhangAnalysisResult,
    summary="Get model overhang diagnostics direct",
)
async def get_model_overhangs(
    model_id: str,
    project_id: Optional[str] = None,
    critical_angle_deg: float = Query(default=45.0, ge=0.0, le=90.0, description="Critical overhang angle in degrees"),
    project_repo: ProjectRepository = Depends(get_project_repo),
) -> OverhangAnalysisResult:
    """
    Calculate overhang diagnostics returning percentage of downward-facing facets
    steeper than critical angle requiring support structures.
    """
    if project_id:
        model = await project_repo.get_working_model_for_project(project_id, model_id)
    else:
        model = await project_repo.get_working_model(model_id)

    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model '{model_id}' not found",
        )

    resolved_path = storage_service.resolve_path(model.storage_path)
    mesh = mesh_service.load_mesh(resolved_path)

    diagnostics = mesh_service.analyze_overhangs(mesh, critical_angle_deg=critical_angle_deg)
    diagnostics.model_id = model_id
    return diagnostics


@router.post(
    "/projects/{project_id}/models/{model_id}/repair",
    response_model=RepairModelResult,
    summary="Automated mesh repair and geometry healing",
)
@router.post(
    "/models/{model_id}/repair",
    response_model=RepairModelResult,
    summary="Automated mesh repair and geometry healing direct",
)
async def repair_model(
    model_id: str,
    payload: Optional[RepairModelPayload] = None,
    project_id: Optional[str] = None,
    project_repo: ProjectRepository = Depends(get_project_repo),
) -> RepairModelResult:
    """
    Automated mesh repair and geometric healing:
    - Removes degenerate zero-area faces and duplicate triangles
    - Merges coincident vertices within tolerance
    - Unifies vertex winding order and fixes inverted normals
    - Fills and triangulates open boundary holes to restore watertight manifold topology
    Saves repaired mesh revision in data/working/, updates database metadata, and logs OPERATION 'REPAIR'.
    """
    if project_id:
        model = await project_repo.get_working_model_for_project(project_id, model_id)
    else:
        model = await project_repo.get_working_model(model_id)

    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model '{model_id}' not found",
        )

    resolved_path = storage_service.resolve_path(model.storage_path)
    mesh = mesh_service.load_mesh(resolved_path)

    opts = payload or RepairModelPayload()
    repaired_mesh, report = mesh_service.repair_mesh(
        mesh=mesh,
        fill_holes=opts.fill_holes,
        fix_normals=opts.fix_normals,
        remove_degenerate=opts.effective_remove_degenerate,
        weld_vertices=opts.weld_vertices,
        weld_tolerance_mm=opts.effective_weld_tolerance_mm,
    )

    analysis = mesh_service.analyze_mesh(repaired_mesh)

    repaired_filename = f"repaired_{model.filename}"
    file_uuid = uuid.uuid4().hex[:12]
    new_working_filename = f"{file_uuid}_{storage_service.sanitize_filename(repaired_filename)}"
    new_working_path = (storage_service.working_dir / new_working_filename).resolve()
    storage_service.validate_safe_path(new_working_path)

    mesh_service.export_mesh(repaired_mesh, new_working_path, format=model.file_format)
    relative_storage_path = f"working/{new_working_filename}"

    updated_model = await project_repo.update_working_model(
        model_id=model_id,
        storage_path=relative_storage_path,
        bounds=analysis.bounds,
        triangle_count=analysis.triangle_count,
        vertex_count=analysis.vertex_count,
        surface_area_cm2=analysis.surface_area_cm2,
        volume_cm3=analysis.volume_cm3,
        is_watertight=analysis.is_watertight,
        transform=model.transform,
    )

    if not updated_model:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update working model in database.",
        )

    await project_repo.record_operation(
        project_id=model.project_id,
        model_id=model_id,
        operation_type="REPAIR",
        parameters=opts.model_dump(),
        user_summary=f"Automated mesh repair: {report.holes_filled} holes filled, {report.degenerate_faces_removed} degenerate faces removed, watertight: {report.is_watertight_after}",
        resulting_state_ref=model_id,
        success=True,
    )

    return RepairModelResult(
        repaired_model=updated_model,
        report=report,
        message=f"Mesh repair completed successfully: {'Watertight' if report.is_watertight_after else 'Healed'}",
    )


@router.post(
    "/projects/{project_id}/models/{model_id}/slice",
    response_model=SliceModelResult,
    summary="Planar slice model into top and bottom parts",
)
@router.post(
    "/models/{model_id}/slice",
    response_model=SliceModelResult,
    summary="Planar slice model direct",
)
async def slice_model(
    model_id: str,
    payload: SliceModelPayload,
    project_id: Optional[str] = None,
    project_repo: ProjectRepository = Depends(get_project_repo),
) -> SliceModelResult:
    """
    Split a 3D model into top and bottom watertight halves along an arbitrary planar slice.
    Optionally generate interlocking alignment dowel pegs and sockets on mating cut surfaces.
    Saves both halves as new working models in data/working/, adds them to the project,
    and logs the SLICE operation.
    """
    if project_id:
        model = await project_repo.get_working_model_for_project(project_id, model_id)
    else:
        model = await project_repo.get_working_model(model_id)

    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model '{model_id}' not found",
        )

    resolved_path = storage_service.resolve_path(model.storage_path)
    mesh = mesh_service.load_mesh(resolved_path)

    try:
        top_mesh, bottom_mesh, cut_area_cm2 = mesh_service.slice_mesh(
            mesh=mesh,
            plane_origin=payload.plane_origin,
            plane_normal=payload.plane_normal,
            cap_faces=payload.cap_faces,
            create_pegs=payload.create_pegs,
            peg_radius_mm=payload.peg_radius_mm,
            peg_height_mm=payload.peg_height_mm,
            peg_clearance_mm=payload.peg_clearance_mm,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to slice mesh: {str(e)}",
        )

    # Analyze both sliced meshes
    top_analysis = mesh_service.analyze_mesh(top_mesh)
    bottom_analysis = mesh_service.analyze_mesh(bottom_mesh)

    stem = Path(model.filename).stem
    ext = model.file_format.lower().lstrip(".")

    top_filename = f"{stem}_top.{ext}"
    top_uuid = uuid.uuid4().hex[:12]
    top_working_filename = f"{top_uuid}_{storage_service.sanitize_filename(top_filename)}"
    top_working_path = (storage_service.working_dir / top_working_filename).resolve()
    storage_service.validate_safe_path(top_working_path)
    mesh_service.export_mesh(top_mesh, top_working_path, format=ext)
    top_rel_path = f"working/{top_working_filename}"

    bottom_filename = f"{stem}_bottom.{ext}"
    bottom_uuid = uuid.uuid4().hex[:12]
    bottom_working_filename = f"{bottom_uuid}_{storage_service.sanitize_filename(bottom_filename)}"
    bottom_working_path = (storage_service.working_dir / bottom_working_filename).resolve()
    storage_service.validate_safe_path(bottom_working_path)
    mesh_service.export_mesh(bottom_mesh, bottom_working_path, format=ext)
    bottom_rel_path = f"working/{bottom_working_filename}"

    from app.models.project import MeshTransform
    base_transform = MeshTransform(
        position_mm=[0.0, 0.0, 0.0],
        rotation_deg=[0.0, 0.0, 0.0],
        scale_factors=[1.0, 1.0, 1.0],
        uniform_scale_percent=100.0,
    )

    top_working = await project_repo.add_working_model(
        project_id=model.project_id,
        source_file_id=model.source_file_id,
        filename=top_filename,
        file_format=ext,
        storage_path=top_rel_path,
        bounds=top_analysis.bounds,
        triangle_count=top_analysis.triangle_count,
        vertex_count=top_analysis.vertex_count,
        surface_area_cm2=top_analysis.surface_area_cm2,
        volume_cm3=top_analysis.volume_cm3,
        is_watertight=top_analysis.is_watertight,
        transform=base_transform,
    )

    bottom_working = await project_repo.add_working_model(
        project_id=model.project_id,
        source_file_id=model.source_file_id,
        filename=bottom_filename,
        file_format=ext,
        storage_path=bottom_rel_path,
        bounds=bottom_analysis.bounds,
        triangle_count=bottom_analysis.triangle_count,
        vertex_count=bottom_analysis.vertex_count,
        surface_area_cm2=bottom_analysis.surface_area_cm2,
        volume_cm3=bottom_analysis.volume_cm3,
        is_watertight=bottom_analysis.is_watertight,
        transform=base_transform,
    )

    await project_repo.record_operation(
        project_id=model.project_id,
        model_id=model_id,
        operation_type="SLICE",
        parameters=payload.model_dump(),
        user_summary=f"Planar sliced model into 2 parts: '{top_filename}' and '{bottom_filename}' (Cut Area: {cut_area_cm2} cm²)",
        resulting_state_ref=f"{top_working.id},{bottom_working.id}",
        success=True,
    )

    return SliceModelResult(
        top_model=top_working,
        bottom_model=bottom_working,
        cut_area_cm2=cut_area_cm2,
        message=f"Model successfully split into '{top_filename}' and '{bottom_filename}'",
    )


@router.post(
    "/projects/{project_id}/models/{model_id}/export",
    response_model=ExportModelResponse,
    summary="Export working model to STL, OBJ, or GLB",
)
async def export_model(
    project_id: str,
    model_id: str,
    payload: ExportModelPayload,
    project_repo: ProjectRepository = Depends(get_project_repo),
) -> ExportModelResponse:
    """
    Export the model into STL, OBJ, or GLB format in data/exports/ and log the EXPORT operation.
    """
    model = await project_repo.get_working_model_for_project(project_id, model_id)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model '{model_id}' not found in project '{project_id}'",
        )

    resolved_path = storage_service.resolve_path(model.storage_path)
    mesh = mesh_service.load_mesh(resolved_path)

    base_name = Path(model.filename).stem
    out_format = payload.format.lower().lstrip(".")
    export_filename = payload.filename or f"{base_name}_export.{out_format}"
    clean_export_name = storage_service.sanitize_filename(export_filename)

    file_uuid = uuid.uuid4().hex[:12]
    stored_export_name = f"{file_uuid}_{clean_export_name}"
    dest_path = (storage_service.exports_dir / stored_export_name).resolve()
    storage_service.validate_safe_path(dest_path)

    mesh_service.export_mesh(mesh, dest_path, format=out_format)

    # Log EXPORT operation
    await project_repo.record_operation(
        project_id=project_id,
        model_id=model_id,
        operation_type="EXPORT",
        parameters={"format": out_format, "filename": clean_export_name},
        user_summary=f"Exported model as {out_format.upper()} ({clean_export_name})",
        resulting_state_ref=f"exports/{stored_export_name}",
        success=True,
    )

    download_url = f"/models/exports/{stored_export_name}"
    return ExportModelResponse(download_url=download_url, filename=clean_export_name)


# --- Printability Evaluation Endpoint ---


@router.get(
    "/projects/{project_id}/printability",
    response_model=PrintabilityAnalysis,
    summary="Evaluate printability for project",
)
async def evaluate_printability(
    project_id: str,
    printer_id: Optional[str] = Query(default=None, description="Optional printer ID override"),
    model_id: Optional[str] = Query(default=None, description="Optional working model ID override"),
    project_repo: ProjectRepository = Depends(get_project_repo),
    printer_repo: PrinterRepository = Depends(get_printer_repo),
) -> PrintabilityAnalysis:
    """
    Evaluate 3D model dimensions and geometry against the project's selected printer profile.
    Calculates build volume fit, exceeded dimensions, and multi-severity findings.
    """
    project = await project_repo.get_by_id(project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID '{project_id}' not found",
        )

    target_printer_id = printer_id or project.selected_printer_id
    if not target_printer_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No printer selected for this project. Please select or specify a printer profile.",
        )

    printer = await printer_repo.get_by_id(target_printer_id)
    if not printer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Printer profile '{target_printer_id}' not found",
        )

    if model_id:
        model = await project_repo.get_working_model_for_project(project_id, model_id)
        if not model:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Model '{model_id}' not found in project '{project_id}'",
            )
    else:
        if not project.working_models:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Project has no 3D models imported yet. Please import a model first.",
            )
        model = project.working_models[-1]

    return printability_service.evaluate(model=model, printer=printer)


# --- Raw Mesh and Export Serving Endpoints ---


@router.get(
    "/models/{model_id}/file",
    summary="Serve raw 3D mesh file for Three.js rendering",
)
@router.get(
    "/projects/{project_id}/models/{model_id}/file",
    summary="Serve raw 3D mesh file via project path",
)
async def serve_model_file(
    model_id: str,
    project_id: Optional[str] = None,
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    """
    Stream the raw binary/text 3D model file (.stl, .obj, .glb) for client Three.js rendering.
    """
    model = await project_repo.get_working_model(model_id)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model '{model_id}' not found",
        )

    if project_id and model.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model '{model_id}' does not belong to project '{project_id}'",
        )

    resolved_path = storage_service.resolve_path(model.storage_path)
    if not resolved_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model file on storage disk not found.",
        )

    media_type = get_media_type_for_format(model.file_format)
    return FileResponse(
        path=str(resolved_path),
        media_type=media_type,
        filename=model.filename,
    )


@router.get(
    "/models/{model_id}",
    response_model=WorkingModel,
    summary="Get working model metadata by ID",
)
async def get_model_direct(
    model_id: str,
    project_repo: ProjectRepository = Depends(get_project_repo),
) -> WorkingModel:
    """Retrieve working model directly by model ID."""
    model = await project_repo.get_working_model(model_id)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model '{model_id}' not found",
        )
    return model


@router.get(
    "/models/exports/{filename}",
    summary="Download exported 3D model file",
)
async def download_exported_file(filename: str):
    """Serve exported 3D files from storage."""
    clean_name = storage_service.sanitize_filename(filename)
    export_path = (storage_service.exports_dir / clean_name).resolve()
    storage_service.validate_safe_path(export_path)

    if not export_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exported file not found.",
        )

    ext = export_path.suffix.lstrip(".")
    media_type = get_media_type_for_format(ext)

    return FileResponse(
        path=str(export_path),
        media_type=media_type,
        filename=clean_name,
    )


# --- Hollow, Duplicate, Delete, and Arrange Endpoints ---


@router.post(
    "/projects/{project_id}/models/{model_id}/hollow",
    response_model=HollowModelResult,
    summary="Hollow 3D model shell with drain holes",
)
@router.post(
    "/models/{model_id}/hollow",
    response_model=HollowModelResult,
    summary="Hollow 3D model shell direct",
)
async def hollow_model(
    model_id: str,
    payload: Optional[HollowModelPayload] = None,
    project_id: Optional[str] = None,
    project_repo: ProjectRepository = Depends(get_project_repo),
) -> HollowModelResult:
    """
    Hollow out a solid 3D model to reduce weight and save resin/filament.
    Creates an inward-offset inner shell with configurable wall thickness and punches bottom drain holes.
    """
    if project_id:
        model = await project_repo.get_working_model_for_project(project_id, model_id)
    else:
        model = await project_repo.get_working_model(model_id)

    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model '{model_id}' not found",
        )

    resolved_path = storage_service.resolve_path(model.storage_path)
    mesh = mesh_service.load_mesh(resolved_path)

    opts = payload or HollowModelPayload()
    hollowed_mesh, volume_saved, drain_holes_count = mesh_service.hollow_mesh(
        mesh=mesh,
        wall_thickness_mm=opts.wall_thickness_mm,
        add_drain_holes=opts.add_drain_holes,
        drain_hole_radius_mm=opts.drain_hole_radius_mm,
        drain_hole_count=opts.drain_hole_count,
    )

    analysis = mesh_service.analyze_mesh(hollowed_mesh)

    hollow_filename = f"hollow_{model.filename}"
    file_uuid = uuid.uuid4().hex[:12]
    new_working_filename = f"{file_uuid}_{storage_service.sanitize_filename(hollow_filename)}"
    new_working_path = (storage_service.working_dir / new_working_filename).resolve()
    storage_service.validate_safe_path(new_working_path)

    mesh_service.export_mesh(hollowed_mesh, new_working_path, format=model.file_format)
    relative_storage_path = f"working/{new_working_filename}"

    updated_model = await project_repo.update_working_model(
        model_id=model_id,
        storage_path=relative_storage_path,
        bounds=analysis.bounds,
        triangle_count=analysis.triangle_count,
        vertex_count=analysis.vertex_count,
        surface_area_cm2=analysis.surface_area_cm2,
        volume_cm3=analysis.volume_cm3,
        is_watertight=analysis.is_watertight,
        transform=model.transform,
    )

    if not updated_model:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update hollowed model in database.",
        )

    await project_repo.record_operation(
        project_id=model.project_id,
        model_id=model_id,
        operation_type="HOLLOW",
        parameters=opts.model_dump(),
        user_summary=f"Hollowed model with {opts.wall_thickness_mm}mm wall thickness and {drain_holes_count} drain holes",
        resulting_state_ref=model_id,
        success=True,
    )

    return HollowModelResult(
        hollowed_model=updated_model,
        wall_thickness_mm=opts.wall_thickness_mm,
        drain_holes_added=drain_holes_count,
        volume_saved_cm3=volume_saved,
        message=f"Model successfully hollowed with {opts.wall_thickness_mm}mm wall thickness",
    )


@router.post(
    "/projects/{project_id}/models/{model_id}/duplicate",
    response_model=WorkingModel,
    status_code=status.HTTP_201_CREATED,
    summary="Duplicate working model in project",
)
@router.post(
    "/models/{model_id}/duplicate",
    response_model=WorkingModel,
    status_code=status.HTTP_201_CREATED,
    summary="Duplicate working model direct",
)
async def duplicate_model(
    model_id: str,
    project_id: Optional[str] = None,
    project_repo: ProjectRepository = Depends(get_project_repo),
) -> WorkingModel:
    """
    Duplicate an existing working model in the project with an offset transform position.
    """
    if project_id:
        model = await project_repo.get_working_model_for_project(project_id, model_id)
    else:
        model = await project_repo.get_working_model(model_id)

    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model '{model_id}' not found",
        )

    resolved_path = storage_service.resolve_path(model.storage_path)
    file_bytes = resolved_path.read_bytes()

    stem = Path(model.filename).stem
    ext = model.file_format.lower().lstrip(".")
    dup_filename = f"{stem}_copy.{ext}"

    dup_working_path, dup_rel_path = storage_service.save_working(
        file_bytes=file_bytes,
        filename=dup_filename,
    )

    from app.models.project import MeshTransform
    orig_pos = model.transform.position_mm
    new_transform = MeshTransform(
        position_mm=[orig_pos[0] + 20.0, orig_pos[1] + 20.0, orig_pos[2]],
        rotation_deg=model.transform.rotation_deg,
        scale_factors=model.transform.scale_factors,
        uniform_scale_percent=model.transform.uniform_scale_percent,
    )

    new_model = await project_repo.add_working_model(
        project_id=model.project_id,
        source_file_id=model.source_file_id,
        filename=dup_filename,
        file_format=ext,
        storage_path=dup_rel_path,
        bounds=model.bounds,
        triangle_count=model.triangle_count,
        vertex_count=model.vertex_count,
        surface_area_cm2=model.surface_area_cm2,
        volume_cm3=model.volume_cm3,
        is_watertight=model.is_watertight,
        transform=new_transform,
    )

    await project_repo.record_operation(
        project_id=model.project_id,
        model_id=new_model.id,
        operation_type="DUPLICATE",
        parameters={"source_model_id": model_id},
        user_summary=f"Duplicated model '{model.filename}' as '{dup_filename}'",
        resulting_state_ref=new_model.id,
        success=True,
    )

    return new_model


@router.delete(
    "/projects/{project_id}/models/{model_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete working model from project",
)
@router.delete(
    "/models/{model_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete working model direct",
)
async def delete_model(
    model_id: str,
    project_id: Optional[str] = None,
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    """
    Remove a working model from the project.
    """
    if project_id:
        model = await project_repo.get_working_model_for_project(project_id, model_id)
    else:
        model = await project_repo.get_working_model(model_id)

    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model '{model_id}' not found",
        )

    deleted = await project_repo.delete_working_model(model_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete working model from database.",
        )

    await project_repo.record_operation(
        project_id=model.project_id,
        model_id=model_id,
        operation_type="DELETE",
        parameters={"deleted_model_id": model_id, "filename": model.filename},
        user_summary=f"Deleted working model '{model.filename}' from project",
        resulting_state_ref=None,
        success=True,
    )

    return {"message": f"Model '{model.filename}' successfully deleted", "model_id": model_id}


@router.post(
    "/projects/{project_id}/arrange",
    response_model=ArrangeProjectResult,
    summary="Auto-arrange all working models collision-free on the build plate",
)
async def arrange_project_models(
    project_id: str,
    payload: Optional[ArrangeProjectPayload] = None,
    project_repo: ProjectRepository = Depends(get_project_repo),
    printer_repo: PrinterRepository = Depends(get_printer_repo),
) -> ArrangeProjectResult:
    """
    Auto-arrange all 3D models in a project across the print bed with collision prevention.
    Updates each model's position in SQLite and records an ARRANGE operation.
    """
    project = await project_repo.get_by_id(project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID '{project_id}' not found",
        )

    if not project.working_models:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project has no 3D models to arrange.",
        )

    opts = payload or ArrangeProjectPayload()
    target_printer_id = opts.printer_id or project.selected_printer_id
    bed_w = 220.0
    bed_d = 220.0
    if target_printer_id:
        printer = await printer_repo.get_by_id(target_printer_id)
        if printer:
            bed_w = float(printer.build_width_mm)
            bed_d = float(printer.build_depth_mm)

    models_data = []
    for wm in project.working_models:
        models_data.append({
            "model_id": wm.id,
            "filename": wm.filename,
            "bounds_dimensions": wm.bounds.dimensions_mm,
        })

    placements_raw, all_fit = mesh_service.arrange_models_on_bed(
        models_data=models_data,
        bed_width_mm=bed_w,
        bed_depth_mm=bed_d,
        spacing_mm=opts.spacing_mm,
        bed_margin_mm=opts.bed_margin_mm,
    )

    placements = []
    for p in placements_raw:
        mid = p["model_id"]
        pos = p["position_mm"]
        rot = p.get("rotation_deg", [0.0, 0.0, 0.0])

        wm = next((m for m in project.working_models if m.id == mid), None)
        if wm:
            from app.models.project import MeshTransform
            updated_transform = MeshTransform(
                position_mm=pos,
                rotation_deg=wm.transform.rotation_deg,
                scale_factors=wm.transform.scale_factors,
                uniform_scale_percent=wm.transform.uniform_scale_percent,
            )
            await project_repo.update_working_model(
                model_id=mid,
                transform=updated_transform,
            )

        placements.append(ArrangeItemPlacement(
            model_id=mid,
            filename=p["filename"],
            position_mm=pos,
            rotation_deg=rot,
        ))

    await project_repo.record_operation(
        project_id=project_id,
        operation_type="ARRANGE",
        parameters={"spacing_mm": opts.spacing_mm, "bed_margin_mm": opts.bed_margin_mm, "printer_id": target_printer_id},
        user_summary=f"Auto-arranged {len(placements)} models on {bed_w}x{bed_d}mm build plate (All fit: {all_fit})",
        resulting_state_ref=project_id,
        success=True,
    )

    return ArrangeProjectResult(
        project_id=project_id,
        models_arranged=len(placements),
        placements=placements,
        all_fit=all_fit,
        message=f"Successfully arranged {len(placements)} models on build bed" if all_fit else "Arranged models on bed with overflow warning",
    )


@router.post(
    "/projects/{project_id}/export_3mf",
    response_model=ExportProject3MFResponse,
    summary="Export all project models into a production-ready 3MF package for OrcaSlicer/Bambu Studio",
)
async def export_project_3mf(
    project_id: str,
    payload: Optional[ExportProject3MFPayload] = None,
    project_repo: ProjectRepository = Depends(get_project_repo),
    printer_repo: PrinterRepository = Depends(get_printer_repo),
) -> ExportProject3MFResponse:
    """
    Exports all active models in the project with their transformations (positions, rotations, scales)
    into a standardized 3MF archive containing 3D/3dmodel.model XML and OrcaSlicer Metadata.
    """
    project = await project_repo.get_by_id(project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID '{project_id}' not found",
        )

    if not project.working_models:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project has no 3D models to export.",
        )

    opts = payload or ExportProject3MFPayload()

    printer_name = "Generic 3D Printer"
    if project.selected_printer_id:
        printer = await printer_repo.get_by_id(project.selected_printer_id)
        if printer:
            printer_name = f"{printer.manufacturer} {printer.model}"

    models_data = []
    for wm in project.working_models:
        resolved_path = storage_service.resolve_path(wm.storage_path)
        try:
            m = mesh_service.load_mesh(resolved_path)
            models_data.append({
                "model_id": wm.id,
                "filename": wm.filename,
                "mesh": m,
                "position_mm": wm.transform.position_mm,
                "rotation_deg": wm.transform.rotation_deg,
                "scale_factors": wm.transform.scale_factors,
            })
        except Exception as e:
            continue

    if not models_data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load project meshes for 3MF export.",
        )

    clean_proj_name = storage_service.sanitize_filename(project.name or "project")
    filename = opts.filename or f"{clean_proj_name}.3mf"
    if not filename.lower().endswith(".3mf"):
        filename += ".3mf"

    file_uuid = uuid.uuid4().hex[:12]
    export_filename = f"{file_uuid}_{storage_service.sanitize_filename(filename)}"
    export_path = (storage_service.exports_dir / export_filename).resolve()
    storage_service.validate_safe_path(export_path)

    mesh_service.export_project_3mf(
        models_data=models_data,
        destination=export_path,
        project_name=project.name,
        printer_model=printer_name,
        filament_name=opts.filament_preset or "Generic PLA",
    )

    file_size_bytes = export_path.stat().st_size
    relative_path = f"exports/{export_filename}"
    download_url = f"/api/v1/models/export/download/{export_filename}"

    await project_repo.record_operation(
        project_id=project_id,
        operation_type="EXPORT_3MF",
        parameters={
            "filename": filename,
            "models_count": len(models_data),
            "printer_model": printer_name,
            "filament_preset": opts.filament_preset,
        },
        user_summary=f"Exported project with {len(models_data)} models to 3MF ({filename}, {file_size_bytes / 1024:.1f} KB)",
        resulting_state_ref=export_filename,
        success=True,
    )

    return ExportProject3MFResponse(
        project_id=project_id,
        filename=filename,
        storage_path=relative_path,
        download_url=download_url,
        file_size_bytes=file_size_bytes,
        models_exported=len(models_data),
        message="Successfully generated 3MF production archive for OrcaSlicer & Bambu Studio",
    )
