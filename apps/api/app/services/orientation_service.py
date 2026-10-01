"""
Auto-Orient Algorithm for FDM 3D Printing (Support Minimization & Bed Adhesion)
Inspired by OrcaSlicer / PrusaSlicer auto-orientation algorithms.
"""

from typing import List, Tuple
import numpy as np
import trimesh
import trimesh.transformations

from app.models.calibration import AutoOrientPayload


class OrientationService:
    """Calculates optimal build plate orientation to minimize supports, reduce height, and maximize bed contact."""

    def auto_orient(
        self, mesh: trimesh.Trimesh, payload: AutoOrientPayload
    ) -> Tuple[trimesh.Trimesh, List[float], float, float, float]:
        """
        Evaluate candidate orientations and rotate the mesh to optimal position.
        Returns: (oriented_mesh, optimal_rotation_deg, orig_overhang_cm2, opt_overhang_cm2, reduction_pct)
        """
        orig_overhang_cm2 = self._calc_overhang_area_cm2(mesh, payload.critical_angle_deg)

        # 1. Generate candidate rotation matrices
        candidate_rotations = self._generate_candidate_rotations(mesh)

        best_cost = float("inf")
        best_rot_matrix = np.eye(4)
        best_overhang_cm2 = orig_overhang_cm2

        # Model bounding diagonal for normalizing height
        bbox_dims = mesh.extents
        diag = max(float(np.linalg.norm(bbox_dims)), 1.0)
        total_area_cm2 = float(mesh.area) / 100.0

        w_overhang = payload.overhang_weight
        w_height = payload.height_weight
        w_bed = payload.bed_contact_weight
        crit_angle = payload.critical_angle_deg

        for rot_mat in candidate_rotations:
            # Apply candidate rotation to a copy of vertices
            verts_rot = trimesh.transformations.transform_points(mesh.vertices, rot_mat)
            normals_rot = trimesh.transformations.transform_points(
                mesh.face_normals, rot_mat, translate=False
            )

            min_z = float(np.min(verts_rot[:, 2]))
            max_z = float(np.max(verts_rot[:, 2]))
            height = max_z - min_z

            # Overhang evaluation (downward facing faces steeper than critical angle)
            # Normal nz < 0 is downward. Angle from down vector is acos(-nz).
            # If angle > 90 - crit_angle (or nz < -sin(crit_angle)), it needs support.
            down_threshold = -np.sin(np.radians(90.0 - crit_angle))
            overhang_mask = normals_rot[:, 2] < down_threshold
            overhang_area_cm2 = float(np.sum(mesh.area_faces[overhang_mask])) / 100.0

            # Bed contact evaluation (faces within 0.2mm of min_z with normal pointing straight down)
            face_min_z = np.min(verts_rot[mesh.faces, 2], axis=1)
            bed_mask = (face_min_z <= min_z + 0.3) & (normals_rot[:, 2] < -0.8)
            bed_contact_cm2 = float(np.sum(mesh.area_faces[bed_mask])) / 100.0

            # Penalty cost function
            norm_height_penalty = (height / diag) * total_area_cm2
            cost = (
                (w_overhang * overhang_area_cm2)
                + (w_height * norm_height_penalty)
                - (w_bed * bed_contact_cm2)
            )

            if cost < best_cost:
                best_cost = cost
                best_rot_matrix = rot_mat
                best_overhang_cm2 = overhang_area_cm2

        # 2. Apply best rotation to mesh
        oriented_mesh = mesh.copy()
        oriented_mesh.apply_transform(best_rot_matrix)

        # 3. Translate so center XY is (0, 0) and min Z is 0.0
        bounds = oriented_mesh.bounds
        center_xy = (bounds[0][:2] + bounds[1][:2]) / 2.0
        min_z = bounds[0][2]
        oriented_mesh.apply_translation([-center_xy[0], -center_xy[1], -min_z])

        # 4. Extract Euler angles in degrees (XYZ convention)
        euler_rad = trimesh.transformations.euler_from_matrix(best_rot_matrix, "rxyz")
        rot_deg = [float(np.round(np.degrees(a), 2)) for a in euler_rad]

        # 5. Compute reduction percentage
        if orig_overhang_cm2 > 1e-4:
            reduction_pct = max(0.0, ((orig_overhang_cm2 - best_overhang_cm2) / orig_overhang_cm2) * 100.0)
        else:
            reduction_pct = 0.0

        return oriented_mesh, rot_deg, orig_overhang_cm2, best_overhang_cm2, reduction_pct

    def _generate_candidate_rotations(self, mesh: trimesh.Trimesh) -> List[np.ndarray]:
        """
        Generate candidate 3D rotation matrices based on convex hull face normals and orthogonal axes.
        """
        rotations = [np.eye(4)]

        # 1. Cardinal / Orthogonal 90-degree rotations
        angles = [0.0, 90.0, 180.0, 270.0]
        for rx in angles:
            for ry in angles:
                if rx == 0.0 and ry == 0.0:
                    continue
                mat = trimesh.transformations.euler_matrix(
                    np.radians(rx), np.radians(ry), 0.0, "rxyz"
                )
                rotations.append(mat)

        # 2. Convex hull facet normal alignments (aligning each candidate resting face to -Z)
        try:
            hull = mesh.convex_hull
            # Sample up to 30 largest faces of the convex hull
            face_areas = hull.area_faces
            top_indices = np.argsort(face_areas)[::-1][:30]

            down_vec = np.array([0.0, 0.0, -1.0])

            for idx in top_indices:
                normal = hull.face_normals[idx]
                norm_len = np.linalg.norm(normal)
                if norm_len < 1e-6:
                    continue
                normal = normal / norm_len

                # Rotation aligning normal to [0, 0, -1]
                rot_mat = trimesh.geometry.align_vectors(normal, down_vec)
                rotations.append(rot_mat)
        except Exception:
            pass

        return rotations

    def _calc_overhang_area_cm2(self, mesh: trimesh.Trimesh, crit_angle: float) -> float:
        """Calculate total surface area requiring support under current orientation."""
        down_threshold = -np.sin(np.radians(90.0 - crit_angle))
        overhang_mask = mesh.face_normals[:, 2] < down_threshold
        return float(np.sum(mesh.area_faces[overhang_mask])) / 100.0


orientation_service = OrientationService()
