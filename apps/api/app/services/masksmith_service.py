import math
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import trimesh

from app.models.studios import (
    HeadSizePreset,
    MagnetPlacementMode,
    MagnetPreset,
    MaskFitAnalysis,
    StrapPreset,
)


HEAD_SIZE_MAP: Dict[HeadSizePreset, float] = {
    "Adult Male (L/XL - 155mm)": 155.0,
    "Adult Male (M - 150mm)": 150.0,
    "Adult Female (M - 145mm)": 145.0,
    "Adult Female (S - 140mm)": 140.0,
    "Youth (130mm)": 130.0,
    "Child (120mm)": 120.0,
    "Custom": 150.0,
}

MAGNET_PRESET_MAP: Dict[MagnetPreset, Tuple[float, float]] = {
    "6x3mm (D:6mm, H:3mm)": (6.0, 3.0),
    "8x3mm (D:8mm, H:3mm)": (8.0, 3.0),
    "10x3mm (D:10mm, H:3mm)": (10.0, 3.0),
    "12x3mm (D:12mm, H:3mm)": (12.0, 3.0),
    "6x2mm (D:6mm, H:2mm)": (6.0, 2.0),
    "8x2mm (D:8mm, H:2mm)": (8.0, 2.0),
    "10x2mm (D:10mm, H:2mm)": (10.0, 2.0),
    "Custom": (8.0, 3.0),
}

STRAP_PRESET_MAP: Dict[StrapPreset, Tuple[float, float]] = {
    "15mm Elastic Band": (16.0, 3.0),
    "20mm (3/4in) Webbing": (21.0, 3.5),
    "25mm (1in) Tactical Webbing": (26.0, 3.8),
    "38mm (1.5in) Heavy Duty Webbing": (39.5, 4.2),
    "Custom": (26.0, 3.5),
}


class MaskSmithService:
    @staticmethod
    def analyze_mask_fit(mesh: trimesh.Trimesh, model_id: str = "") -> MaskFitAnalysis:
        """
        Analyze mask dimensions, calculate anthropometric head clearance,
        and calculate recommended scale factors for various human head profiles.
        """
        extents = [float(v) for v in mesh.extents]
        width_mm = round(extents[0], 2)
        depth_mm = round(extents[1], 2)
        height_mm = round(extents[2], 2)

        # Standard adult male default clearance: 8mm foam padding
        default_padding = 8.0
        target_male = HEAD_SIZE_MAP["Adult Male (L/XL - 155mm)"] + default_padding
        target_female = HEAD_SIZE_MAP["Adult Female (M - 145mm)"] + default_padding
        target_youth = HEAD_SIZE_MAP["Youth (130mm)"] + default_padding

        scale_male_pct = round((target_male / max(width_mm, 1.0)) * 100.0, 2)
        scale_female_pct = round((target_female / max(width_mm, 1.0)) * 100.0, 2)
        scale_youth_pct = round((target_youth / max(width_mm, 1.0)) * 100.0, 2)

        is_wearable = 120.0 <= width_mm <= 220.0 and 150.0 <= height_mm <= 320.0

        if width_mm >= 160.0:
            rec_preset = "Adult Male (L/XL - 155mm)"
            notes = "Mask is currently scaled for large adult male sizing."
        elif width_mm >= 148.0:
            rec_preset = "Adult Male (M - 150mm)"
            notes = "Mask is currently scaled for standard adult male sizing."
        elif width_mm >= 140.0:
            rec_preset = "Adult Female (M - 145mm)"
            notes = "Mask is currently scaled for adult female sizing."
        elif width_mm >= 125.0:
            rec_preset = "Youth (130mm)"
            notes = "Mask is currently scaled for youth sizing."
        else:
            rec_preset = "Child (120mm)"
            notes = "Mask appears miniature or scaled for child/display sizing."

        return MaskFitAnalysis(
            model_id=model_id,
            inner_width_mm=width_mm,
            inner_height_mm=height_mm,
            inner_depth_mm=depth_mm,
            recommended_preset=rec_preset,
            recommended_scale_male_pct=scale_male_pct,
            recommended_scale_female_pct=scale_female_pct,
            recommended_scale_youth_pct=scale_youth_pct,
            head_clearance_padding_mm=default_padding,
            is_wearable_scale=is_wearable,
            notes=notes,
        )

    @staticmethod
    def scale_mask_fit(
        mesh: trimesh.Trimesh,
        target_preset: Optional[HeadSizePreset] = "Adult Male (L/XL - 155mm)",
        custom_inner_width_mm: Optional[float] = None,
        padding_clearance_mm: float = 8.0,
        uniform: bool = True,
    ) -> Tuple[trimesh.Trimesh, float]:
        """
        Scale mask geometry proportionally to match targeted anthropometric head width + comfort padding.
        """
        if mesh is None or len(mesh.faces) == 0:
            raise ValueError("Cannot scale empty mesh.")

        current_w = float(mesh.extents[0])
        if custom_inner_width_mm and custom_inner_width_mm > 0:
            base_head_w = custom_inner_width_mm
        else:
            base_head_w = HEAD_SIZE_MAP.get(target_preset or "Adult Male (L/XL - 155mm)", 155.0)

        target_w = base_head_w + padding_clearance_mm
        scale_factor = target_w / max(current_w, 0.001)

        scaled = mesh.copy()
        if uniform:
            scaled.apply_scale(scale_factor)
        else:
            scaled.apply_scale([scale_factor, scale_factor, scale_factor])

        return scaled, scale_factor

    @staticmethod
    def punch_magnet_sockets(
        mesh: trimesh.Trimesh,
        magnet_preset: Optional[MagnetPreset] = "8x3mm (D:8mm, H:3mm)",
        custom_diameter_mm: Optional[float] = None,
        custom_depth_mm: Optional[float] = None,
        clearance_tolerance_mm: float = 0.15,
        placement_mode: MagnetPlacementMode = "perimeter_4_corner",
        margin_inset_mm: float = 6.0,
        custom_points: Optional[List[List[float]]] = None,
    ) -> Tuple[trimesh.Trimesh, List[List[float]], float, float]:
        """
        Boolean-subtract cylindrical magnet receiver sockets around perimeter or custom anchor points.
        """
        if mesh is None or len(mesh.faces) == 0:
            raise ValueError("Cannot punch magnet sockets into empty mesh.")

        if custom_diameter_mm and custom_depth_mm:
            dia, depth = float(custom_diameter_mm), float(custom_depth_mm)
        else:
            dia, depth = MAGNET_PRESET_MAP.get(magnet_preset or "8x3mm (D:8mm, H:3mm)", (8.0, 3.0))

        hole_radius = (dia + clearance_tolerance_mm) / 2.0
        hole_height = depth + 0.5

        bounds_min = mesh.bounds[0]
        bounds_max = mesh.bounds[1]

        min_x, min_y, min_z = [float(v) for v in bounds_min]
        max_x, max_y, max_z = [float(v) for v in bounds_max]
        center_x = (min_x + max_x) / 2.0
        center_z = (min_z + max_z) / 2.0
        width = max_x - min_x
        height = max_z - min_z

        socket_positions: List[List[float]] = []

        if custom_points and len(custom_points) > 0:
            socket_positions = [[float(c) for c in pt] for pt in custom_points]
        elif placement_mode == "perimeter_4_corner":
            dx = max(width / 2.0 - margin_inset_mm, 5.0)
            z_low = min_z + height * 0.25
            z_high = min_z + height * 0.75
            y_pos = min_y + margin_inset_mm

            socket_positions = [
                [-dx, y_pos, z_low],
                [dx, y_pos, z_low],
                [-dx, y_pos, z_high],
                [dx, y_pos, z_high],
            ]
        elif placement_mode == "perimeter_6_point":
            dx = max(width / 2.0 - margin_inset_mm, 5.0)
            z_low = min_z + height * 0.2
            z_mid = min_z + height * 0.5
            z_high = min_z + height * 0.8
            y_pos = min_y + margin_inset_mm

            socket_positions = [
                [-dx, y_pos, z_low],
                [dx, y_pos, z_low],
                [-dx, y_pos, z_mid],
                [dx, y_pos, z_mid],
                [-dx, y_pos, z_high],
                [dx, y_pos, z_high],
            ]
        elif placement_mode == "split_seam_flange":
            dx = max(width / 2.0 - margin_inset_mm, 5.0)
            y_mid = (min_y + max_y) / 2.0
            socket_positions = [
                [-dx, y_mid - 20.0, center_z],
                [-dx, y_mid + 20.0, center_z],
                [dx, y_mid - 20.0, center_z],
                [dx, y_mid + 20.0, center_z],
            ]
        else:
            dx = max(width / 2.0 - margin_inset_mm, 5.0)
            socket_positions = [
                [-dx, min_y + margin_inset_mm, center_z],
                [dx, min_y + margin_inset_mm, center_z],
            ]

        # Construct cylindrical socket cutter meshes aligned along Y-axis (inward facing)
        cutters = []
        for pos in socket_positions:
            cyl = trimesh.creation.cylinder(radius=hole_radius, height=hole_height * 2.0)
            # Rotate cylinder from Z to Y axis
            rot_y = trimesh.transformations.rotation_matrix(np.pi / 2.0, [1, 0, 0])
            cyl.apply_transform(rot_y)
            cyl.apply_translation(pos)
            cutters.append(cyl)

        punched_mesh = mesh.copy()
        if cutters:
            try:
                cutter_union = trimesh.util.concatenate(cutters) if len(cutters) > 1 else cutters[0]
                diff = trimesh.boolean.difference([punched_mesh, cutter_union])
                if diff is not None and len(diff.faces) > 0:
                    punched_mesh = diff
                    punched_mesh.fix_normals()
            except Exception:
                # Fallback to returning original mesh if boolean library encounters non-manifold facet
                pass

        return punched_mesh, socket_positions, dia, depth

    @staticmethod
    def punch_strap_slots(
        mesh: trimesh.Trimesh,
        strap_preset: Optional[StrapPreset] = "25mm (1in) Tactical Webbing",
        slot_width_mm: Optional[float] = None,
        slot_thickness_mm: Optional[float] = None,
        placement: str = "temple_bilateral",
        inset_from_edge_mm: float = 12.0,
        custom_positions: Optional[List[List[float]]] = None,
    ) -> Tuple[trimesh.Trimesh, List[List[float]], float, float]:
        """
        Boolean-subtract through-slots for elastic strap webbing and harness loops.
        """
        if mesh is None or len(mesh.faces) == 0:
            raise ValueError("Cannot punch strap slots into empty mesh.")

        if slot_width_mm and slot_thickness_mm:
            sw, st = float(slot_width_mm), float(slot_thickness_mm)
        else:
            sw, st = STRAP_PRESET_MAP.get(strap_preset or "25mm (1in) Tactical Webbing", (26.0, 3.8))

        bounds_min = mesh.bounds[0]
        bounds_max = mesh.bounds[1]

        min_x, min_y, min_z = [float(v) for v in bounds_min]
        max_x, max_y, max_z = [float(v) for v in bounds_max]
        center_x = (min_x + max_x) / 2.0
        center_y = (min_y + max_y) / 2.0
        center_z = (min_z + max_z) / 2.0
        width = max_x - min_x
        height = max_z - min_z

        slot_positions: List[List[float]] = []

        if custom_positions and len(custom_positions) > 0:
            slot_positions = [[float(c) for c in pt] for pt in custom_positions]
        elif placement == "crown_and_temple_3point":
            dx = max(width / 2.0 - inset_from_edge_mm, 5.0)
            z_temple = min_z + height * 0.6
            z_crown = max_z - inset_from_edge_mm
            slot_positions = [
                [-dx, center_y, z_temple],
                [dx, center_y, z_temple],
                [0.0, center_y, z_crown],
            ]
        else:  # temple_bilateral
            dx = max(width / 2.0 - inset_from_edge_mm, 5.0)
            z_temple = min_z + height * 0.55
            slot_positions = [
                [-dx, center_y, z_temple],
                [dx, center_y, z_temple],
            ]

        # Cutter depth (deep box cutter through the mask wall)
        cutter_depth = 80.0
        cutters = []
        for pos in slot_positions:
            box = trimesh.creation.box(extents=[st, cutter_depth, sw])
            box.apply_translation(pos)
            cutters.append(box)

        punched_mesh = mesh.copy()
        if cutters:
            try:
                cutter_union = trimesh.util.concatenate(cutters) if len(cutters) > 1 else cutters[0]
                diff = trimesh.boolean.difference([punched_mesh, cutter_union])
                if diff is not None and len(diff.faces) > 0:
                    punched_mesh = diff
                    punched_mesh.fix_normals()
            except Exception:
                pass

        return punched_mesh, slot_positions, sw, st


masksmith_service = MaskSmithService()
