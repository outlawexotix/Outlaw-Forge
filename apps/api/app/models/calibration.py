from typing import Any, Dict, List, Literal, Optional, Tuple, Union
from pydantic import BaseModel, ConfigDict, Field
from app.models.project import MeshBounds, WorkingModel

CalibrationType = Literal[
    "temp_tower",
    "flow_rate",
    "retraction_tower",
    "tolerance_gauge",
    "overhang_benchmark",
    "calibration_cube_v2",
    "max_volumetric_speed",
]

FilamentMaterial = Literal[
    "PLA",
    "PETG",
    "ABS",
    "ASA",
    "TPU",
    "PC",
    "PA-CF",
    "PETG-CF",
    "Silk PLA",
]


class CalibrationGeneratePayload(BaseModel):
    calibration_type: CalibrationType = Field(
        default="temp_tower", description="Calibration test artifact type"
    )
    start_temp_c: Optional[int] = Field(
        default=220, ge=150, le=350, description="Starting temperature in C"
    )
    end_temp_c: Optional[int] = Field(
        default=180, ge=150, le=350, description="Ending temperature in C"
    )
    temp_step_c: Optional[int] = Field(
        default=5, ge=1, le=20, description="Temperature decrease step per tier in C"
    )
    flow_rate_start_pct: Optional[float] = Field(
        default=-15.0, ge=-50.0, le=50.0, description="Flow rate start offset %"
    )
    flow_rate_end_pct: Optional[float] = Field(
        default=15.0, ge=-50.0, le=50.0, description="Flow rate end offset %"
    )
    flow_rate_step_pct: Optional[float] = Field(
        default=5.0, ge=1.0, le=20.0, description="Flow rate step %"
    )
    retraction_start_mm: Optional[float] = Field(
        default=1.0, ge=0.0, le=15.0, description="Starting retraction distance in mm"
    )
    retraction_end_mm: Optional[float] = Field(
        default=6.0, ge=0.5, le=20.0, description="Ending retraction distance in mm"
    )
    retraction_step_mm: Optional[float] = Field(
        default=1.0, ge=0.1, le=5.0, description="Retraction step distance in mm"
    )
    tolerance_min_mm: Optional[float] = Field(
        default=0.1, ge=0.01, le=1.0, description="Minimum clearance gap in mm"
    )
    tolerance_max_mm: Optional[float] = Field(
        default=0.5, ge=0.05, le=2.0, description="Maximum clearance gap in mm"
    )
    tolerance_step_mm: Optional[float] = Field(
        default=0.1, ge=0.01, le=0.5, description="Clearance step in mm"
    )
    cube_size_mm: Optional[float] = Field(
        default=20.0, ge=10.0, le=100.0, description="Calibration cube dimension in mm"
    )
    custom_name: Optional[str] = Field(
        default=None, description="Optional custom name for calibration model"
    )


class CalibrationGenerateResult(BaseModel):
    model: WorkingModel
    calibration_type: CalibrationType
    suggested_slicer_notes: List[str] = Field(default_factory=list)
    message: str

    model_config = ConfigDict(from_attributes=True)


class AutoOrientPayload(BaseModel):
    overhang_weight: float = Field(
        default=1.0, ge=0.0, le=10.0, description="Penalty weight for overhangs requiring support"
    )
    height_weight: float = Field(
        default=0.3, ge=0.0, le=10.0, description="Penalty weight for total Z height / print time"
    )
    bed_contact_weight: float = Field(
        default=0.5, ge=0.0, le=10.0, description="Reward weight for bed contact surface area"
    )
    critical_angle_deg: float = Field(
        default=45.0, ge=15.0, le=85.0, description="Critical overhang angle threshold in degrees"
    )


class AutoOrientResult(BaseModel):
    oriented_model: WorkingModel
    optimal_rotation_deg: List[float] = Field(default_factory=lambda: [0.0, 0.0, 0.0])
    original_overhang_area_cm2: float
    optimized_overhang_area_cm2: float
    reduction_percentage: float
    message: str

    model_config = ConfigDict(from_attributes=True)


class AutoArrangePayload(BaseModel):
    spacing_mm: float = Field(
        default=10.0, ge=1.0, le=50.0, description="Gap spacing between models in mm"
    )
    bed_width_mm: Optional[float] = Field(
        default=None, ge=50.0, le=1000.0, description="Build plate width in mm"
    )
    bed_depth_mm: Optional[float] = Field(
        default=None, ge=50.0, le=1000.0, description="Build plate depth in mm"
    )
    model_ids: Optional[List[str]] = Field(
        default=None, description="Subset of working model IDs to arrange (or all if None)"
    )


class ModelPlacement(BaseModel):
    model_id: str
    x_offset_mm: float
    y_offset_mm: float
    rotation_deg: float = 0.0
    bounds: MeshBounds

    model_config = ConfigDict(from_attributes=True)


class AutoArrangeResult(BaseModel):
    arranged_models: List[WorkingModel] = Field(default_factory=list)
    placements: List[ModelPlacement] = Field(default_factory=list)
    fits_bed: bool = True
    message: str

    model_config = ConfigDict(from_attributes=True)


class MouseEarPayload(BaseModel):
    radius_mm: float = Field(
        default=8.0, ge=2.0, le=30.0, description="Radius of corner brim discs in mm"
    )
    thickness_mm: float = Field(
        default=0.2, ge=0.1, le=1.0, description="Thickness/height of corner discs in mm (1 layer)"
    )
    corner_angle_threshold_deg: float = Field(
        default=120.0, ge=30.0, le=170.0, description="Maximum interior corner angle to treat as acute corner"
    )
    auto_detect_corners: bool = Field(
        default=True, description="Automatically find acute corners on base footprint"
    )
    custom_centers_mm: Optional[List[List[float]]] = Field(
        default=None, description="Optional manual list of [x, y] coordinates for mouse ear placement"
    )


class MouseEarResult(BaseModel):
    modified_model: WorkingModel
    ears_added_count: int
    ear_positions_mm: List[List[float]] = Field(default_factory=list)
    message: str

    model_config = ConfigDict(from_attributes=True)


class AdaptiveLayerPayload(BaseModel):
    min_layer_height_mm: float = Field(
        default=0.08, ge=0.04, le=0.20, description="Minimum layer height for curved slopes in mm"
    )
    max_layer_height_mm: float = Field(
        default=0.28, ge=0.12, le=0.40, description="Maximum layer height for vertical walls in mm"
    )
    nominal_layer_height_mm: float = Field(
        default=0.20, ge=0.08, le=0.32, description="Nominal standard layer height in mm"
    )
    step_size_mm: float = Field(
        default=0.04, ge=0.01, le=0.10, description="Layer height quantization step in mm"
    )
    smoothness_factor: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Transition smoothing between adjacent layers"
    )


class AdaptiveLayerCurvePoint(BaseModel):
    z_height_mm: float
    layer_height_mm: float
    slope_deg: float
    layer_index: int

    model_config = ConfigDict(from_attributes=True)


class AdaptiveLayerResult(BaseModel):
    model_id: str
    total_layers_nominal: int
    total_layers_adaptive: int
    estimated_time_nominal_min: float
    estimated_time_adaptive_min: float
    time_savings_pct: float
    layer_curve: List[AdaptiveLayerCurvePoint] = Field(default_factory=list)
    message: str

    model_config = ConfigDict(from_attributes=True)


class FilamentProfile(BaseModel):
    id: str
    name: str
    material: FilamentMaterial
    density_g_cm3: float
    nozzle_temp_c: int
    bed_temp_c: int
    cost_per_kg_usd: float
    shrinkage_factor_pct: float
    recommended_speed_mm_s: int
    color_hex: Optional[str] = "#3b82f6"
    notes: Optional[str] = ""

    model_config = ConfigDict(from_attributes=True)


class CostEstimationPayload(BaseModel):
    filament_id: Optional[str] = Field(default=None, description="Preset filament profile ID")
    custom_density_g_cm3: Optional[float] = Field(default=None, description="Custom density g/cm3")
    custom_cost_per_kg_usd: Optional[float] = Field(default=None, description="Custom price USD/kg")
    infill_percentage: float = Field(default=15.0, ge=0.0, le=100.0, description="Infill density %")
    wall_count: int = Field(default=3, ge=1, le=10, description="Perimeter wall count")
    top_bottom_layers: int = Field(default=4, ge=1, le=10, description="Top and bottom solid layers")


class CostEstimationResult(BaseModel):
    model_id: str
    material_name: str
    estimated_mass_grams: float
    estimated_filament_length_meters: float
    estimated_material_cost_usd: float
    model_volume_cm3: float
    effective_infill_volume_cm3: float
    message: str

    model_config = ConfigDict(from_attributes=True)
