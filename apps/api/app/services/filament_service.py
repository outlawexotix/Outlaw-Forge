"""
Filament Library & Print Cost Calculator Service
Manages material engineering presets and calculates filament consumption, mass, and print cost.
Inspired by OrcaSlicer's material management system.
"""

from typing import Dict, List, Optional, Tuple
import numpy as np
import trimesh

from app.models.calibration import (
    CostEstimationPayload,
    CostEstimationResult,
    FilamentMaterial,
    FilamentProfile,
)


DEFAULT_FILAMENTS: List[FilamentProfile] = [
    FilamentProfile(
        id="generic_pla",
        name="Generic PLA",
        material="PLA",
        density_g_cm3=1.24,
        nozzle_temp_c=210,
        bed_temp_c=60,
        cost_per_kg_usd=20.00,
        shrinkage_factor_pct=0.3,
        recommended_speed_mm_s=150,
        color_hex="#06b6d4",
        notes="Standard easy-printing PLA suitable for prototypes and decorative models.",
    ),
    FilamentProfile(
        id="polymaker_petg",
        name="Polymaker PolyLite PETG",
        material="PETG",
        density_g_cm3=1.27,
        nozzle_temp_c=240,
        bed_temp_c=75,
        cost_per_kg_usd=24.00,
        shrinkage_factor_pct=0.4,
        recommended_speed_mm_s=120,
        color_hex="#3b82f6",
        notes="Durable, chemical-resistant and water-resistant filament with higher thermal stability.",
    ),
    FilamentProfile(
        id="bambu_abs",
        name="Bambu ABS",
        material="ABS",
        density_g_cm3=1.04,
        nozzle_temp_c=260,
        bed_temp_c=90,
        cost_per_kg_usd=25.00,
        shrinkage_factor_pct=0.8,
        recommended_speed_mm_s=150,
        color_hex="#f59e0b",
        notes="High impact resistance and machinability. Requires enclosed chamber to prevent warping.",
    ),
    FilamentProfile(
        id="esun_asa",
        name="eSUN ASA",
        material="ASA",
        density_g_cm3=1.07,
        nozzle_temp_c=250,
        bed_temp_c=95,
        cost_per_kg_usd=28.00,
        shrinkage_factor_pct=0.7,
        recommended_speed_mm_s=120,
        color_hex="#ef4444",
        notes="UV and weather resistant alternative to ABS. Ideal for outdoor automotive and functional parts.",
    ),
    FilamentProfile(
        id="overture_tpu_95a",
        name="Overture TPU 95A",
        material="TPU",
        density_g_cm3=1.21,
        nozzle_temp_c=225,
        bed_temp_c=50,
        cost_per_kg_usd=32.00,
        shrinkage_factor_pct=0.2,
        recommended_speed_mm_s=45,
        color_hex="#10b981",
        notes="Flexible, rubber-like Shore 95A elastomer with exceptional layer bonding and tear strength.",
    ),
    FilamentProfile(
        id="polymaker_pc",
        name="Polymaker PolyMax PC",
        material="PC",
        density_g_cm3=1.18,
        nozzle_temp_c=280,
        bed_temp_c=105,
        cost_per_kg_usd=45.00,
        shrinkage_factor_pct=0.9,
        recommended_speed_mm_s=100,
        color_hex="#8b5cf6",
        notes="Engineering grade polycarbonate with extreme heat deflection (110°C) and structural toughness.",
    ),
    FilamentProfile(
        id="bambu_pa_cf",
        name="Bambu PA-CF (Carbon Fiber Nylon)",
        material="PA-CF",
        density_g_cm3=1.15,
        nozzle_temp_c=290,
        bed_temp_c=100,
        cost_per_kg_usd=60.00,
        shrinkage_factor_pct=0.4,
        recommended_speed_mm_s=120,
        color_hex="#374151",
        notes="Chopped carbon fiber reinforced polyamide. High stiffness, low weight, and premium matte finish.",
    ),
    FilamentProfile(
        id="petg_cf",
        name="Generic PETG-CF",
        material="PETG-CF",
        density_g_cm3=1.29,
        nozzle_temp_c=250,
        bed_temp_c=80,
        cost_per_kg_usd=38.00,
        shrinkage_factor_pct=0.3,
        recommended_speed_mm_s=120,
        color_hex="#475569",
        notes="Carbon fiber filled PETG with enhanced rigidity and reduced stringing.",
    ),
    FilamentProfile(
        id="silk_pla",
        name="Silk Shiny PLA",
        material="Silk PLA",
        density_g_cm3=1.25,
        nozzle_temp_c=215,
        bed_temp_c=60,
        cost_per_kg_usd=23.00,
        shrinkage_factor_pct=0.3,
        recommended_speed_mm_s=100,
        color_hex="#ec4899",
        notes="High-gloss reflective sheen formulation for artistic figurines, props, and display models.",
    ),
]


class FilamentService:
    """Provides material presets and computes print cost and mass estimates."""

    def __init__(self) -> None:
        self.filaments: Dict[str, FilamentProfile] = {f.id: f for f in DEFAULT_FILAMENTS}

    def list_filaments(self) -> List[FilamentProfile]:
        return list(self.filaments.values())

    def get_filament(self, filament_id: str) -> Optional[FilamentProfile]:
        return self.filaments.get(filament_id)

    def estimate_cost(
        self, mesh: trimesh.Trimesh, model_id: str, payload: CostEstimationPayload
    ) -> CostEstimationResult:
        """
        Calculates mass, filament length, and cost based on geometry and material density.
        """
        # Determine material properties
        profile = None
        if payload.filament_id:
            profile = self.get_filament(payload.filament_id)

        material_name = profile.name if profile else "Custom Material"
        density = (
            payload.custom_density_g_cm3
            if payload.custom_density_g_cm3 is not None
            else (profile.density_g_cm3 if profile else 1.24)
        )
        cost_per_kg = (
            payload.custom_cost_per_kg_usd
            if payload.custom_cost_per_kg_usd is not None
            else (profile.cost_per_kg_usd if profile else 20.00)
        )

        # 1. Calculate raw volume in cm3
        if mesh.is_watertight and mesh.volume > 0:
            raw_vol_cm3 = float(mesh.volume) / 1000.0  # mm3 to cm3
        else:
            # Fallback estimation from bounding box with 50% packing fill factor
            ext = mesh.extents
            raw_vol_cm3 = float(ext[0] * ext[1] * ext[2] * 0.5) / 1000.0

        surface_area_cm2 = float(mesh.area) / 100.0  # mm2 to cm2

        # 2. Estimate perimeter shell solid volume vs internal infill volume
        # Shell wall thickness: wall_count * 0.4mm nozzle = e.g. 1.2mm (0.12 cm)
        wall_thickness_cm = (payload.wall_count * 0.4) / 10.0
        shell_vol_cm3 = surface_area_cm2 * wall_thickness_cm

        # Infill volume calculation
        internal_vol_cm3 = max(0.0, raw_vol_cm3 - shell_vol_cm3)
        infill_fraction = np.clip(payload.infill_percentage / 100.0, 0.0, 1.0)
        infill_vol_cm3 = internal_vol_cm3 * infill_fraction

        effective_vol_cm3 = min(raw_vol_cm3, shell_vol_cm3) + infill_vol_cm3

        # 3. Mass calculation (Mass = Volume * Density)
        estimated_mass_g = effective_vol_cm3 * density

        # 4. Filament Length (for 1.75mm diameter filament spool)
        # Volume of 1m of 1.75mm filament = pi * (1.75 / 20)^2 * 100 cm = 2.405 cm3
        filament_cm3_per_meter = np.pi * ((1.75 / 2.0) / 10.0) ** 2 * 100.0  # ~2.405 cm3/m
        estimated_length_m = effective_vol_cm3 / filament_cm3_per_meter

        # 5. Total Material Cost
        estimated_cost_usd = (estimated_mass_g / 1000.0) * cost_per_kg

        message = (
            f"Cost estimation for {material_name}: "
            f"{estimated_mass_g:.1f}g ({estimated_length_m:.1f}m), "
            f"${estimated_cost_usd:.2f} USD at {payload.infill_percentage:.0f}% infill."
        )

        return CostEstimationResult(
            model_id=model_id,
            material_name=material_name,
            estimated_mass_grams=round(estimated_mass_g, 2),
            estimated_filament_length_meters=round(estimated_length_m, 2),
            estimated_material_cost_usd=round(estimated_cost_usd, 2),
            model_volume_cm3=round(raw_vol_cm3, 2),
            effective_infill_volume_cm3=round(effective_vol_cm3, 2),
            message=message,
        )


filament_service = FilamentService()
