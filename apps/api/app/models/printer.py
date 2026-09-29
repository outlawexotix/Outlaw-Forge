from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class PrinterProfileBase(BaseModel):
    manufacturer: str = Field(..., description="Printer manufacturer, e.g. Creality, Prusa")
    model: str = Field(..., description="Printer model name, e.g. Ender-3")
    build_width_mm: float = Field(..., gt=0, description="X build volume dimension in mm")
    build_depth_mm: float = Field(..., gt=0, description="Y build volume dimension in mm")
    build_height_mm: float = Field(..., gt=0, description="Z build volume dimension in mm")
    nozzle_diameter_mm: float = Field(..., gt=0, description="Nozzle diameter in mm")
    notes: Optional[str] = Field(default=None, description="Optional notes or details about the printer")


class PrinterProfileCreatePayload(PrinterProfileBase):
    pass


class PrinterProfileCreate(PrinterProfileCreatePayload):
    pass


class PrinterProfile(PrinterProfileBase):
    id: str = Field(..., description="Unique identifier for the printer profile")
    created_at: Optional[str] = Field(default=None, description="ISO timestamp of creation")

    model_config = ConfigDict(from_attributes=True)
