from typing import Any, Dict, List, Literal, Optional, Tuple, Union
from pydantic import BaseModel, ConfigDict, Field

from app.models.project import MeshBounds, MeshTransform, WorkingModel


class MeshAnalysisResult(BaseModel):
    bounds: MeshBounds
    triangle_count: int
    vertex_count: int
    surface_area_cm2: float
    volume_cm3: Optional[float] = None
    is_watertight: bool

    model_config = ConfigDict(from_attributes=True)
class ScaleModelPayload(BaseModel):
    uniform_scale_percent: Optional[float] = Field(
        default=None, description="Uniform scaling factor percentage (e.g. 200 = 200%)"
    )
    target_height_mm: Optional[float] = Field(
        default=None, description="Target Z dimension in mm"
    )
    target_width_mm: Optional[float] = Field(
        default=None, description="Target X dimension in mm"
    )
    target_depth_mm: Optional[float] = Field(
        default=None, description="Target Y dimension in mm"
    )
    preserve_aspect_ratio: bool = Field(
        default=True, description="Lock aspect ratio across all axes when scaling to a target dimension"
    )


class ExportModelPayload(BaseModel):
    format: Literal["stl", "obj", "glb", "3mf"] = Field(
        default="stl", description="Target export 3D format"
    )
    filename: Optional[str] = Field(
        default=None, description="Optional custom export filename"
    )


class ExportModelResponse(BaseModel):
    download_url: str
    filename: str


class ExportResult(BaseModel):
    export_path: str
    filename: str
    format: str
    file_size_bytes: int

    model_config = ConfigDict(from_attributes=True)


class RotateModelPayload(BaseModel):
    rx_deg: Optional[float] = Field(default=0.0, description="Rotation around X axis in degrees")
    ry_deg: Optional[float] = Field(default=0.0, description="Rotation around Y axis in degrees")
    rz_deg: Optional[float] = Field(default=0.0, description="Rotation around Z axis in degrees")
    rx: Optional[float] = None
    ry: Optional[float] = None
    rz: Optional[float] = None
    x_deg: Optional[float] = None
    y_deg: Optional[float] = None
    z_deg: Optional[float] = None

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    @property
    def x(self) -> float:
        if self.rx_deg is not None and self.rx_deg != 0.0:
            return float(self.rx_deg)
        if self.rx is not None:
            return float(self.rx)
        if self.x_deg is not None:
            return float(self.x_deg)
        return float(self.rx_deg or 0.0)

    @property
    def y(self) -> float:
        if self.ry_deg is not None and self.ry_deg != 0.0:
            return float(self.ry_deg)
        if self.ry is not None:
            return float(self.ry)
        if self.y_deg is not None:
            return float(self.y_deg)
        return float(self.ry_deg or 0.0)

    @property
    def z(self) -> float:
        if self.rz_deg is not None and self.rz_deg != 0.0:
            return float(self.rz_deg)
        if self.rz is not None:
            return float(self.rz)
        if self.z_deg is not None:
            return float(self.z_deg)
        return float(self.rz_deg or 0.0)


class OverhangAnalysisResult(BaseModel):
    model_id: Optional[str] = None
    critical_angle_deg: float = 45.0
    overhang_percentage: float = 0.0
    overhang_area_cm2: float = 0.0
    total_area_cm2: float = 0.0
    overhang_face_count: int = 0
    total_face_count: int = 0
    requires_support: bool = False

    model_config = ConfigDict(from_attributes=True)

    def __float__(self) -> float:
        return float(self.overhang_percentage)


class SliceModelPayload(BaseModel):
    plane_origin: Optional[List[float]] = Field(
        default=None, description="Point on the slice plane [x, y, z] in mm (defaults to model center)"
    )
    plane_normal: Optional[List[float]] = Field(
        default_factory=lambda: [0.0, 0.0, 1.0], description="Normal vector of the cut plane [nx, ny, nz]"
    )
    cap_faces: bool = Field(
        default=True, description="Cap cut surfaces with planar faces to maintain watertight geometry"
    )
    create_pegs: bool = Field(
        default=False, description="Generate alignment pegs and socket joints on mating cut surfaces"
    )
    peg_radius_mm: float = Field(
        default=3.0, ge=0.5, le=20.0, description="Radius of alignment dowel pins in mm"
    )
    peg_height_mm: float = Field(
        default=6.0, ge=1.0, le=50.0, description="Height of alignment dowel pins in mm"
    )
    peg_clearance_mm: float = Field(
        default=0.2, ge=0.05, le=1.0, description="Clearance tolerance between peg and hole in mm"
    )


class SliceModelResult(BaseModel):
    top_model: WorkingModel
    bottom_model: WorkingModel
    cut_area_cm2: float
    message: str

    model_config = ConfigDict(from_attributes=True)


class MeshRepairReport(BaseModel):
    holes_filled: int = 0
    degenerate_faces_removed: int = 0
    duplicate_vertices_welded: int = 0
    inverted_normals_fixed: bool = False
    is_watertight_before: bool = False
    is_watertight_after: bool = False
    triangle_count_before: int = 0
    triangle_count_after: int = 0
    volume_restored_cm3: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class RepairModelPayload(BaseModel):
    fill_holes: bool = Field(
        default=True, description="Fill and triangulate open boundary loops and holes"
    )
    fix_normals: bool = Field(
        default=True, description="Unify vertex winding and ensure outward-pointing face normals"
    )
    remove_degenerate: bool = Field(
        default=True, description="Remove zero-area, unreferenced, and duplicated triangles"
    )
    remove_degenerate_faces: Optional[bool] = None
    weld_vertices: bool = Field(
        default=True, description="Merge duplicate/close coincident vertices within tolerance"
    )
    weld_tolerance_mm: float = Field(
        default=0.001, ge=0.00001, le=1.0, description="Tolerance distance in mm to merge coincident vertices"
    )
    weld_threshold_mm: Optional[float] = None

    @property
    def effective_remove_degenerate(self) -> bool:
        if self.remove_degenerate_faces is not None:
            return self.remove_degenerate_faces
        return self.remove_degenerate

    @property
    def effective_weld_tolerance_mm(self) -> float:
        if self.weld_threshold_mm is not None:
            return self.weld_threshold_mm
        return self.weld_tolerance_mm


class RepairModelResult(BaseModel):
    repaired_model: WorkingModel
    report: MeshRepairReport
    message: str

    model_config = ConfigDict(from_attributes=True)


class HollowModelPayload(BaseModel):
    wall_thickness_mm: float = Field(
        default=2.0, ge=0.4, le=20.0, description="Shell wall thickness in mm"
    )
    add_drain_holes: bool = Field(
        default=True, description="Add drain holes at the bottom of the hollowed model"
    )
    drain_hole_radius_mm: float = Field(
        default=2.0, ge=0.5, le=15.0, description="Radius of drain holes in mm"
    )
    drain_hole_count: int = Field(
        default=2, ge=1, le=8, description="Number of drain holes to punch"
    )


class HollowModelResult(BaseModel):
    hollowed_model: WorkingModel
    wall_thickness_mm: float
    drain_holes_added: int
    volume_saved_cm3: Optional[float] = None
    message: str

    model_config = ConfigDict(from_attributes=True)


class ArrangeItemPlacement(BaseModel):
    model_id: str
    filename: str
    position_mm: List[float] = Field(description="[X, Y, Z] bed coordinates in mm")
    rotation_deg: List[float] = Field(default_factory=lambda: [0.0, 0.0, 0.0])


class ArrangeProjectPayload(BaseModel):
    spacing_mm: float = Field(
        default=5.0, ge=1.0, le=50.0, description="Clearance margin between models in mm"
    )
    bed_margin_mm: float = Field(
        default=10.0, ge=0.0, le=50.0, description="Margin distance from bed perimeter in mm"
    )
    printer_id: Optional[str] = Field(
        default=None, description="Optional printer profile ID to retrieve bed dimensions"
    )


class ArrangeProjectResult(BaseModel):
    project_id: str
    models_arranged: int
    placements: List[ArrangeItemPlacement]
    all_fit: bool
    message: str

    model_config = ConfigDict(from_attributes=True)


class ExportProject3MFPayload(BaseModel):
    filename: Optional[str] = Field(
        default=None, description="Custom 3MF export filename"
    )
    plate_name: Optional[str] = Field(
        default="Plate 1", description="Build plate name"
    )
    filament_id: Optional[str] = Field(
        default=None, description="Optional filament profile ID to attach to 3MF metadata"
    )
    filament_preset: Optional[str] = Field(
        default="Generic PLA", description="Preset filament name"
    )


class ExportProject3MFResponse(BaseModel):
    project_id: Optional[str] = None
    filename: str
    storage_path: Optional[str] = None
    download_url: str
    file_size_bytes: int
    models_exported: int = 0
    models_included: int = 0
    printer_model: Optional[str] = None
    message: str

    model_config = ConfigDict(from_attributes=True)



