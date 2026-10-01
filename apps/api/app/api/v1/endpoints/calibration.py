import json
import logging
from typing import List, Optional
import uuid
import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, status
import trimesh

from app.db.database import get_db
from app.models.calibration import (
    AdaptiveLayerPayload,
    AdaptiveLayerResult,
    AutoArrangePayload,
    AutoArrangeResult,
    AutoOrientPayload,
    AutoOrientResult,
    CalibrationGeneratePayload,
    CalibrationGenerateResult,
    CostEstimationPayload,
    CostEstimationResult,
    FilamentProfile,
    MouseEarPayload,
    MouseEarResult,
)
from app.models.project import MeshBounds, MeshTransform, WorkingModel
from app.repositories.printer_repo import PrinterRepository
from app.repositories.project_repo import ProjectRepository
from app.services.adhesion_service import adhesion_service
from app.services.arrangement_service import arrangement_service
from app.services.calibration_service import calibration_service
from app.services.filament_service import filament_service
from app.services.layer_height_service import layer_height_service
from app.services.mesh_service import mesh_service
from app.services.orientation_service import orientation_service
from app.services.storage import storage_service

logger = logging.getLogger("outlaw_forge.api.calibration")

router = APIRouter(tags=["Orca Calibration & CAD Features"])


# --- Calibration Artifact Generator ---

@router.post(
    "/projects/{project_id}/calibration/generate",
    response_model=CalibrationGenerateResult,
    status_code=status.HTTP_201_CREATED,
    summary="Generate procedural 3D calibration artifact model",
)
async def generate_calibration_artifact(
    project_id: str,
    payload: CalibrationGeneratePayload,
    conn: aiosqlite.Connection = Depends(get_db),
) -> CalibrationGenerateResult:
    """
    Generates a procedural calibration test artifact (Temp Tower, Flow Rate, Retraction Tower,
    Tolerance Gauge, Overhang Benchmark, Calibration Cube V2, Max Volumetric Speed) and adds it
    to the active project as a working model.
    """
    project_repo = ProjectRepository(conn)
    project = await project_repo.get_by_id(project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID '{project_id}' not found",
        )

    # 1. Generate 3D procedural mesh
    mesh, suggested_filename, notes = calibration_service.generate(payload)
    if payload.custom_name:
        filename = payload.custom_name if payload.custom_name.endswith(".stl") else f"{payload.custom_name}.stl"
    else:
        filename = suggested_filename

    # Export mesh to STL bytes
    stl_bytes = mesh.export(file_type="stl")
    if isinstance(stl_bytes, str):
        stl_bytes = stl_bytes.encode("utf-8")

    # 2. Save immutable source and working copy
    orig_path, orig_rel_path, sanitized_name, file_size = storage_service.save_original(
        file_bytes=stl_bytes,
        filename=filename,
    )
    working_path, working_rel_path = storage_service.save_working(
        file_bytes=stl_bytes,
        filename=sanitized_name,
    )

    # 3. Analyze geometry
    analysis = mesh_service.analyze_mesh(mesh)

    # 4. Insert into database
    source_file = await project_repo.add_source_file(
        project_id=project_id,
        filename=sanitized_name,
        file_format="stl",
        file_size_bytes=file_size,
        storage_path=str(orig_path),
    )

    working_model = await project_repo.add_working_model(
        project_id=project_id,
        source_file_id=source_file.id,
        filename=sanitized_name,
        file_format="stl",
        storage_path=str(working_path),
        bounds=analysis.bounds,
        triangle_count=analysis.triangle_count,
        vertex_count=analysis.vertex_count,
        surface_area_cm2=analysis.surface_area_cm2,
        volume_cm3=analysis.volume_cm3,
        is_watertight=analysis.is_watertight,
        transform=MeshTransform(
            position_mm=[0.0, 0.0, 0.0],
            rotation_deg=[0.0, 0.0, 0.0],
            scale_factors=[1.0, 1.0, 1.0],
            uniform_scale_percent=100.0,
        ),
    )

    await project_repo.record_operation(
        project_id=project_id,
        model_id=working_model.id,
        operation_type="CALIBRATION_GENERATE",
        parameters=payload.model_dump(),
        resulting_state_ref=str(working_path),
        user_summary=f"Generated {payload.calibration_type} calibration artifact: {filename}",
        success=True,
    )

    return CalibrationGenerateResult(
        model=working_model,
        calibration_type=payload.calibration_type,
        suggested_slicer_notes=notes,
        message=f"Generated {payload.calibration_type} artifact successfully.",
    )


# --- Auto-Orient Endpoint ---

@router.post(
    "/projects/{project_id}/models/{model_id}/auto_orient",
    response_model=AutoOrientResult,
    summary="Auto-orient model to minimize overhang support and maximize bed contact",
)
async def auto_orient_model(
    project_id: str,
    model_id: str,
    payload: AutoOrientPayload = AutoOrientPayload(),
    conn: aiosqlite.Connection = Depends(get_db),
) -> AutoOrientResult:
    """
    Evaluates multi-axis candidate orientations against overhang support requirements,
    total Z height, and bed contact surface area to find the optimal FDM print angle.
    """
    project_repo = ProjectRepository(conn)
    model = await project_repo.get_working_model(model_id)
    if not model or model.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model with ID '{model_id}' not found in project '{project_id}'",
        )

    resolved_path = storage_service.resolve_path(model.storage_path)
    mesh = mesh_service.load_mesh(resolved_path)
    (
        oriented_mesh,
        optimal_rot_deg,
        orig_overhang_cm2,
        opt_overhang_cm2,
        reduction_pct,
    ) = orientation_service.auto_orient(mesh, payload)

    # Export transformed working mesh
    export_fmt = model.file_format if model.file_format in ["stl", "obj", "glb"] else "stl"
    mesh_bytes = oriented_mesh.export(file_type=export_fmt)
    if isinstance(mesh_bytes, str):
        mesh_bytes = mesh_bytes.encode("utf-8")
    working_path, working_rel_path = storage_service.save_working(mesh_bytes, model.filename)

    analysis = mesh_service.analyze_mesh(oriented_mesh)
    new_transform = model.transform.model_copy()
    new_transform.rotation_deg = optimal_rot_deg
    new_transform.position_mm = [0.0, 0.0, 0.0]

    updated_model = await project_repo.update_working_model(
        model_id=model_id,
        storage_path=str(working_path),
        bounds=analysis.bounds,
        triangle_count=analysis.triangle_count,
        vertex_count=analysis.vertex_count,
        surface_area_cm2=analysis.surface_area_cm2,
        volume_cm3=analysis.volume_cm3,
        is_watertight=analysis.is_watertight,
        transform=new_transform,
    )

    await project_repo.record_operation(
        project_id=project_id,
        model_id=model_id,
        operation_type="AUTO_ORIENT",
        parameters=payload.model_dump(),
        resulting_state_ref=str(working_path),
        user_summary=(
            f"Auto-oriented model '{model.filename}' (Overhang reduced by {reduction_pct:.1f}%: "
            f"{orig_overhang_cm2:.2f} -> {opt_overhang_cm2:.2f} cm²)"
        ),
        success=True,
    )

    return AutoOrientResult(
        oriented_model=updated_model or model,
        optimal_rotation_deg=optimal_rot_deg,
        original_overhang_area_cm2=round(orig_overhang_cm2, 2),
        optimized_overhang_area_cm2=round(opt_overhang_cm2, 2),
        reduction_percentage=round(reduction_pct, 1),
        message=f"Optimal orientation applied (Overhang support reduced by {reduction_pct:.1f}%).",
    )


# --- Auto-Arrange Endpoint ---

@router.post(
    "/projects/{project_id}/auto_arrange",
    response_model=AutoArrangeResult,
    summary="Auto-arrange multiple models on build plate with optimal nesting",
)
async def auto_arrange_models(
    project_id: str,
    payload: AutoArrangePayload = AutoArrangePayload(),
    conn: aiosqlite.Connection = Depends(get_db),
) -> AutoArrangeResult:
    """
    Arranges multiple models onto the build plate using 2D nesting with configurable spacing.
    """
    project_repo = ProjectRepository(conn)
    printer_repo = PrinterRepository(conn)

    project = await project_repo.get_by_id(project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID '{project_id}' not found",
        )

    if not project.working_models:
        return AutoArrangeResult(
            arranged_models=[],
            placements=[],
            fits_bed=True,
            message="No models to arrange on the build plate.",
        )

    # Determine bed bounds
    bed_w = payload.bed_width_mm or 256.0
    bed_d = payload.bed_depth_mm or 256.0
    if project.selected_printer_id:
        printer = await printer_repo.get_by_id(project.selected_printer_id)
        if printer:
            bed_w = printer.build_width_mm
            bed_d = printer.build_depth_mm

    # Load all meshes
    models_data = []
    for wm in project.working_models:
        try:
            resolved_path = storage_service.resolve_path(wm.storage_path)
            m = mesh_service.load_mesh(resolved_path)
            models_data.append((wm, m))
        except Exception as e:
            logger.warning(f"Could not load mesh for {wm.id}: {e}")

    # Compute arrangement
    updated_models_with_meshes, placements, fits_bed, message = arrangement_service.arrange(
        models_data,
        payload,
        printer_bounds=(bed_w, bed_d, 250.0),
    )

    # Persist updated positions to database
    final_arranged_models: List[WorkingModel] = []
    for wm, mesh in updated_models_with_meshes:
        export_fmt = wm.file_format if wm.file_format in ["stl", "obj", "glb"] else "stl"
        mesh_bytes = mesh.export(file_type=export_fmt)
        if isinstance(mesh_bytes, str):
            mesh_bytes = mesh_bytes.encode("utf-8")
        working_path, working_rel_path = storage_service.save_working(mesh_bytes, wm.filename)
        analysis = mesh_service.analyze_mesh(mesh)

        updated_wm = await project_repo.update_working_model(
            model_id=wm.id,
            storage_path=str(working_path),
            bounds=analysis.bounds,
            triangle_count=analysis.triangle_count,
            vertex_count=analysis.vertex_count,
            surface_area_cm2=analysis.surface_area_cm2,
            volume_cm3=analysis.volume_cm3,
            is_watertight=analysis.is_watertight,
            transform=wm.transform,
        )
        if updated_wm:
            final_arranged_models.append(updated_wm)

    await project_repo.record_operation(
        project_id=project_id,
        operation_type="AUTO_ARRANGE",
        parameters=payload.model_dump(),
        user_summary=f"Auto-arranged {len(final_arranged_models)} models with {payload.spacing_mm}mm spacing",
        resulting_state_ref="",
        success=True,
    )


    return AutoArrangeResult(
        arranged_models=final_arranged_models,
        placements=placements,
        fits_bed=fits_bed,
        message=message,
    )


# --- Mouse-Ear Anti-Warping Brim Endpoint ---

@router.post(
    "/projects/{project_id}/models/{model_id}/mouse_ears",
    response_model=MouseEarResult,
    summary="Generate mouse-ear anti-warping brim discs at sharp corners",
)
async def generate_mouse_ears(
    project_id: str,
    model_id: str,
    payload: MouseEarPayload = MouseEarPayload(),
    conn: aiosqlite.Connection = Depends(get_db),
) -> MouseEarResult:
    """
    Detects high-stress exterior corners on the model's first layer and attaches procedural
    low-profile circular adhesion discs (mouse ears) to prevent lifting/warping.
    """
    project_repo = ProjectRepository(conn)
    model = await project_repo.get_working_model(model_id)
    if not model or model.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model with ID '{model_id}' not found in project '{project_id}'",
        )

    resolved_path = storage_service.resolve_path(model.storage_path)
    mesh = mesh_service.load_mesh(resolved_path)
    (
        modified_mesh,
        ears_count,
        ear_positions,
        message,
    ) = adhesion_service.generate_mouse_ears(mesh, payload)

    # Save modified mesh
    export_fmt = model.file_format if model.file_format in ["stl", "obj", "glb"] else "stl"
    mesh_bytes = modified_mesh.export(file_type=export_fmt)
    if isinstance(mesh_bytes, str):
        mesh_bytes = mesh_bytes.encode("utf-8")
    working_path, working_rel_path = storage_service.save_working(mesh_bytes, model.filename)

    analysis = mesh_service.analyze_mesh(modified_mesh)
    updated_model = await project_repo.update_working_model(
        model_id=model_id,
        storage_path=str(working_path),
        bounds=analysis.bounds,
        triangle_count=analysis.triangle_count,
        vertex_count=analysis.vertex_count,
        surface_area_cm2=analysis.surface_area_cm2,
        volume_cm3=analysis.volume_cm3,
        is_watertight=analysis.is_watertight,
        transform=model.transform,
    )

    await project_repo.record_operation(
        project_id=project_id,
        model_id=model_id,
        operation_type="MOUSE_EAR_BRIM",
        parameters=payload.model_dump(),
        resulting_state_ref=str(working_path),
        user_summary=f"Added {ears_count} anti-warping mouse-ear discs (Radius {payload.radius_mm}mm) to '{model.filename}'",
        success=True,
    )

    return MouseEarResult(
        modified_model=updated_model or model,
        ears_added_count=ears_count,
        ear_positions_mm=ear_positions,
        message=message,
    )


# --- Adaptive Layer Height Endpoint ---

@router.post(
    "/projects/{project_id}/models/{model_id}/adaptive_layers",
    response_model=AdaptiveLayerResult,
    summary="Compute adaptive variable layer height profile for model",
)
async def compute_adaptive_layers(
    project_id: str,
    model_id: str,
    payload: AdaptiveLayerPayload = AdaptiveLayerPayload(),
    conn: aiosqlite.Connection = Depends(get_db),
) -> AdaptiveLayerResult:
    """
    Analyzes mesh curvature per Z-height to generate an adaptive variable layer height profile,
    providing high surface resolution on curves and fast printing on vertical walls.
    """
    project_repo = ProjectRepository(conn)
    model = await project_repo.get_working_model(model_id)
    if not model or model.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model with ID '{model_id}' not found in project '{project_id}'",
        )

    resolved_path = storage_service.resolve_path(model.storage_path)
    mesh = mesh_service.load_mesh(resolved_path)
    result = layer_height_service.compute_adaptive_profile(mesh, model_id, payload)

    await project_repo.record_operation(
        project_id=project_id,
        model_id=model_id,
        operation_type="ADAPTIVE_LAYERS",
        parameters=payload.model_dump(),
        resulting_state_ref="",
        user_summary=(
            f"Computed adaptive layer profile for '{model.filename}': {result.total_layers_adaptive} "
            f"layers ({result.time_savings_pct:.1f}% time savings)"
        ),
        success=True,
    )

    return result


# --- Filament Library & Cost Estimator Endpoints ---

@router.get(
    "/projects/{project_id}/filaments",
    response_model=List[FilamentProfile],
    summary="List available 3D printing filament profiles and spool prices",
)
async def list_filament_profiles(project_id: str) -> List[FilamentProfile]:
    """
    Returns preset and custom filament materials (PLA, PETG, ABS, TPU, PA-CF, PC, etc.) with densities & costs.
    """
    return filament_service.list_filaments()


@router.post(
    "/projects/{project_id}/models/{model_id}/estimate_cost",
    response_model=CostEstimationResult,
    summary="Estimate filament mass, length, and print material cost for model",
)
async def estimate_model_cost(
    project_id: str,
    model_id: str,
    payload: CostEstimationPayload = CostEstimationPayload(),
    conn: aiosqlite.Connection = Depends(get_db),
) -> CostEstimationResult:
    """
    Estimates total required filament weight in grams, length in meters, and financial cost
    based on selected material density, infill percentage, and per-kg spool price.
    """
    project_repo = ProjectRepository(conn)
    model = await project_repo.get_working_model(model_id)
    if not model or model.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model with ID '{model_id}' not found in project '{project_id}'",
        )

    resolved_path = storage_service.resolve_path(model.storage_path)
    mesh = mesh_service.load_mesh(resolved_path)
    return filament_service.estimate_cost(mesh, model_id, payload)
