from typing import Any, Dict, List, Literal, Optional, Tuple, Union
from pydantic import BaseModel, ConfigDict, Field

from app.models.project import MeshBounds, MeshTransform


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
    format: Literal["stl", "obj", "glb"] = Field(
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

