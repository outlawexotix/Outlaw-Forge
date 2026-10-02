import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
import aiosqlite

from app.db.database import get_db
from app.models.project import WorkingModel
from app.models.studios import (
    CenterOfMassAnalysis,
    KeyPegPayload,
    KeyPegResult,
    MagnetSocketPunchPayload,
    MagnetSocketPunchResult,
    MaskFitAnalysis,
    MaskFitScalePayload,
    PlinthGeneratePayload,
    PlinthGenerateResult,
    StrapSlotPunchPayload,
    StrapSlotPunchResult,
)
from app.repositories.project_repo import ProjectRepository
from app.services.figureforge_service import figureforge_service
from app.services.masksmith_service import masksmith_service
from app.services.mesh_service import mesh_service
from app.services.storage import storage_service

router = APIRouter()


def get_project_repo(conn: aiosqlite.Connection = Depends(get_db)) -> ProjectRepository:
    return ProjectRepository(conn)


# ============================================================================
# MASKSMITH STUDIO ENDPOINTS
# ============================================================================

@router.post(
    "/projects/{project_id}/models/{model_id}/masksmith/fit-analyze",
    response_model=MaskFitAnalysis,
    summary="Analyze mask dimensions and calculate anthropometric wearable sizing",
)
async def analyze_mask_fit(
    project_id: str,
    model_id: str,
    project_repo: ProjectRepository = Depends(get_project_repo),
) -> MaskFitAnalysis:
    model = await project_repo.get_working_model_for_project(project_id, model_id)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model '{model_id}' not found in project '{project_id}'",
        )

    resolved_path = storage_service.resolve_path(model.storage_path)
    mesh = mesh_service.load_mesh(resolved_path)

    analysis = masksmith_service.analyze_mask_fit(mesh, model_id=model_id)
    return analysis


@router.post(
    "/projects/{project_id}/models/{model_id}/masksmith/auto-scale",
    response_model=WorkingModel,
    summary="Auto-scale mask to fit target anthropometric head profile",
)
async def auto_scale_mask(
    project_id: str,
    model_id: str,
    payload: MaskFitScalePayload,
    project_repo: ProjectRepository = Depends(get_project_repo),
) -> WorkingModel:
    model = await project_repo.get_working_model_for_project(project_id, model_id)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model '{model_id}' not found in project '{project_id}'",
        )

    resolved_path = storage_service.resolve_path(model.storage_path)
    mesh = mesh_service.load_mesh(resolved_path)

    scaled_mesh, scale_factor = masksmith_service.scale_mask_fit(
        mesh=mesh,
        target_preset=payload.target_preset,
        custom_inner_width_mm=payload.target_inner_width_mm,
        padding_clearance_mm=payload.padding_clearance_mm,
        uniform=payload.uniform_scale,
    )

    analysis = mesh_service.analyze_mesh(scaled_mesh)

    file_uuid = uuid.uuid4().hex[:12]
    new_filename = f"{file_uuid}_maskfit_{storage_service.sanitize_filename(model.filename)}"
    new_path = (storage_service.working_dir / new_filename).resolve()
    storage_service.validate_safe_path(new_path)

    mesh_service.export_mesh(scaled_mesh, new_path, format=model.file_format)
    rel_path = f"working/{new_filename}"

    from app.models.project import MeshTransform
    new_transform = MeshTransform(
        position_mm=model.transform.position_mm,
        rotation_deg=model.transform.rotation_deg,
        scale_factors=[
            round(model.transform.scale_factors[0] * scale_factor, 4),
            round(model.transform.scale_factors[1] * scale_factor, 4),
            round(model.transform.scale_factors[2] * scale_factor, 4),
        ],
        uniform_scale_percent=round(model.transform.uniform_scale_percent * scale_factor, 2),
    )

    updated_model = await project_repo.update_working_model(
        model_id=model_id,
        storage_path=rel_path,
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
        operation_type="MASK_FIT_SCALE",
        parameters={"preset": payload.target_preset, "scale_factor": scale_factor, "padding_mm": payload.padding_clearance_mm},
        user_summary=f"MaskSmith: Scaled mask to {payload.target_preset} (Scale: {scale_factor:.3f}x, Width: {analysis.bounds.dimensions_mm[0]:.1f}mm)",
        resulting_state_ref=model_id,
        success=True,
    )

    return updated_model


@router.post(
    "/projects/{project_id}/models/{model_id}/masksmith/punch-magnets",
    response_model=MagnetSocketPunchResult,
    summary="Punch neodymium magnet sockets around mask perimeter",
)
async def punch_magnet_sockets(
    project_id: str,
    model_id: str,
    payload: MagnetSocketPunchPayload,
    project_repo: ProjectRepository = Depends(get_project_repo),
) -> MagnetSocketPunchResult:
    model = await project_repo.get_working_model_for_project(project_id, model_id)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model '{model_id}' not found in project '{project_id}'",
        )

    resolved_path = storage_service.resolve_path(model.storage_path)
    mesh = mesh_service.load_mesh(resolved_path)

    punched_mesh, positions, dia, depth = masksmith_service.punch_magnet_sockets(
        mesh=mesh,
        magnet_preset=payload.magnet_preset,
        custom_diameter_mm=payload.custom_diameter_mm,
        custom_depth_mm=payload.custom_depth_mm,
        clearance_tolerance_mm=payload.clearance_tolerance_mm,
        placement_mode=payload.placement_mode,
        margin_inset_mm=payload.margin_inset_mm,
        custom_points=payload.custom_points,
    )

    analysis = mesh_service.analyze_mesh(punched_mesh)

    file_uuid = uuid.uuid4().hex[:12]
    new_filename = f"{file_uuid}_magnets_{storage_service.sanitize_filename(model.filename)}"
    new_path = (storage_service.working_dir / new_filename).resolve()
    storage_service.validate_safe_path(new_path)

    mesh_service.export_mesh(punched_mesh, new_path, format=model.file_format)
    rel_path = f"working/{new_filename}"

    updated_model = await project_repo.update_working_model(
        model_id=model_id,
        storage_path=rel_path,
        bounds=analysis.bounds,
        triangle_count=analysis.triangle_count,
        vertex_count=analysis.vertex_count,
        surface_area_cm2=analysis.surface_area_cm2,
        volume_cm3=analysis.volume_cm3,
        is_watertight=analysis.is_watertight,
    )

    await project_repo.record_operation(
        project_id=project_id,
        model_id=model_id,
        operation_type="MASK_MAGNET_PUNCH",
        parameters={"preset": payload.magnet_preset, "sockets_count": len(positions), "diameter_mm": dia, "depth_mm": depth},
        user_summary=f"MaskSmith: Punched {len(positions)} magnet sockets ({dia}x{depth}mm, {payload.placement_mode})",
        resulting_state_ref=model_id,
        success=True,
    )

    return MagnetSocketPunchResult(
        model=updated_model,
        sockets_punched=len(positions),
        magnet_diameter_mm=dia,
        magnet_depth_mm=depth,
        socket_positions=positions,
        message=f"Successfully punched {len(positions)} neodymium magnet sockets ({dia}x{depth}mm)",
    )


@router.post(
    "/projects/{project_id}/models/{model_id}/masksmith/punch-strap-slots",
    response_model=StrapSlotPunchResult,
    summary="Punch webbing strap slots and harness loops",
)
async def punch_strap_slots(
    project_id: str,
    model_id: str,
    payload: StrapSlotPunchPayload,
    project_repo: ProjectRepository = Depends(get_project_repo),
) -> StrapSlotPunchResult:
    model = await project_repo.get_working_model_for_project(project_id, model_id)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model '{model_id}' not found in project '{project_id}'",
        )

    resolved_path = storage_service.resolve_path(model.storage_path)
    mesh = mesh_service.load_mesh(resolved_path)

    punched_mesh, positions, sw, st = masksmith_service.punch_strap_slots(
        mesh=mesh,
        strap_preset=payload.strap_preset,
        slot_width_mm=payload.slot_width_mm,
        slot_thickness_mm=payload.slot_thickness_mm,
        placement=payload.placement,
        inset_from_edge_mm=payload.inset_from_edge_mm,
        custom_positions=payload.custom_positions,
    )

    analysis = mesh_service.analyze_mesh(punched_mesh)

    file_uuid = uuid.uuid4().hex[:12]
    new_filename = f"{file_uuid}_straps_{storage_service.sanitize_filename(model.filename)}"
    new_path = (storage_service.working_dir / new_filename).resolve()
    storage_service.validate_safe_path(new_path)

    mesh_service.export_mesh(punched_mesh, new_path, format=model.file_format)
    rel_path = f"working/{new_filename}"

    updated_model = await project_repo.update_working_model(
        model_id=model_id,
        storage_path=rel_path,
        bounds=analysis.bounds,
        triangle_count=analysis.triangle_count,
        vertex_count=analysis.vertex_count,
        surface_area_cm2=analysis.surface_area_cm2,
        volume_cm3=analysis.volume_cm3,
        is_watertight=analysis.is_watertight,
    )

    await project_repo.record_operation(
        project_id=project_id,
        model_id=model_id,
        operation_type="MASK_STRAP_SLOT",
        parameters={"preset": payload.strap_preset, "slots_count": len(positions), "slot_width_mm": sw, "slot_thickness_mm": st},
        user_summary=f"MaskSmith: Punched {len(positions)} strap slots ({sw}x{st}mm for {payload.strap_preset})",
        resulting_state_ref=model_id,
        success=True,
    )

    return StrapSlotPunchResult(
        model=updated_model,
        slots_punched=len(positions),
        slot_width_mm=sw,
        slot_thickness_mm=st,
        slot_positions=positions,
        message=f"Successfully punched {len(positions)} strap slots ({sw}x{st}mm)",
    )


# ============================================================================
# FIGUREFORGE STUDIO ENDPOINTS
# ============================================================================

@router.post(
    "/projects/{project_id}/models/{model_id}/figureforge/com-analyze",
    response_model=CenterOfMassAnalysis,
    summary="Analyze center of mass, ground projection, and tipping stability",
)
async def analyze_figure_com(
    project_id: str,
    model_id: str,
    project_repo: ProjectRepository = Depends(get_project_repo),
) -> CenterOfMassAnalysis:
    model = await project_repo.get_working_model_for_project(project_id, model_id)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model '{model_id}' not found in project '{project_id}'",
        )

    resolved_path = storage_service.resolve_path(model.storage_path)
    mesh = mesh_service.load_mesh(resolved_path)

    analysis = figureforge_service.analyze_center_of_mass(mesh, model_id=model_id)
    return analysis


@router.post(
    "/projects/{project_id}/models/{model_id}/figureforge/generate-plinth",
    response_model=PlinthGenerateResult,
    summary="Generate custom display plinth base paired with figure",
)
async def generate_figure_plinth(
    project_id: str,
    model_id: str,
    payload: PlinthGeneratePayload,
    project_repo: ProjectRepository = Depends(get_project_repo),
) -> PlinthGenerateResult:
    project = await project_repo.get_by_id(project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{project_id}' not found",
        )

    model = await project_repo.get_working_model_for_project(project_id, model_id)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model '{model_id}' not found in project '{project_id}'",
        )

    plinth_mesh = figureforge_service.generate_plinth(
        shape=payload.shape,
        diameter_mm=payload.diameter_mm,
        height_mm=payload.height_mm,
        chamfer_height_mm=payload.chamfer_height_mm,
        add_nameplate_recess=payload.add_nameplate_recess,
        add_figure_sockets=payload.add_figure_sockets,
        socket_diameter_mm=payload.socket_diameter_mm,
        socket_depth_mm=payload.socket_depth_mm,
        socket_spacing_mm=payload.socket_spacing_mm,
    )

    analysis = mesh_service.analyze_mesh(plinth_mesh)

    file_uuid = uuid.uuid4().hex[:12]
    plinth_filename = f"plinth_{payload.shape}_{payload.diameter_mm:.0f}mm.stl"
    new_storage_filename = f"{file_uuid}_{storage_service.sanitize_filename(plinth_filename)}"
    new_path = (storage_service.working_dir / new_storage_filename).resolve()
    storage_service.validate_safe_path(new_path)

    mesh_service.export_mesh(plinth_mesh, new_path, format="stl")
    rel_path = f"working/{new_storage_filename}"

    from app.models.project import MeshTransform
    plinth_wm = await project_repo.add_working_model(
        project_id=project_id,
        source_file_id=model.source_file_id,
        filename=plinth_filename,
        file_format="stl",
        storage_path=rel_path,
        bounds=analysis.bounds,
        triangle_count=analysis.triangle_count,
        vertex_count=analysis.vertex_count,
        surface_area_cm2=analysis.surface_area_cm2,
        volume_cm3=analysis.volume_cm3,
        is_watertight=analysis.is_watertight,
        transform=MeshTransform(position_mm=[0.0, 0.0, 0.0]),
    )

    await project_repo.record_operation(
        project_id=project_id,
        model_id=plinth_wm.id,
        operation_type="FIGURE_PLINTH_GENERATE",
        parameters={"shape": payload.shape, "diameter_mm": payload.diameter_mm, "height_mm": payload.height_mm},
        user_summary=f"FigureForge: Generated {payload.shape} display plinth (Ø{payload.diameter_mm}mm x {payload.height_mm}mm)",
        resulting_state_ref=plinth_wm.id,
        success=True,
    )

    return PlinthGenerateResult(
        plinth_model=plinth_wm,
        shape=payload.shape,
        diameter_mm=payload.diameter_mm,
        height_mm=payload.height_mm,
        has_sockets=payload.add_figure_sockets,
        message=f"Generated {payload.shape} display plinth (Ø{payload.diameter_mm}mm)",
    )


@router.post(
    "/projects/{project_id}/models/{model_id}/figureforge/create-key-pegs",
    response_model=KeyPegResult,
    summary="Add downward key-pegs to figure feet for plinth mounting",
)
async def create_figure_key_pegs(
    project_id: str,
    model_id: str,
    payload: KeyPegPayload,
    project_repo: ProjectRepository = Depends(get_project_repo),
) -> KeyPegResult:
    model = await project_repo.get_working_model_for_project(project_id, model_id)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model '{model_id}' not found in project '{project_id}'",
        )

    resolved_path = storage_service.resolve_path(model.storage_path)
    mesh = mesh_service.load_mesh(resolved_path)

    pegged_mesh, positions, dia, length = figureforge_service.create_key_pegs(
        mesh=mesh,
        peg_shape=payload.peg_shape,
        peg_diameter_mm=payload.peg_diameter_mm,
        peg_length_mm=payload.peg_length_mm,
        foot_offset_mm=payload.foot_offset_mm,
        dual_feet_pegs=payload.dual_feet_pegs,
    )

    analysis = mesh_service.analyze_mesh(pegged_mesh)

    file_uuid = uuid.uuid4().hex[:12]
    new_filename = f"{file_uuid}_pegs_{storage_service.sanitize_filename(model.filename)}"
    new_path = (storage_service.working_dir / new_filename).resolve()
    storage_service.validate_safe_path(new_path)

    mesh_service.export_mesh(pegged_mesh, new_path, format=model.file_format)
    rel_path = f"working/{new_filename}"

    updated_model = await project_repo.update_working_model(
        model_id=model_id,
        storage_path=rel_path,
        bounds=analysis.bounds,
        triangle_count=analysis.triangle_count,
        vertex_count=analysis.vertex_count,
        surface_area_cm2=analysis.surface_area_cm2,
        volume_cm3=analysis.volume_cm3,
        is_watertight=analysis.is_watertight,
    )

    await project_repo.record_operation(
        project_id=project_id,
        model_id=model_id,
        operation_type="FIGURE_KEY_PEG",
        parameters={"peg_shape": payload.peg_shape, "pegs_count": len(positions), "diameter_mm": dia, "length_mm": length},
        user_summary=f"FigureForge: Added {len(positions)} mounting key-pegs (Ø{dia}mm x {length}mm)",
        resulting_state_ref=model_id,
        success=True,
    )

    return KeyPegResult(
        model_with_pegs=updated_model,
        pegs_added_count=len(positions),
        peg_diameter_mm=dia,
        peg_length_mm=length,
        peg_positions=positions,
        message=f"Added {len(positions)} mounting key-pegs (Ø{dia}mm x {length}mm)",
    )
