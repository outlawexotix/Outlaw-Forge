from typing import Any, Dict, List, Optional, Tuple, Union

from app.models.printer import PrinterProfile
from app.models.project import (
    ExceededDimensions,
    PrintabilityAnalysis,
    PrintabilityFinding,
    WorkingModel,
)


class PrintabilityService:
    """Deterministic evaluation of 3D model dimensions against 3D printer build volumes."""

    @staticmethod
    def evaluate(
        model: Union[WorkingModel, Dict[str, Any]],
        printer: Union[PrinterProfile, Dict[str, Any]],
    ) -> PrintabilityAnalysis:
        """
        Evaluate a WorkingModel against a PrinterProfile build volume and geometry constraints.
        """
        if isinstance(model, dict):
            model_id = model.get("id", "model")
            bounds = model.get("bounds", {})
            if isinstance(bounds, dict):
                dims = bounds.get("dimensions_mm", [0.0, 0.0, 0.0])
            else:
                dims = getattr(bounds, "dimensions_mm", [0.0, 0.0, 0.0])
            triangle_count = model.get("triangle_count", 0)
            is_watertight = model.get("is_watertight", True)
        else:
            model_id = model.id
            dims = model.bounds.dimensions_mm
            triangle_count = model.triangle_count
            is_watertight = model.is_watertight

        analysis = check_printability(dimensions_mm=dims, printer=printer, model_id=model_id)

        # Add geometry findings if issues exist
        if not is_watertight:
            analysis.findings.append(
                PrintabilityFinding(
                    severity="WARNING",
                    category="Mesh Integrity",
                    message="Model is not watertight (non-manifold geometry detected). Slicers may experience infill or slicing defects.",
                    details={"is_watertight": False},
                )
            )

        if triangle_count > 1_000_000:
            analysis.findings.append(
                PrintabilityFinding(
                    severity="WARNING",
                    category="Mesh Complexity",
                    message=f"High polygon density ({triangle_count:,} triangles). Slicing may take longer.",
                    details={"triangle_count": triangle_count},
                )
            )
        elif 0 < triangle_count < 100:
            analysis.findings.append(
                PrintabilityFinding(
                    severity="WARNING",
                    category="Mesh Complexity",
                    message=f"Low polygon count ({triangle_count} triangles). Surfaces may appear faceted.",
                    details={"triangle_count": triangle_count},
                )
            )

        return analysis


def check_printability(
    dimensions_mm: Union[Tuple[float, float, float], List[float]],
    printer: Union[PrinterProfile, Dict[str, Any]],
    model_id: str = "model",
) -> PrintabilityAnalysis:
    """
    Deterministically analyze if a 3D model's bounding dimensions fit within a printer's build volume.
    Calculates exact exceeded millimeters per axis (X, Y, Z).
    """
    dim_x = float(dimensions_mm[0]) if len(dimensions_mm) > 0 else 0.0
    dim_y = float(dimensions_mm[1]) if len(dimensions_mm) > 1 else 0.0
    dim_z = float(dimensions_mm[2]) if len(dimensions_mm) > 2 else 0.0

    if isinstance(printer, dict):
        p_id = printer.get("id", "printer")
        p_name = f"{printer.get('manufacturer', '')} {printer.get('model', '')}".strip() or "Printer"
        max_x = float(printer.get("build_width_mm", 0.0))
        max_y = float(printer.get("build_depth_mm", 0.0))
        max_z = float(printer.get("build_height_mm", 0.0))
    else:
        p_id = printer.id
        p_name = f"{printer.manufacturer} {printer.model}".strip()
        max_x = float(printer.build_width_mm)
        max_y = float(printer.build_depth_mm)
        max_z = float(printer.build_height_mm)

    exceeded_x = max(0.0, round(dim_x - max_x, 4))
    exceeded_y = max(0.0, round(dim_y - max_y, 4))
    exceeded_z = max(0.0, round(dim_z - max_z, 4))

    fits_build_volume = (exceeded_x == 0.0 and exceeded_y == 0.0 and exceeded_z == 0.0)

    findings: List[PrintabilityFinding] = []

    if fits_build_volume:
        findings.append(
            PrintabilityFinding(
                severity="INFO",
                category="build_volume",
                message=f"Model dimensions ({dim_x:.1f} x {dim_y:.1f} x {dim_z:.1f} mm) fit within {p_name} build volume ({max_x:.1f} x {max_y:.1f} x {max_z:.1f} mm).",
                details={
                    "model_dimensions_mm": [dim_x, dim_y, dim_z],
                    "printer_build_volume_mm": [max_x, max_y, max_z],
                },
            )
        )
    else:
        exceeded_parts = []
        if exceeded_x > 0:
            exceeded_parts.append(f"Width (X) exceeds by {exceeded_x:.1f} mm")
        if exceeded_y > 0:
            exceeded_parts.append(f"Depth (Y) exceeds by {exceeded_y:.1f} mm")
        if exceeded_z > 0:
            exceeded_parts.append(f"Height (Z) exceeds by {exceeded_z:.1f} mm")

        findings.append(
            PrintabilityFinding(
                severity="ERROR",
                category="build_volume",
                message=f"Model exceeds {p_name} build volume: {', '.join(exceeded_parts)}.",
                details={
                    "model_dimensions_mm": [dim_x, dim_y, dim_z],
                    "printer_build_volume_mm": [max_x, max_y, max_z],
                    "exceeded_dimensions_mm": {
                        "x": exceeded_x,
                        "y": exceeded_y,
                        "z": exceeded_z,
                    },
                },
            )
        )

    return PrintabilityAnalysis(
        model_id=model_id,
        printer_id=p_id,
        fits_build_volume=fits_build_volume,
        exceeded_dimensions_mm=ExceededDimensions(
            x=exceeded_x,
            y=exceeded_y,
            z=exceeded_z,
        ),
        findings=findings,
    )


printability_service = PrintabilityService()
