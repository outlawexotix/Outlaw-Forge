from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


FindingSeverity = Literal["INFO", "WARNING", "ERROR"]


class PrintabilityFinding(BaseModel):
    severity: FindingSeverity
    category: str
    message: str
    details: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)


class ExceededDimensions(BaseModel):
    x: float = Field(default=0.0, description="Exceeded width in mm (0 if fits)")
    y: float = Field(default=0.0, description="Exceeded depth in mm (0 if fits)")
    z: float = Field(default=0.0, description="Exceeded height in mm (0 if fits)")

    model_config = ConfigDict(from_attributes=True)


class PrintabilityAnalysis(BaseModel):
    model_id: str
    printer_id: str
    fits_build_volume: bool
    exceeded_dimensions_mm: ExceededDimensions
    findings: List[PrintabilityFinding] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
