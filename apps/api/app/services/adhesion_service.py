"""
Mouse-Ear Anti-Warping Brim Generator Service
Generates procedural low-profile corner adhesion discs (mouse-ears) at high-stress vertices.
Inspired by OrcaSlicer's mouse ear bed adhesion feature.
"""

from typing import List, Tuple
import numpy as np
from scipy.spatial import ConvexHull
import trimesh
import trimesh.creation
import trimesh.util

from app.models.calibration import MouseEarPayload


class AdhesionService:
    """Detects acute base corners and attaches anti-warping mouse-ear discs."""

    def generate_mouse_ears(
        self, mesh: trimesh.Trimesh, payload: MouseEarPayload
    ) -> Tuple[trimesh.Trimesh, int, List[List[float]], str]:
        """
        Detects corner vertices at Z=0 and attaches mouse-ear discs.
        Returns: (modified_mesh, ears_count, ear_positions_mm, message)
        """
        radius = payload.radius_mm
        thickness = payload.thickness_mm
        min_z = float(np.min(mesh.vertices[:, 2]))

        # 1. Determine corner coordinates
        corner_coords: List[Tuple[float, float]] = []

        if payload.custom_centers_mm:
            for pt in payload.custom_centers_mm:
                if len(pt) >= 2:
                    corner_coords.append((float(pt[0]), float(pt[1])))
        elif payload.auto_detect_corners:
            corner_coords = self._detect_base_corners(
                mesh=mesh,
                min_z=min_z,
                angle_threshold_deg=payload.corner_angle_threshold_deg,
            )

        if not corner_coords:
            # Fallback to bounding box 4 corners
            bounds = mesh.bounds
            min_x, min_y = bounds[0][0], bounds[0][1]
            max_x, max_y = bounds[1][0], bounds[1][1]
            corner_coords = [
                (min_x, min_y),
                (max_x, min_y),
                (max_x, max_y),
                (min_x, max_y),
            ]

        # 2. Generate circular discs for each corner
        discs = []
        ear_positions: List[List[float]] = []

        for cx, cy in corner_coords:
            # Create cylinder disc with thickness
            disc = trimesh.creation.cylinder(radius=radius, height=thickness, sections=32)
            disc.apply_translation([cx, cy, min_z + thickness / 2.0])
            discs.append(disc)
            ear_positions.append([round(cx, 2), round(cy, 2)])

        # 3. Combine with base mesh
        combined_mesh = trimesh.util.concatenate([mesh] + discs)
        combined_mesh.update_faces(combined_mesh.nondegenerate_faces())

        message = (
            f"Successfully generated {len(discs)} mouse-ear anti-warping tabs "
            f"(Radius: {radius}mm, Thickness: {thickness}mm) at base footprint corners."
        )

        return combined_mesh, len(discs), ear_positions, message

    def _detect_base_corners(
        self, mesh: trimesh.Trimesh, min_z: float, angle_threshold_deg: float
    ) -> List[Tuple[float, float]]:
        """
        Extracts 2D perimeter corners from vertices resting near the build plate.
        """
        # Find vertices within 0.5mm of the bottom build plate
        bottom_mask = mesh.vertices[:, 2] <= (min_z + 0.5)
        bottom_pts_2d = mesh.vertices[bottom_mask, :2]

        if len(bottom_pts_2d) < 3:
            return []

        # Remove duplicate close points
        unique_pts = np.unique(np.round(bottom_pts_2d, 1), axis=0)
        if len(unique_pts) < 3:
            return []

        try:
            hull = ConvexHull(unique_pts)
            hull_pts = unique_pts[hull.vertices]
            n_hull = len(hull_pts)

            corners = []
            thresh_rad = np.radians(angle_threshold_deg)

            for i in range(n_hull):
                p_prev = hull_pts[(i - 1) % n_hull]
                p_curr = hull_pts[i]
                p_next = hull_pts[(i + 1) % n_hull]

                v1 = p_prev - p_curr
                v2 = p_next - p_curr

                len1 = np.linalg.norm(v1)
                len2 = np.linalg.norm(v2)

                if len1 < 1e-4 or len2 < 1e-4:
                    continue

                cos_angle = np.clip(np.dot(v1, v2) / (len1 * len2), -1.0, 1.0)
                interior_angle = np.arccos(cos_angle)

                # If corner angle is sharper than threshold
                if interior_angle <= thresh_rad:
                    corners.append((float(p_curr[0]), float(p_curr[1])))

            return corners
        except Exception:
            return []


adhesion_service = AdhesionService()
