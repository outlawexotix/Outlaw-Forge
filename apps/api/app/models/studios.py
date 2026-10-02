from typing import Any, Dict, List, Literal, Optional, Tuple, Union
from pydantic import BaseModel, ConfigDict, Field
from app.models.project import WorkingModel


# ==========================================
# MASKSMITH STUDIO MODELS
# ==========================================

HeadSizePreset = Literal[
    "Adult Male (L/XL - 155mm)",
    "Adult Male (M - 150mm)",
    "Adult Female (M - 145mm)",
    "Adult Female (S - 140mm)",
    "Youth (130mm)",
    "Child (120mm)",
    "Custom",
]

MagnetPreset = Literal[
    "6x3mm (D:6mm, H:3mm)",
    "8x3mm (D:8mm, H:3mm)",
    "10x3mm (D:10mm, H:3mm)",
    "12x3mm (D:12mm, H:3mm)",
    "6x2mm (D:6mm, H:2mm)",
    "8x2mm (D:8mm, H:2mm)",
    "10x2mm (D:10mm, H:2mm)",
    "Custom",
]

MagnetPlacementMode = Literal[
    "perimeter_4_corner",
    "perimeter_6_point",
    "split_seam_flange",
    "custom_points",
]

StrapPreset = Literal[
    "15mm Elastic Band",
    "20mm (3/4in) Webbing",
    "25mm (1in) Tactical Webbing",
    "38mm (1.5in) Heavy Duty Webbing",
    "Custom",
]


class MaskFitAnalysis(BaseModel):
    model_id: str
    inner_width_mm: float
    inner_height_mm: float
    inner_depth_mm: float
    recommended_preset: HeadSizePreset
    recommended_scale_male_pct: float
    recommended_scale_female_pct: float
    recommended_scale_youth_pct: float
    head_clearance_padding_mm: float
    is_wearable_scale: bool
    notes: str

    model_config = ConfigDict(from_attributes=True)


class MaskFitScalePayload(BaseModel):
    target_preset: Optional[HeadSizePreset] = "Adult Male (L/XL - 155mm)"
    target_inner_width_mm: Optional[float] = Field(
        default=None, ge=50.0, le=300.0, description="Target inner temple width in mm"
    )
    padding_clearance_mm: float = Field(
        default=8.0, ge=0.0, le=30.0, description="Comfort foam/padding clearance margin in mm"
    )
    uniform_scale: bool = Field(
        default=True, description="Maintain proportional aspect ratio across X, Y, Z"
    )


class MagnetSocketPunchPayload(BaseModel):
    magnet_preset: Optional[MagnetPreset] = "8x3mm (D:8mm, H:3mm)"
    custom_diameter_mm: Optional[float] = Field(default=8.0, ge=1.0, le=30.0)
    custom_depth_mm: Optional[float] = Field(default=3.0, ge=0.5, le=20.0)
    clearance_tolerance_mm: float = Field(
        default=0.15, ge=0.0, le=1.0, description="Press-fit clearance tolerance"
    )
    placement_mode: MagnetPlacementMode = "perimeter_4_corner"
    margin_inset_mm: float = Field(
        default=5.0, ge=1.0, le=50.0, description="Inset distance from outer perimeter edge"
    )
    custom_points: Optional[List[List[float]]] = Field(
        default=None, description="Optional custom [X, Y, Z] coordinate list for sockets"
    )


class MagnetSocketPunchResult(BaseModel):
    model: WorkingModel
    sockets_punched: int
    magnet_diameter_mm: float
    magnet_depth_mm: float
    socket_positions: List[List[float]]
    message: str

    model_config = ConfigDict(from_attributes=True)


class StrapSlotPunchPayload(BaseModel):
    strap_preset: Optional[StrapPreset] = "25mm (1in) Tactical Webbing"
    slot_width_mm: Optional[float] = Field(default=26.0, ge=5.0, le=60.0)
    slot_thickness_mm: Optional[float] = Field(default=3.5, ge=1.0, le=15.0)
    placement: Literal["temple_bilateral", "crown_and_temple_3point", "custom"] = "temple_bilateral"
    inset_from_edge_mm: float = Field(default=12.0, ge=2.0, le=50.0)
    custom_positions: Optional[List[List[float]]] = None


class StrapSlotPunchResult(BaseModel):
    model: WorkingModel
    slots_punched: int
    slot_width_mm: float
    slot_thickness_mm: float
    slot_positions: List[List[float]]
    message: str

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# FIGUREFORGE STUDIO MODELS
# ==========================================

PlinthShape = Literal[
    "cylinder",
    "hexagon",
    "octagon",
    "stepped_round",
    "square_chamfered",
]


class CenterOfMassAnalysis(BaseModel):
    model_id: str
    center_of_mass: List[float] = Field(description="[X, Y, Z] center of gravity in mm")
    ground_projection: List[float] = Field(description="[X, Y, 0] projected footprint point in mm")
    base_centroid: List[float] = Field(description="[X, Y, 0] base center point in mm")
    com_offset_from_center_mm: float
    base_contact_radius_mm: float
    tipping_angle_deg: float
    stability_status: Literal["STABLE", "MARGINAL", "TOPPLE_RISK"]
    is_freestanding: bool
    recommended_plinth_diameter_mm: float
    notes: str

    model_config = ConfigDict(from_attributes=True)


class PlinthGeneratePayload(BaseModel):
    shape: PlinthShape = "cylinder"
    diameter_mm: float = Field(
        default=80.0, ge=20.0, le=350.0, description="Plinth diameter / width in mm"
    )
    height_mm: float = Field(
        default=15.0, ge=3.0, le=100.0, description="Plinth base height in mm"
    )
    chamfer_height_mm: float = Field(
        default=3.0, ge=0.0, le=20.0, description="Top bevel/chamfer height in mm"
    )
    add_nameplate_recess: bool = Field(
        default=False, description="Recessed frontal slot for metal/acrylic nameplate"
    )
    add_figure_sockets: bool = Field(
        default=True, description="Add peg socket holes to receive figure key-pegs"
    )
    socket_diameter_mm: float = Field(default=5.0, ge=1.0, le=20.0)
    socket_depth_mm: float = Field(default=8.0, ge=2.0, le=40.0)
    socket_spacing_mm: float = Field(default=25.0, ge=5.0, le=150.0)


class PlinthGenerateResult(BaseModel):
    plinth_model: WorkingModel
    shape: PlinthShape
    diameter_mm: float
    height_mm: float
    has_sockets: bool
    message: str

    model_config = ConfigDict(from_attributes=True)


class KeyPegPayload(BaseModel):
    peg_shape: Literal["cylinder", "square", "keyed_dowel"] = "cylinder"
    peg_diameter_mm: float = Field(default=4.8, ge=1.5, le=20.0)
    peg_length_mm: float = Field(default=8.0, ge=3.0, le=30.0)
    foot_offset_mm: float = Field(
        default=12.0, ge=0.0, le=50.0, description="Lateral spacing from center line for foot pegs"
    )
    dual_feet_pegs: bool = Field(
        default=True, description="Add 2 pegs (left and right foot) or single central peg"
    )


class KeyPegResult(BaseModel):
    model_with_pegs: WorkingModel
    pegs_added_count: int
    peg_diameter_mm: float
    peg_length_mm: float
    peg_positions: List[List[float]]
    message: str

    model_config = ConfigDict(from_attributes=True)
