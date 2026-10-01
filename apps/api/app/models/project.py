from typing import Any, Dict, List, Literal, Optional, Tuple, Union
from pydantic import BaseModel, ConfigDict, Field

ProjectType = Literal[
    "Character",
    "Collectible Figure",
    "Mask",
    "Bust",
    "Statue",
    "Prop",
    "Plaque",
    "Mechanical Part",
    "Decorative Object",
    "Other",
]

OperationType = Literal[
    "IMPORT",
    "SCALE",
    "ROTATE",
    "CENTER",
    "LAY_FLAT",
    "SLICE",
    "REPAIR",
    "EXPORT",
    "CALIBRATION_GENERATE",
    "AUTO_ORIENT",
    "AUTO_ARRANGE",
    "MOUSE_EAR_BRIM",
    "ADAPTIVE_LAYERS",
    "HOLLOW",
    "DUPLICATE",
    "DELETE",
    "ARRANGE",
    "EXPORT_3MF",
]


class SourceFile(BaseModel):
    id: str
    project_id: str
    filename: str
    file_format: str
    file_size_bytes: int
    storage_path: str
    created_at: str

    model_config = ConfigDict(from_attributes=True)


class MeshTransform(BaseModel):
    position_mm: Union[Tuple[float, float, float], List[float]] = Field(
        default_factory=lambda: [0.0, 0.0, 0.0]
    )
    rotation_deg: Union[Tuple[float, float, float], List[float]] = Field(
        default_factory=lambda: [0.0, 0.0, 0.0]
    )
    scale_factors: Union[Tuple[float, float, float], List[float]] = Field(
        default_factory=lambda: [1.0, 1.0, 1.0]
    )
    uniform_scale_percent: float = 100.0

    model_config = ConfigDict(from_attributes=True)


class MeshBounds(BaseModel):
    min: Union[Tuple[float, float, float], List[float]] = Field(
        default_factory=lambda: [0.0, 0.0, 0.0]
    )
    max: Union[Tuple[float, float, float], List[float]] = Field(
        default_factory=lambda: [0.0, 0.0, 0.0]
    )
    dimensions_mm: Union[Tuple[float, float, float], List[float]] = Field(
        default_factory=lambda: [0.0, 0.0, 0.0]
    )

    model_config = ConfigDict(from_attributes=True)


class WorkingModel(BaseModel):
    id: str
    project_id: str
    source_file_id: str
    filename: str
    file_format: str
    storage_path: str
    units: str = "mm"
    bounds: MeshBounds
    triangle_count: int
    vertex_count: int
    surface_area_cm2: float
    volume_cm3: Optional[float] = None
    is_watertight: bool
    transform: MeshTransform
    created_at: str
    updated_at: str

    model_config = ConfigDict(from_attributes=True)


class OperationRecord(BaseModel):
    id: str
    project_id: str
    model_id: Optional[str] = None
    operation_type: OperationType
    timestamp: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    resulting_state_ref: Optional[str] = None
    user_summary: str
    success: bool

    model_config = ConfigDict(from_attributes=True)


class ProjectCreatePayload(BaseModel):
    name: str = Field(..., min_length=1, description="Project name")
    description: Optional[str] = Field(default="", description="Detailed project description")
    project_type: ProjectType = Field(default="Other", description="Project type category")
    selected_printer_id: Optional[str] = Field(default=None, description="Associated printer profile ID")
    notes: Optional[str] = Field(default="", description="General project notes")


class ProjectCreate(ProjectCreatePayload):
    pass


class ProjectUpdatePayload(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, description="Updated project name")
    description: Optional[str] = Field(default=None, description="Updated project description")
    project_type: Optional[ProjectType] = Field(default=None, description="Updated project type")
    selected_printer_id: Optional[str] = Field(default=None, description="Updated printer profile ID")
    notes: Optional[str] = Field(default=None, description="Updated notes")


class ProjectUpdate(ProjectUpdatePayload):
    pass


class Project(BaseModel):
    id: str
    name: str
    description: str = ""
    project_type: ProjectType = "Other"
    created_at: str
    updated_at: str
    thumbnail_url: Optional[str] = None
    selected_printer_id: Optional[str] = None
    units: str = "mm"
    notes: str = ""
    source_files: List[SourceFile] = Field(default_factory=list)
    working_models: List[WorkingModel] = Field(default_factory=list)
    operations: List[OperationRecord] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class ProjectDeleteResponse(BaseModel):
    success: bool
    id: str


FindingSeverity = Literal["INFO", "WARNING", "ERROR"]


class PrintabilityFinding(BaseModel):
    severity: FindingSeverity
    category: str
    message: str
    details: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)


class ExceededDimensions(BaseModel):
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    model_config = ConfigDict(from_attributes=True)


class PrintabilityAnalysis(BaseModel):
    model_id: str
    printer_id: str
    fits_build_volume: bool
    exceeded_dimensions_mm: ExceededDimensions
    findings: List[PrintabilityFinding] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class ScaleModelPayload(BaseModel):
    uniform_scale_percent: Optional[float] = None
    target_height_mm: Optional[float] = None
    target_width_mm: Optional[float] = None
    target_depth_mm: Optional[float] = None
    preserve_aspect_ratio: bool = True


class ExportModelPayload(BaseModel):
    format: Literal["stl", "obj", "glb"]
    filename: Optional[str] = None


class ExportModelResponse(BaseModel):
    download_url: str
    filename: str

