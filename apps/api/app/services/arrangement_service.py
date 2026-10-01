"""
Auto-Arrange / Multi-Model Bed Nesting Service
Positions multiple working models onto the 3D printer build plate with optimal packing and clearance.
Inspired by OrcaSlicer / PrusaSlicer auto-arrange functionality.
"""

from typing import Dict, List, Optional, Tuple
import numpy as np
import trimesh

from app.models.calibration import AutoArrangePayload, ModelPlacement
from app.models.project import MeshBounds, WorkingModel


class ArrangementService:
    """Arranges multiple 3D models onto the build plate using 2D packing with configurable spacing."""

    def arrange(
        self,
        models_data: List[Tuple[WorkingModel, trimesh.Trimesh]],
        payload: AutoArrangePayload,
        printer_bounds: Optional[Tuple[float, float, float]] = None,
    ) -> Tuple[List[Tuple[WorkingModel, trimesh.Trimesh]], List[ModelPlacement], bool, str]:
        """
        Nests and positions models on the build plate.
        Returns: (updated_models_with_meshes, placements, fits_bed, message)
        """
        if not models_data:
            return [], [], True, "No models to arrange"

        spacing = payload.spacing_mm
        bed_w = payload.bed_width_mm or (printer_bounds[0] if printer_bounds else 220.0)
        bed_d = payload.bed_depth_mm or (printer_bounds[1] if printer_bounds else 220.0)

        # 1. Extract 2D bounding boxes for each model (oriented at Z=0)
        items = []
        for wm, mesh in models_data:
            bounds = mesh.bounds
            min_pt, max_pt = bounds[0], bounds[1]
            width = float(max_pt[0] - min_pt[0])
            depth = float(max_pt[1] - min_pt[1])
            height = float(max_pt[2] - min_pt[2])
            items.append({
                "wm": wm,
                "mesh": mesh,
                "id": wm.id,
                "width": width,
                "depth": depth,
                "height": height,
                "area": width * depth,
                "orig_bounds": bounds,
            })

        # Sort items by largest footprint area first (heuristic for efficient packing)
        items.sort(key=lambda x: x["area"], reverse=True)

        # 2. Shelf / Row Packing Algorithm
        placements = []
        placed_rects = []  # List of (x, y, w, d)

        # Estimate grid columns based on square root of count
        num_items = len(items)
        cols = max(1, int(np.ceil(np.sqrt(num_items))))

        current_x = 0.0
        current_y = 0.0
        row_max_depth = 0.0
        col_idx = 0

        for item in items:
            w = item["width"]
            d = item["depth"]

            if col_idx >= cols and current_x > 0:
                # Start new row
                current_x = 0.0
                current_y += row_max_depth + spacing
                row_max_depth = 0.0
                col_idx = 0

            item_x = current_x
            item_y = current_y

            placed_rects.append((item_x, item_y, w, d))
            row_max_depth = max(row_max_depth, d)
            current_x += w + spacing
            col_idx += 1

        # 3. Calculate total bounding box of all placed items
        all_min_x = min(r[0] for r in placed_rects)
        all_max_x = max(r[0] + r[2] for r in placed_rects)
        all_min_y = min(r[1] for r in placed_rects)
        all_max_y = max(r[1] + r[3] for r in placed_rects)

        total_packed_w = all_max_x - all_min_x
        total_packed_d = all_max_y - all_min_y

        # Center offset so that the packed group is centered at (0, 0)
        center_x_offset = -(all_min_x + total_packed_w / 2.0)
        center_y_offset = -(all_min_y + total_packed_d / 2.0)

        # 4. Check if layout fits on the bed
        fits_bed = (total_packed_w <= bed_w) and (total_packed_d <= bed_d)

        # 5. Apply translations to meshes and update working model bounds
        updated_data = []
        placement_records = []

        for i, item in enumerate(items):
            wm = item["wm"]
            mesh = item["mesh"].copy()
            rect = placed_rects[i]

            # Center of the item in packed coordinates
            target_center_x = rect[0] + rect[2] / 2.0 + center_x_offset
            target_center_y = rect[1] + rect[3] / 2.0 + center_y_offset

            # Current mesh center
            curr_bounds = mesh.bounds
            curr_center_xy = (curr_bounds[0][:2] + curr_bounds[1][:2]) / 2.0
            curr_min_z = curr_bounds[0][2]

            # Translate mesh
            dx = target_center_x - curr_center_xy[0]
            dy = target_center_y - curr_center_xy[1]
            dz = -curr_min_z  # align to bed Z=0
            mesh.apply_translation([dx, dy, dz])

            new_bounds = mesh.bounds
            updated_bounds = MeshBounds(
                min=[float(new_bounds[0][0]), float(new_bounds[0][1]), float(new_bounds[0][2])],
                max=[float(new_bounds[1][0]), float(new_bounds[1][1]), float(new_bounds[1][2])],
                dimensions_mm=[
                    float(new_bounds[1][0] - new_bounds[0][0]),
                    float(new_bounds[1][1] - new_bounds[0][1]),
                    float(new_bounds[1][2] - new_bounds[0][2]),
                ],
            )

            # Update working model
            wm_copy = wm.model_copy(update={
                "bounds": updated_bounds,
            })
            wm_copy.transform.position_mm = [target_center_x, target_center_y, 0.0]

            updated_data.append((wm_copy, mesh))

            placement_records.append(
                ModelPlacement(
                    model_id=wm.id,
                    x_offset_mm=round(target_center_x, 2),
                    y_offset_mm=round(target_center_y, 2),
                    rotation_deg=0.0,
                    bounds=updated_bounds,
                )
            )

        status_msg = (
            f"Successfully arranged {len(models_data)} models with {spacing}mm spacing. "
            f"Packed footprint: {total_packed_w:.1f} x {total_packed_d:.1f} mm "
            f"(Bed: {bed_w:.0f} x {bed_d:.0f} mm)."
        )
        if not fits_bed:
            status_msg += " Warning: Total packed footprint exceeds print bed dimensions."

        return updated_data, placement_records, fits_bed, status_msg


arrangement_service = ArrangementService()
