import io
import json
import os
import re
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union
import numpy as np
import trimesh
from fastapi import HTTPException, status

from app.core.config import settings
from app.models.mesh import (
    CostEstimationPayload,
    CostEstimationResult,
    ExportModelPayload,
    ExportResult,
    FloatingIslandModel,
    IslandAnalysisPayload,
    IslandAnalysisResult,
    MeshAnalysisResult,
    MeshRepairReport,
    OverhangAnalysisResult,
    RotateModelPayload,
    ScaleModelPayload,
    SliceModelPayload,
    SliceModelResult,
    ThinRegionModel,
    ThinWallAnalysisPayload,
    ThinWallAnalysisResult,
)
from app.models.project import MeshBounds, MeshTransform

ALLOWED_EXTENSIONS: Set[str] = {"stl", "obj", "glb", "gltf", "3mf"}
MAX_FILE_SIZE_BYTES: int = settings.MAX_UPLOAD_SIZE_BYTES


class MeshValidationError(HTTPException):
    def __init__(self, detail: str = "Invalid 3D mesh input"):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


class MeshProcessingError(HTTPException):
    def __init__(self, detail: str = "Failed to process 3D mesh"):
        super().__init__(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=detail)


def sanitize_and_validate_filename(filename: Optional[str], allowed_extensions: Optional[Set[str]] = None) -> str:
    """
    Validate that filename is safe, free of directory traversal, and contains an allowed 3D extension.
    """
    if not filename or not isinstance(filename, str):
        raise MeshValidationError("Filename cannot be empty or null.")

    if "\0" in filename:
        raise MeshValidationError("Filename contains null byte.")

    if "/" in filename or "\\" in filename or ".." in filename:
        raise MeshValidationError("Filename contains directory traversal components.")

    if os.path.isabs(filename) or (len(filename) > 1 and filename[1] == ":"):
        raise MeshValidationError("Absolute paths are not permitted.")

    allowed = allowed_extensions or ALLOWED_EXTENSIONS
    ext = Path(filename).suffix.lower().lstrip(".")
    if not ext or ext not in allowed:
        raise MeshValidationError(f"Disallowed extension '.{ext}'. Allowed: {', '.join(sorted(allowed))}")

    return filename


class MeshService:
    @staticmethod
    def load_mesh(
        file_or_bytes_or_stream: Union[str, Path, bytes, bytearray, io.BytesIO],
        filename: Optional[str] = None,
    ) -> trimesh.Trimesh:
        """
        Load a 3D mesh from filepath, raw bytes, or BytesIO stream.
        """
        if file_or_bytes_or_stream is None:
            raise MeshValidationError("File content is empty.")

        file_type = None
        if filename:
            file_type = Path(filename).suffix.lower().lstrip(".")

        try:
            if isinstance(file_or_bytes_or_stream, (bytes, bytearray)):
                if len(file_or_bytes_or_stream) == 0:
                    raise MeshValidationError("File is empty (0 bytes).")
                stream = io.BytesIO(file_or_bytes_or_stream)
                loaded = trimesh.load(stream, file_type=file_type or "stl")
            elif isinstance(file_or_bytes_or_stream, io.BytesIO):
                stream_content = file_or_bytes_or_stream.getvalue()
                if len(stream_content) == 0:
                    raise MeshValidationError("File is empty (0 bytes).")
                file_or_bytes_or_stream.seek(0)
                loaded = trimesh.load(file_or_bytes_or_stream, file_type=file_type or "stl")
            elif isinstance(file_or_bytes_or_stream, (str, Path)):
                p = Path(file_or_bytes_or_stream)
                if not p.exists():
                    raise MeshValidationError(f"File '{p}' does not exist.")
                if p.stat().st_size == 0:
                    raise MeshValidationError("File is empty (0 bytes).")
                loaded = trimesh.load(str(p), file_type=file_type)
            else:
                raise MeshValidationError("Unsupported input type for mesh loading.")
        except MeshValidationError:
            raise
        except Exception as e:
            raise MeshProcessingError(f"Failed to parse 3D mesh geometry: {str(e)}")

        if isinstance(loaded, trimesh.Scene):
            if not loaded.geometry:
                raise MeshValidationError("Loaded 3D file contains no valid mesh geometry.")
            if len(loaded.geometry) == 1:
                mesh = list(loaded.geometry.values())[0]
            else:
                mesh = trimesh.util.concatenate(tuple(loaded.geometry.values()))
        elif isinstance(loaded, trimesh.Trimesh):
            mesh = loaded
        else:
            raise MeshValidationError("Unsupported 3D geometry object type.")

        if len(mesh.faces) == 0 or len(mesh.vertices) == 0:
            raise MeshProcessingError("Parsed mesh has zero faces or vertices.")

        return mesh

    @staticmethod
    def analyze_mesh(mesh: trimesh.Trimesh) -> MeshAnalysisResult:
        """
        Perform computational analysis on a Trimesh geometry.
        Returns MeshAnalysisResult containing bounding extents, vertex/face count, surface area, and volume.
        """
        bounds_min = [float(val) for val in mesh.bounds[0]]
        bounds_max = [float(val) for val in mesh.bounds[1]]
        extents = [float(val) for val in mesh.extents]

        triangle_count = int(len(mesh.faces))
        vertex_count = int(len(mesh.vertices))

        # Surface area: convert mm^2 to cm^2 (divide by 100)
        surface_area_cm2 = round(float(mesh.area) / 100.0, 4)

        # Volume: convert mm^3 to cm^3 (divide by 1000) only if watertight
        is_watertight = bool(mesh.is_watertight)
        volume_cm3 = None
        if is_watertight:
            try:
                raw_vol = float(mesh.volume)
                if raw_vol > 0:
                    volume_cm3 = round(raw_vol / 1000.0, 4)
            except Exception:
                volume_cm3 = None

        return MeshAnalysisResult(
            bounds=MeshBounds(
                min=bounds_min,
                max=bounds_max,
                dimensions_mm=extents,
            ),
            triangle_count=triangle_count,
            vertex_count=vertex_count,
            surface_area_cm2=surface_area_cm2,
            volume_cm3=volume_cm3,
            is_watertight=is_watertight,
        )

    @staticmethod
    def scale_mesh(
        mesh: trimesh.Trimesh,
        payload_or_percent: Optional[Union[ScaleModelPayload, float]] = None,
        target_h: Optional[float] = None,
        target_w: Optional[float] = None,
        target_d: Optional[float] = None,
        preserve_aspect: bool = True,
    ) -> trimesh.Trimesh:
        """
        Scale mesh geometry deterministically.
        Supports passing ScaleModelPayload directly or keyword arguments.
        """
        if hasattr(payload_or_percent, "uniform_scale_percent") or hasattr(payload_or_percent, "preserve_aspect_ratio"):
            uniform_percent = getattr(payload_or_percent, "uniform_scale_percent", None)
            target_h = getattr(payload_or_percent, "target_height_mm", None)
            target_w = getattr(payload_or_percent, "target_width_mm", None)
            target_d = getattr(payload_or_percent, "target_depth_mm", None)
            preserve_aspect = getattr(payload_or_percent, "preserve_aspect_ratio", True)
        elif isinstance(payload_or_percent, (int, float)):
            uniform_percent = float(payload_or_percent)
        else:
            uniform_percent = None


        # Validation
        if uniform_percent is not None and uniform_percent <= 0:
            raise MeshValidationError("Uniform scale percentage must be positive and greater than zero.")
        if target_h is not None and target_h <= 0:
            raise MeshValidationError("Target height must be positive and greater than zero.")
        if target_w is not None and target_w <= 0:
            raise MeshValidationError("Target width must be positive and greater than zero.")
        if target_d is not None and target_d <= 0:
            raise MeshValidationError("Target depth must be positive and greater than zero.")

        scaled_mesh = mesh.copy()
        current_w, current_d, current_h = [float(v) for v in scaled_mesh.extents]

        if current_w <= 0:
            current_w = 1.0
        if current_d <= 0:
            current_d = 1.0
        if current_h <= 0:
            current_h = 1.0

        if uniform_percent is not None and uniform_percent > 0:
            factor = float(uniform_percent) / 100.0
            scaled_mesh.apply_scale(factor)
        else:
            if preserve_aspect:
                factor = 1.0
                if target_h is not None and target_h > 0:
                    factor = float(target_h) / current_h
                elif target_w is not None and target_w > 0:
                    factor = float(target_w) / current_w
                elif target_d is not None and target_d > 0:
                    factor = float(target_d) / current_d

                scaled_mesh.apply_scale(factor)
            else:
                sx = (float(target_w) / current_w) if (target_w is not None and target_w > 0) else 1.0
                sy = (float(target_d) / current_d) if (target_d is not None and target_d > 0) else 1.0
                sz = (float(target_h) / current_h) if (target_h is not None and target_h > 0) else 1.0

                transform_matrix = np.diag([sx, sy, sz, 1.0])
                scaled_mesh.apply_transform(transform_matrix)

        return scaled_mesh

    @staticmethod
    def scale_mesh_with_transform(
        mesh: trimesh.Trimesh,
        payload_or_percent: Optional[Union[ScaleModelPayload, float]] = None,
        target_h: Optional[float] = None,
        target_w: Optional[float] = None,
        target_d: Optional[float] = None,
        preserve_aspect: bool = True,
    ) -> Tuple[trimesh.Trimesh, MeshTransform]:
        """
        Scale mesh and compute associated MeshTransform metadata.
        """
        if hasattr(payload_or_percent, "uniform_scale_percent") or hasattr(payload_or_percent, "preserve_aspect_ratio"):
            uniform_percent = getattr(payload_or_percent, "uniform_scale_percent", None)
            target_h = getattr(payload_or_percent, "target_height_mm", None)
            target_w = getattr(payload_or_percent, "target_width_mm", None)
            target_d = getattr(payload_or_percent, "target_depth_mm", None)
            preserve_aspect = getattr(payload_or_percent, "preserve_aspect_ratio", True)
        elif isinstance(payload_or_percent, (int, float)):
            uniform_percent = float(payload_or_percent)
        else:
            uniform_percent = None


        scaled = MeshService.scale_mesh(
            mesh=mesh,
            payload_or_percent=payload_or_percent,
            target_h=target_h,
            target_w=target_w,
            target_d=target_d,
            preserve_aspect=preserve_aspect,
        )

        orig_w, orig_d, orig_h = [float(v) for v in mesh.extents]
        new_w, new_d, new_h = [float(v) for v in scaled.extents]

        sx = new_w / orig_w if orig_w > 0 else 1.0
        sy = new_d / orig_d if orig_d > 0 else 1.0
        sz = new_h / orig_h if orig_h > 0 else 1.0

        uniform_scale = float(uniform_percent) if uniform_percent is not None else round(((sx + sy + sz) / 3.0) * 100.0, 2)

        transform = MeshTransform(
            position_mm=[0.0, 0.0, 0.0],
            rotation_deg=[0.0, 0.0, 0.0],
            scale_factors=[round(sx, 4), round(sy, 4), round(sz, 4)],
            uniform_scale_percent=uniform_scale,
        )

        return scaled, transform

    @staticmethod
    def export_mesh(
        mesh: trimesh.Trimesh,
        destination: Union[str, Path],
        payload_or_format: Optional[Union[ExportModelPayload, str]] = None,
        format: Optional[str] = None,
        file_format: Optional[str] = None,
        payload: Optional[ExportModelPayload] = None,
    ) -> Union[ExportResult, Path]:
        """
        Export mesh to STL (binary), OBJ, or GLB.
        Handles directory output with ExportModelPayload and direct filepath output with format string.
        """
        effective_payload = payload if isinstance(payload, ExportModelPayload) else (payload_or_format if isinstance(payload_or_format, ExportModelPayload) else None)
        effective_format = format or file_format or (str(payload_or_format) if isinstance(payload_or_format, str) else None)

        if effective_payload is not None:
            export_dir = Path(destination)
            fmt = effective_payload.format.lower().lstrip(".")
            custom_name = effective_payload.filename or f"exported_model.{fmt}"

            # Security check on filename
            sanitize_and_validate_filename(custom_name)

            out_path = (export_dir / custom_name).resolve()
            export_dir.mkdir(parents=True, exist_ok=True)

            if fmt == "stl":
                mesh.export(str(out_path), file_type="stl")
            elif fmt == "obj":
                mesh.export(str(out_path), file_type="obj")
            elif fmt in ("glb", "gltf"):
                mesh.export(str(out_path), file_type="glb")
            elif fmt == "3mf":
                MeshService.export_project_3mf(
                    models_data=[{"mesh": mesh, "filename": custom_name}],
                    destination=out_path,
                )
            else:
                raise MeshValidationError(f"Unsupported export format: '{fmt}'")

            file_size = out_path.stat().st_size
            return ExportResult(
                export_path=str(out_path),
                filename=custom_name,
                format=fmt,
                file_size_bytes=file_size,
            )
        else:
            out_p = Path(destination)
            fmt = (effective_format or "stl").lower().lstrip(".")
            out_p.parent.mkdir(parents=True, exist_ok=True)

            if fmt == "stl":
                mesh.export(str(out_p), file_type="stl")
            elif fmt == "obj":
                mesh.export(str(out_p), file_type="obj")
            elif fmt in ("glb", "gltf"):
                mesh.export(str(out_p), file_type="glb")
            elif fmt == "3mf":
                MeshService.export_project_3mf(
                    models_data=[{"mesh": mesh, "filename": out_p.name}],
                    destination=out_p,
                )
            else:
                raise MeshValidationError(f"Unsupported export format: '{fmt}'")

            return out_p

    @staticmethod
    def rotate_mesh(
        mesh: trimesh.Trimesh,
        rx_deg: float = 0.0,
        ry_deg: float = 0.0,
        rz_deg: float = 0.0,
    ) -> trimesh.Trimesh:
        """
        Rotate mesh geometry around X, Y, and Z axes by Euler degrees around its centroid,
        and ensure the model is grounded on the build bed (Z_min = 0).
        Returns rotated trimesh with updated bounds.
        """
        rotated = mesh.copy()
        rx = float(rx_deg or 0.0)
        ry = float(ry_deg or 0.0)
        rz = float(rz_deg or 0.0)

        if rx != 0.0 or ry != 0.0 or rz != 0.0:
            center = rotated.centroid
            rotated.apply_translation(-center)
            rot_matrix = trimesh.transformations.euler_matrix(
                np.radians(rx),
                np.radians(ry),
                np.radians(rz),
                axes="sxyz",
            )
            rotated.apply_transform(rot_matrix)
            rotated.apply_translation(center)

            # Re-ground base to Z_min = 0
            min_z = float(rotated.bounds[0][2])
            rotated.apply_translation([0.0, 0.0, -min_z])

        return rotated

    @staticmethod
    def center_mesh_on_bed(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
        """
        Translate mesh so center of bounding box in (X,Y) is at (0,0) and minimum Z is 0.0.
        """
        centered = mesh.copy()
        bounds_min = centered.bounds[0]
        bounds_max = centered.bounds[1]

        center_x = float(bounds_min[0] + bounds_max[0]) / 2.0
        center_y = float(bounds_min[1] + bounds_max[1]) / 2.0
        min_z = float(bounds_min[2])

        translation = np.array([-center_x, -center_y, -min_z], dtype=float)
        centered.apply_translation(translation)
        return centered

    @staticmethod
    def lay_flat_mesh(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
        """
        Find the largest planar convex hull face or base facet and rotate it to lie on the Z=0 plane.
        """
        flat_mesh = mesh.copy()
        if len(flat_mesh.faces) == 0:
            return flat_mesh

        try:
            target_geom = flat_mesh.convex_hull if len(flat_mesh.vertices) >= 4 else flat_mesh
        except Exception:
            target_geom = flat_mesh

        normals = target_geom.face_normals
        areas = target_geom.area_faces
        vertices = target_geom.vertices[target_geom.faces[:, 0]]

        if len(normals) == 0 or len(areas) == 0:
            return MeshService.center_mesh_on_bed(flat_mesh)

        # Plane offsets d = -dot(n, v)
        d = -np.einsum("ij,ij->i", normals, vertices)

        # Group coplanar faces to identify the largest facet area
        groups: List[Tuple[float, np.ndarray]] = []
        used = set()
        for i in range(len(normals)):
            if i in used:
                continue
            cos_sim = np.dot(normals, normals[i])
            dist_diff = np.abs(d - d[i])
            match = np.where((cos_sim > 0.99) & (dist_diff < 1e-2))[0]
            total_area = float(np.sum(areas[match]))
            groups.append((total_area, normals[i]))
            for idx in match:
                used.add(idx)

        if not groups:
            return MeshService.center_mesh_on_bed(flat_mesh)

        groups.sort(key=lambda x: x[0], reverse=True)
        best_area, best_normal = groups[0]

        # Outward normal of bottom face should point downwards [0, 0, -1]
        target_normal = np.array([0.0, 0.0, -1.0], dtype=float)
        norm_val = np.linalg.norm(best_normal)
        if norm_val > 1e-6:
            unit_normal = best_normal / norm_val
            align_matrix = trimesh.geometry.align_vectors(unit_normal, target_normal)
            flat_mesh.apply_transform(align_matrix)

        # Position on bed so min Z = 0 and (X,Y) centered at (0,0)
        return MeshService.center_mesh_on_bed(flat_mesh)

    @staticmethod
    def analyze_overhangs(
        mesh: trimesh.Trimesh,
        critical_angle_deg: float = 45.0,
    ) -> OverhangAnalysisResult:
        """
        Analyze geometry and compute the percentage of downward-facing facets
        steeper than the critical angle requiring support structures.
        """
        if mesh is None or len(mesh.faces) == 0:
            return OverhangAnalysisResult(
                critical_angle_deg=critical_angle_deg,
                overhang_percentage=0.0,
                overhang_area_cm2=0.0,
                total_area_cm2=0.0,
                overhang_face_count=0,
                total_face_count=0,
                requires_support=False,
            )

        normals = mesh.face_normals
        areas = mesh.area_faces

        total_area_mm2 = float(np.sum(areas))
        total_area_cm2 = round(total_area_mm2 / 100.0, 4)
        total_faces = int(len(mesh.faces))

        crit_rad = np.radians(float(critical_angle_deg))
        threshold_nz = -float(np.sin(crit_rad))

        overhang_mask = normals[:, 2] < threshold_nz
        overhang_faces = int(np.sum(overhang_mask))
        overhang_area_mm2 = float(np.sum(areas[overhang_mask]))
        overhang_area_cm2 = round(overhang_area_mm2 / 100.0, 4)

        overhang_pct = round((overhang_area_mm2 / total_area_mm2 * 100.0), 2) if total_area_mm2 > 0 else 0.0
        requires_support = overhang_faces > 0

        return OverhangAnalysisResult(
            critical_angle_deg=critical_angle_deg,
            overhang_percentage=overhang_pct,
            overhang_area_cm2=overhang_area_cm2,
            total_area_cm2=total_area_cm2,
            overhang_face_count=overhang_faces,
            total_face_count=total_faces,
            requires_support=requires_support,
        )

    @staticmethod
    def slice_mesh(
        mesh: trimesh.Trimesh,
        plane_origin: Optional[Union[List[float], Tuple[float, float, float], np.ndarray]] = None,
        plane_normal: Optional[Union[List[float], Tuple[float, float, float], np.ndarray]] = None,
        cap_faces: bool = True,
        create_pegs: bool = False,
        peg_radius_mm: float = 3.0,
        peg_height_mm: float = 6.0,
        peg_clearance_mm: float = 0.2,
    ) -> Tuple[trimesh.Trimesh, trimesh.Trimesh, float]:
        """
        Split a mesh into top and bottom watertight halves along an arbitrary planar slice.
        Optionally generates interlocking alignment dowel pegs and sockets on mating cut faces.
        Returns: (top_mesh, bottom_mesh, cut_area_cm2)
        """
        if mesh is None or len(mesh.faces) == 0:
            raise MeshValidationError("Cannot slice empty mesh.")

        # Default origin is bounding box centroid
        if plane_origin is None:
            origin = np.array(mesh.centroid, dtype=float)
        else:
            origin = np.array(plane_origin, dtype=float)

        # Default normal is Z-up [0, 0, 1]
        if plane_normal is None:
            normal = np.array([0.0, 0.0, 1.0], dtype=float)
        else:
            normal = np.array(plane_normal, dtype=float)

        norm_len = np.linalg.norm(normal)
        if norm_len < 1e-6:
            normal = np.array([0.0, 0.0, 1.0], dtype=float)
        else:
            normal = normal / norm_len

        # Slice positive half (above cut plane)
        try:
            top_slice = trimesh.intersections.slice_mesh_plane(
                mesh=mesh,
                plane_normal=normal,
                plane_origin=origin,
                cap=cap_faces,
            )
        except Exception:
            top_slice = trimesh.intersections.slice_mesh_plane(
                mesh=mesh,
                plane_normal=normal,
                plane_origin=origin,
                cap=False,
            )

        # Slice negative half (below cut plane)
        try:
            bottom_slice = trimesh.intersections.slice_mesh_plane(
                mesh=mesh,
                plane_normal=-normal,
                plane_origin=origin,
                cap=cap_faces,
            )
        except Exception:
            bottom_slice = trimesh.intersections.slice_mesh_plane(
                mesh=mesh,
                plane_normal=-normal,
                plane_origin=origin,
                cap=False,
            )

        if top_slice is None or len(top_slice.faces) == 0:
            raise MeshProcessingError("Cut plane does not intersect mesh: top slice is empty.")
        if bottom_slice is None or len(bottom_slice.faces) == 0:
            raise MeshProcessingError("Cut plane does not intersect mesh: bottom slice is empty.")

        # Ensure vertex normals are computed
        top_slice.fix_normals()
        bottom_slice.fix_normals()

        # Compute cut boundary area approximately (difference in surface area)
        cut_area_mm2 = max(0.0, (float(top_slice.area) + float(bottom_slice.area) - float(mesh.area)) / 2.0)
        cut_area_cm2 = round(cut_area_mm2 / 100.0, 4)

        # Optional alignment peg / socket connector generation
        if create_pegs and peg_radius_mm > 0 and peg_height_mm > 0:
            try:
                # Generate peg cylinder on bottom slice, hole cylinder on top slice
                z_axis = np.array([0.0, 0.0, 1.0])
                align_mat = trimesh.geometry.align_vectors(z_axis, normal)

                # Peg cylinder (positive on bottom mating face)
                peg = trimesh.creation.cylinder(radius=peg_radius_mm, height=peg_height_mm)
                peg.apply_translation([0, 0, peg_height_mm / 2.0])
                peg.apply_transform(align_mat)
                peg.apply_translation(origin)

                # Socket hole (slightly enlarged with clearance tolerance)
                hole_radius = peg_radius_mm + peg_clearance_mm
                hole_height = peg_height_mm + 1.0
                socket = trimesh.creation.cylinder(radius=hole_radius, height=hole_height)
                socket.apply_translation([0, 0, hole_height / 2.0])
                socket.apply_transform(align_mat)
                socket.apply_translation(origin)

                # Union peg with bottom half
                bottom_with_peg = trimesh.boolean.union([bottom_slice, peg])
                if bottom_with_peg is not None and len(bottom_with_peg.faces) > 0:
                    bottom_slice = bottom_with_peg

                # Difference socket from top half
                top_with_socket = trimesh.boolean.difference([top_slice, socket])
                if top_with_socket is not None and len(top_with_socket.faces) > 0:
                    top_slice = top_with_socket
            except Exception:
                # Fallback cleanly to standard cut without boolean failure
                pass

        return top_slice, bottom_slice, cut_area_cm2

    @staticmethod
    def repair_mesh(
        mesh: trimesh.Trimesh,
        fill_holes: bool = True,
        fix_normals: bool = True,
        remove_degenerate: bool = True,
        weld_vertices: bool = True,
        weld_tolerance_mm: float = 0.001,
    ) -> Tuple[trimesh.Trimesh, MeshRepairReport]:
        """
        Automated mesh repair and geometric healing:
        - Removes degenerate zero-area faces and duplicate triangles
        - Merges coincident vertices
        - Unifies vertex winding order and fixes inverted normals
        - Fills and triangulates open boundary holes to restore watertight manifold topology
        """
        if mesh is None or len(mesh.faces) == 0:
            raise MeshValidationError("Cannot repair empty mesh.")

        repaired = mesh.copy()
        triangles_before = int(len(repaired.faces))
        is_watertight_before = bool(repaired.is_watertight)
        duplicate_vertices_welded = 0
        degenerate_faces_removed = 0
        holes_filled_count = 0
        inverted_normals_fixed = False

        # 1. Weld coincident vertices
        if weld_vertices:
            v_before = len(repaired.vertices)
            repaired.merge_vertices(merge_tex=True, merge_norm=True, digits_vertex=5)
            duplicate_vertices_welded = max(0, v_before - len(repaired.vertices))

        # 2. Remove degenerate / duplicate faces
        if remove_degenerate:
            f_before = len(repaired.faces)
            repaired.update_faces(repaired.nondegenerate_faces())
            repaired.update_faces(repaired.unique_faces())
            repaired.remove_unreferenced_vertices()
            degenerate_faces_removed = max(0, f_before - len(repaired.faces))

        # 3. Fill boundary holes
        if fill_holes:
            try:
                trimesh.repair.fill_holes(repaired)
                if not repaired.is_watertight:
                    trimesh.repair.stitch(repaired)
                holes_filled_count = max(0, len(repaired.faces) - (triangles_before - degenerate_faces_removed))
            except Exception:
                pass

        # 4. Fix normals and winding order
        if fix_normals:
            try:
                trimesh.repair.fix_inversion(repaired)
                trimesh.repair.fix_winding(repaired)
                trimesh.repair.fix_normals(repaired)
                repaired.fix_normals()
                inverted_normals_fixed = True
            except Exception:
                pass

        triangles_after = int(len(repaired.faces))
        is_watertight_after = bool(repaired.is_watertight)
        volume_restored_cm3 = None
        if is_watertight_after and repaired.volume is not None and repaired.volume > 0:
            volume_restored_cm3 = round(float(repaired.volume) / 1000.0, 4)

        report = MeshRepairReport(
            holes_filled=holes_filled_count,
            degenerate_faces_removed=degenerate_faces_removed,
            duplicate_vertices_welded=duplicate_vertices_welded,
            inverted_normals_fixed=inverted_normals_fixed,
            is_watertight_before=is_watertight_before,
            is_watertight_after=is_watertight_after,
            triangle_count_before=triangles_before,
            triangle_count_after=triangles_after,
            volume_restored_cm3=volume_restored_cm3,
        )

        return repaired, report

    @staticmethod
    def hollow_mesh(
        mesh: trimesh.Trimesh,
        wall_thickness_mm: float = 2.0,
        add_drain_holes: bool = True,
        drain_hole_radius_mm: float = 2.0,
        drain_hole_count: int = 2,
    ) -> Tuple[trimesh.Trimesh, Optional[float], int]:
        """
        Hollow out a solid 3D mesh with specified wall thickness and optional bottom drain holes.
        Returns: (hollowed_mesh, volume_saved_cm3, drain_holes_added)
        """
        if mesh is None or len(mesh.faces) == 0:
            raise MeshValidationError("Cannot hollow empty mesh.")

        original_vol_cm3 = None
        if mesh.is_watertight and mesh.volume is not None and mesh.volume > 0:
            original_vol_cm3 = float(mesh.volume) / 1000.0

        outer = mesh.copy()
        min_extent = float(min(outer.extents))
        safe_thickness = min(float(wall_thickness_mm), max(0.5, min_extent * 0.4))

        inner = outer.copy()
        if len(inner.vertex_normals) == len(inner.vertices):
            inner.vertices -= inner.vertex_normals * safe_thickness
        else:
            centroid = inner.centroid
            inner.vertices = centroid + (inner.vertices - centroid) * max(0.1, (1.0 - (safe_thickness / (min_extent / 2.0))))

        inner.faces = np.fliplr(inner.faces)
        inner.fix_normals()

        hollowed = trimesh.util.concatenate([outer, inner])
        hollowed.fix_normals()

        drain_holes_added = 0
        if add_drain_holes and drain_hole_radius_mm > 0:
            try:
                bounds_min = hollowed.bounds[0]
                bounds_max = hollowed.bounds[1]
                base_z = float(bounds_min[2])
                center_x = float(bounds_min[0] + bounds_max[0]) / 2.0
                center_y = float(bounds_min[1] + bounds_max[1]) / 2.0
                width = float(bounds_max[0] - bounds_min[0])
                depth = float(bounds_max[1] - bounds_min[1])

                hole_height = safe_thickness * 4.0 + 2.0
                cylinders = []

                offsets = []
                if drain_hole_count <= 1:
                    offsets.append((0.0, 0.0))
                elif drain_hole_count == 2:
                    dx = min(width * 0.25, 15.0)
                    offsets.extend([(-dx, 0.0), (dx, 0.0)])
                elif drain_hole_count == 3:
                    r = min(min(width, depth) * 0.25, 15.0)
                    for angle in [0, 120, 240]:
                        rad = np.radians(angle)
                        offsets.append((r * np.cos(rad), r * np.sin(rad)))
                else:
                    dx = min(width * 0.25, 15.0)
                    dy = min(depth * 0.25, 15.0)
                    offsets.extend([(-dx, -dy), (dx, -dy), (dx, dy), (-dx, dy)])

                for ox, oy in offsets[:drain_hole_count]:
                    cyl = trimesh.creation.cylinder(radius=drain_hole_radius_mm, height=hole_height)
                    cyl.apply_translation([center_x + ox, center_y + oy, base_z])
                    cylinders.append(cyl)

                if cylinders:
                    cutters = trimesh.util.concatenate(cylinders) if len(cylinders) > 1 else cylinders[0]
                    holed = trimesh.boolean.difference([hollowed, cutters])
                    if holed is not None and len(holed.faces) > 0:
                        hollowed = holed
                        drain_holes_added = len(offsets[:drain_hole_count])
            except Exception:
                drain_holes_added = 0

        volume_saved_cm3 = None
        if original_vol_cm3 is not None:
            try:
                inner_test = outer.copy()
                inner_test.vertices -= inner_test.vertex_normals * safe_thickness
                if inner_test.is_watertight and inner_test.volume is not None and inner_test.volume > 0:
                    volume_saved_cm3 = round(float(inner_test.volume) / 1000.0, 4)
                else:
                    volume_saved_cm3 = round(original_vol_cm3 * 0.65, 4)
            except Exception:
                volume_saved_cm3 = round(original_vol_cm3 * 0.65, 4)

        return hollowed, volume_saved_cm3, drain_holes_added

    @staticmethod
    def arrange_models_on_bed(
        models_data: List[Dict[str, Any]],
        bed_width_mm: float = 220.0,
        bed_depth_mm: float = 220.0,
        spacing_mm: float = 5.0,
        bed_margin_mm: float = 10.0,
    ) -> Tuple[List[Dict[str, Any]], bool]:
        """
        2D Shelf-packing algorithm to arrange multiple 3D models collision-free on the build plate.
        models_data is a list of dicts: {"model_id": str, "filename": str, "mesh": trimesh.Trimesh or "bounds_dimensions": [w, d, h]}
        Returns: (placements: list of {"model_id", "filename", "position_mm", "rotation_deg"}, all_fit: bool)
        """
        if not models_data:
            return [], True

        usable_w = bed_width_mm - 2 * bed_margin_mm
        usable_d = bed_depth_mm - 2 * bed_margin_mm

        items = []
        for item in models_data:
            mid = item.get("model_id", "")
            fname = item.get("filename", "model.stl")
            mesh = item.get("mesh")
            if mesh is not None:
                w, d, h = [float(v) for v in mesh.extents]
                min_z = float(mesh.bounds[0][2])
            elif "bounds_dimensions" in item:
                w, d, h = [float(v) for v in item["bounds_dimensions"]]
                min_z = 0.0
            elif "dimensions" in item:
                w, d, h = [float(v) for v in item["dimensions"]]
                min_z = 0.0
            else:
                w, d, h = (50.0, 50.0, 50.0)
                min_z = 0.0
            items.append({
                "model_id": mid,
                "filename": fname,
                "w": w,
                "d": d,
                "h": h,
                "min_z": min_z,
                "mesh": mesh,
            })

        items.sort(key=lambda it: it["d"], reverse=True)

        current_x = 0.0
        current_y = 0.0
        row_height = 0.0

        placed_rects = []
        for it in items:
            w = it["w"]
            d = it["d"]

            if current_x + w > usable_w and current_x > 0:
                current_x = 0.0
                current_y += row_height + spacing_mm
                row_height = 0.0

            pos_x = current_x + w / 2.0
            pos_y = current_y + d / 2.0
            row_height = max(row_height, d)
            current_x += w + spacing_mm

            placed_rects.append({
                "item": it,
                "x_center": pos_x,
                "y_center": pos_y,
                "x_min": current_x - w - spacing_mm,
                "x_max": current_x - spacing_mm,
                "y_min": current_y,
                "y_max": current_y + d,
            })

        if placed_rects:
            all_x_min = min(r["x_min"] for r in placed_rects)
            all_x_max = max(r["x_max"] for r in placed_rects)
            all_y_min = min(r["y_min"] for r in placed_rects)
            all_y_max = max(r["y_max"] for r in placed_rects)

            packed_center_x = (all_x_min + all_x_max) / 2.0
            packed_center_y = (all_y_min + all_y_max) / 2.0
            packed_width = all_x_max - all_x_min
            packed_depth = all_y_max - all_y_min

            all_fit = (packed_width <= usable_w) and (packed_depth <= usable_d)
        else:
            packed_center_x = 0.0
            packed_center_y = 0.0
            all_fit = True

        placements = []
        for r in placed_rects:
            it = r["item"]
            centered_x = round(float(r["x_center"] - packed_center_x), 2)
            centered_y = round(float(r["y_center"] - packed_center_y), 2)
            centered_z = 0.0

            placements.append({
                "model_id": it["model_id"],
                "filename": it["filename"],
                "position_mm": [centered_x, centered_y, centered_z],
                "rotation_deg": [0.0, 0.0, 0.0],
            })

        return placements, all_fit

    @staticmethod
    def export_project_3mf(
        models_data: List[Dict[str, Any]],
        destination: Union[str, Path],
        project_name: str = "Outlaw_Forge_Project",
        printer_model: str = "Generic FDM Printer",
        filament_name: str = "Generic PLA",
    ) -> Path:
        """
        Package multiple 3D models with their bed placements, rotations, and scales into
        a standard 3MF (3D Manufacturing Format) container compatible with OrcaSlicer and Bambu Studio.
        """
        dest_path = Path(destination)
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        content_types_xml = """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>
  <Default Extension="json" ContentType="application/json"/>
</Types>"""

        rels_xml = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>
</Relationships>"""

        model_xml_parts = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<model unit="millimeter" xml:lang="en-US" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" xmlns:BambuStudio="http://schemas.bambulab.com/package/2021">',
            f'  <metadata name="Title">{project_name}</metadata>',
            '  <metadata name="Designer">Outlaw Forge</metadata>',
            '  <metadata name="Application">Outlaw Forge CAD Studio</metadata>',
            '  <resources>',
        ]

        build_items = []
        object_id = 1

        for item in models_data:
            mesh = item.get("mesh")
            if mesh is None:
                continue

            fname = item.get("filename", f"object_{object_id}.stl")
            pos = item.get("position_mm", [0.0, 0.0, 0.0])
            rot = item.get("rotation_deg", [0.0, 0.0, 0.0])
            scl = item.get("scale_factors", [1.0, 1.0, 1.0])

            model_xml_parts.append(f'    <object id="{object_id}" type="model" name="{fname}">')
            model_xml_parts.append('      <mesh>')
            model_xml_parts.append('        <vertices>')
            for v in mesh.vertices:
                model_xml_parts.append(f'          <vertex x="{v[0]:.4f}" y="{v[1]:.4f}" z="{v[2]:.4f}"/>')
            model_xml_parts.append('        </vertices>')
            model_xml_parts.append('        <triangles>')
            for f in mesh.faces:
                model_xml_parts.append(f'          <triangle v1="{f[0]}" v2="{f[1]}" v3="{f[2]}"/>')
            model_xml_parts.append('        </triangles>')
            model_xml_parts.append('      </mesh>')
            model_xml_parts.append('    </object>')

            rx, ry, rz = np.radians(rot[0]), np.radians(rot[1]), np.radians(rot[2])
            rot_mat = trimesh.transformations.euler_matrix(rx, ry, rz, axes="sxyz")
            scale_mat = np.diag([scl[0], scl[1], scl[2], 1.0])
            transform_mat = rot_mat @ scale_mat

            m00, m01, m02 = transform_mat[0, 0], transform_mat[0, 1], transform_mat[0, 2]
            m10, m11, m12 = transform_mat[1, 0], transform_mat[1, 1], transform_mat[1, 2]
            m20, m21, m22 = transform_mat[2, 0], transform_mat[2, 1], transform_mat[2, 2]
            tx, ty, tz = pos[0], pos[1], pos[2]

            transform_str = f"{m00:.6f} {m01:.6f} {m02:.6f} {m10:.6f} {m11:.6f} {m12:.6f} {m20:.6f} {m21:.6f} {m22:.6f} {tx:.4f} {ty:.4f} {tz:.4f}"
            build_items.append(f'    <item objectid="{object_id}" transform="{transform_str}"/>')
            object_id += 1

        model_xml_parts.append('  </resources>')
        model_xml_parts.append('  <build>')
        model_xml_parts.extend(build_items)
        model_xml_parts.append('  </build>')
        model_xml_parts.append('</model>')

        model_xml = "\n".join(model_xml_parts)

        orca_project_info = {
            "version": "1.0.0",
            "project_name": project_name,
            "printer_model": printer_model,
            "filament": filament_name,
            "plates": [
                {
                    "plate_index": 1,
                    "plate_name": "Plate 1",
                    "model_count": len(build_items),
                }
            ]
        }
        orca_json = json.dumps(orca_project_info, indent=2)

        with zipfile.ZipFile(dest_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("[Content_Types].xml", content_types_xml)
            zf.writestr("_rels/.rels", rels_xml)
            zf.writestr("3D/3dmodel.model", model_xml)
            zf.writestr("Metadata/project_info.json", orca_json)

        return dest_path

    @staticmethod
    def analyze_thin_walls(
        mesh: trimesh.Trimesh,
        min_wall_thickness_mm: float = 0.8,
        sample_points: int = 500,
        model_id: str = "model",
    ) -> ThinWallAnalysisResult:
        """
        Analyze model surface geometry for walls/features thinner than min_wall_thickness_mm.
        Uses inward normal raycasting to measure opposing surface distance.
        """
        if mesh is None or len(mesh.faces) == 0 or len(mesh.vertices) == 0:
            raise MeshValidationError("Cannot analyze thin walls on an empty mesh.")

        min_thickness = max(0.05, float(min_wall_thickness_mm))
        num_samples = min(max(50, int(sample_points)), len(mesh.faces))

        # Sample points on the surface with corresponding normals
        try:
            points, face_indices = trimesh.sample.sample_surface(mesh, num_samples)
            normals = mesh.face_normals[face_indices]
        except Exception:
            # Fallback to face centers and face normals
            step = max(1, len(mesh.faces) // num_samples)
            face_indices = np.arange(0, len(mesh.faces), step)[:num_samples]
            points = mesh.triangles_center[face_indices]
            normals = mesh.face_normals[face_indices]

        # Inward ray origins offset slightly inwards along -normal
        ray_origins = points - (normals * 0.005)
        ray_directions = -normals

        thin_regions: List[ThinRegionModel] = []
        min_detected = float("inf")
        total_thin_area_estimate = 0.0

        try:
            locations, index_ray, index_tri = mesh.ray.intersects_location(
                ray_origins=ray_origins,
                ray_directions=ray_directions,
            )

            if len(index_ray) > 0:
                # Group hits by ray index
                for i in range(len(ray_origins)):
                    hit_mask = index_ray == i
                    if np.any(hit_mask):
                        hit_locs = locations[hit_mask]
                        diffs = hit_locs - ray_origins[i]
                        dists = np.linalg.norm(diffs, axis=1)
                        # Filter out self-intersections (too close to 0)
                        valid_dists = dists[dists > 0.02]
                        if len(valid_dists) > 0:
                            closest_dist = float(np.min(valid_dists))
                            if closest_dist < min_thickness:
                                min_detected = min(min_detected, closest_dist)
                                is_crit = closest_dist < (min_thickness * 0.5)
                                thin_regions.append(
                                    ThinRegionModel(
                                        center_mm=[
                                            round(float(points[i][0]), 2),
                                            round(float(points[i][1]), 2),
                                            round(float(points[i][2]), 2),
                                        ],
                                        thickness_mm=round(closest_dist, 3),
                                        severity="critical" if is_crit else "warning",
                                        feature_id=len(thin_regions) + 1,
                                    )
                                )
                                total_thin_area_estimate += (mesh.area / len(points)) / 100.0
        except Exception:
            pass

        # If no thin walls or raycast failed, test bounding box minimum extent
        extents = [float(v) for v in mesh.extents]
        if min(extents) < min_thickness and len(thin_regions) == 0:
            min_detected = min(extents)
            thin_regions.append(
                ThinRegionModel(
                    center_mm=[
                        round(float(mesh.centroid[0]), 2),
                        round(float(mesh.centroid[1]), 2),
                        round(float(mesh.centroid[2]), 2),
                    ],
                    thickness_mm=round(min_detected, 3),
                    severity="critical" if min_detected < (min_thickness * 0.5) else "warning",
                    feature_id=1,
                )
            )
            total_thin_area_estimate = mesh.area / 100.0

        if min_detected == float("inf"):
            min_detected = min_thickness

        summary = (
            f"Found {len(thin_regions)} thin feature region(s) (< {min_thickness:.2f}mm). "
            f"Minimum wall thickness: {min_detected:.2f}mm."
            if thin_regions
            else f"No wall thickness issues detected (all evaluated surfaces >= {min_thickness:.2f}mm)."
        )

        return ThinWallAnalysisResult(
            model_id=model_id,
            thin_wall_count=len(thin_regions),
            min_detected_thickness_mm=round(min_detected, 3),
            thin_regions=thin_regions[:50],  # Cap output to top 50
            total_thin_area_cm2=round(total_thin_area_estimate, 3),
            summary=summary,
        )

    @staticmethod
    def analyze_floating_islands(
        mesh: trimesh.Trimesh,
        min_island_area_mm2: float = 0.5,
        overhang_threshold_deg: float = 65.0,
        model_id: str = "model",
    ) -> IslandAnalysisResult:
        """
        Detect severe downward-facing surfaces (islands) that have no supporting geometry underneath.
        """
        if mesh is None or len(mesh.faces) == 0 or len(mesh.vertices) == 0:
            raise MeshValidationError("Cannot analyze floating islands on an empty mesh.")

        min_z = float(mesh.bounds[0][2])
        normals = mesh.face_normals
        centers = mesh.triangles_center
        areas = mesh.area_faces

        # Severe downward normal condition: Z component < -0.85 (steeply facing the build plate)
        downward_mask = (normals[:, 2] < -0.85) & (centers[:, 2] > (min_z + 1.5)) & (areas >= (min_island_area_mm2 / 2.0))
        island_faces = np.where(downward_mask)[0]

        islands: List[FloatingIslandModel] = []

        if len(island_faces) > 0:
            origins = centers[island_faces] + np.array([0, 0, -0.05])
            directions = np.repeat([[0.0, 0.0, -1.0]], len(origins), axis=0)

            try:
                locations, index_ray, _ = mesh.ray.intersects_location(
                    ray_origins=origins,
                    ray_directions=directions,
                )

                hit_rays = set(index_ray) if len(index_ray) > 0 else set()

                for i, face_idx in enumerate(island_faces):
                    # If ray does not hit any part of the model below it within 20mm, it's an unsupported island
                    is_unsupported = False
                    if i not in hit_rays:
                        is_unsupported = True
                    else:
                        mask = index_ray == i
                        hit_dists = np.linalg.norm(locations[mask] - origins[i], axis=1)
                        if len(hit_dists) > 0 and np.min(hit_dists) > 20.0:
                            is_unsupported = True

                    if is_unsupported:
                        pt = centers[face_idx]
                        is_crit = float(areas[face_idx]) > 5.0
                        islands.append(
                            FloatingIslandModel(
                                point_mm=[
                                    round(float(pt[0]), 2),
                                    round(float(pt[1]), 2),
                                    round(float(pt[2]), 2),
                                ],
                                layer_z_mm=round(float(pt[2]), 2),
                                area_mm2=round(float(areas[face_idx]), 2),
                                severity="critical" if is_crit else "warning",
                            )
                        )
            except Exception:
                # Fallback: flag top severe downward faces
                for face_idx in island_faces[:10]:
                    pt = centers[face_idx]
                    islands.append(
                        FloatingIslandModel(
                            point_mm=[
                                round(float(pt[0]), 2),
                                round(float(pt[1]), 2),
                                round(float(pt[2]), 2),
                            ],
                            layer_z_mm=round(float(pt[2]), 2),
                            area_mm2=round(float(areas[face_idx]), 2),
                            severity="warning",
                        )
                    )

        summary = (
            f"Detected {len(islands)} unsupported floating island(s) requiring print supports or reorientation."
            if islands
            else "No critical unsupported floating islands detected."
        )

        return IslandAnalysisResult(
            model_id=model_id,
            island_count=len(islands),
            islands=islands[:50],
            summary=summary,
        )

    @staticmethod
    def estimate_cost_and_time(
        mesh: trimesh.Trimesh,
        payload: Optional[CostEstimationPayload] = None,
        model_id: str = "model",
    ) -> CostEstimationResult:
        """
        Calculate printed material volume, mass, filament length, cost, and print time.
        """
        if mesh is None or len(mesh.faces) == 0:
            raise MeshValidationError("Cannot estimate print metrics for an empty mesh.")

        if payload is None:
            payload = CostEstimationPayload()

        # 1. Volume & Surface Area
        try:
            if mesh.is_watertight and mesh.volume > 0:
                model_vol_cm3 = float(mesh.volume) / 1000.0
            else:
                # Approximate volume from bounding box or convex hull
                model_vol_cm3 = float(np.prod(mesh.extents)) * 0.45 / 1000.0
        except Exception:
            model_vol_cm3 = float(np.prod(mesh.extents)) * 0.45 / 1000.0

        if model_vol_cm3 <= 0:
            model_vol_cm3 = 1.0

        surface_area_cm2 = float(mesh.area) / 100.0

        # 2. Shell volume vs Infill volume
        shell_thickness_cm = float(payload.wall_thickness_mm) / 10.0
        shell_vol_cm3 = min(model_vol_cm3, surface_area_cm2 * shell_thickness_cm)
        interior_vol_cm3 = max(0.0, model_vol_cm3 - shell_vol_cm3)
        infill_vol_cm3 = interior_vol_cm3 * (float(payload.effective_infill_pct) / 100.0)

        total_printed_vol_cm3 = shell_vol_cm3 + infill_vol_cm3

        # 3. Mass & Cost
        mass_grams = total_printed_vol_cm3 * float(payload.density_g_cm3)
        spool_wt = max(1.0, float(payload.spool_weight_g))
        spool_pr = float(payload.spool_price_usd)
        material_cost = (mass_grams / spool_wt) * spool_pr

        # 4. Filament Length (for 1.75mm diameter filament)
        r_mm = 1.75 / 2.0
        filament_area_mm2 = np.pi * (r_mm ** 2)
        filament_length_m = (total_printed_vol_cm3 * 1000.0) / filament_area_mm2 / 1000.0

        # 5. Print Time Calculation
        layer_h = max(0.05, float(payload.layer_height_mm))
        speed_mm_s = max(10.0, float(payload.print_speed_mm_s))
        # Volumetric flow rate Q in mm3/s
        q_flow = 0.4 * layer_h * speed_mm_s * 0.65
        extrusion_secs = (total_printed_vol_cm3 * 1000.0) / max(0.1, q_flow)

        height_mm = float(mesh.extents[2]) if len(mesh.extents) > 2 else 20.0
        layer_count = max(1, int(height_mm / layer_h))
        overhead_secs = layer_count * 1.5

        total_minutes = (extrusion_secs + overhead_secs) / 60.0
        hours = int(total_minutes // 60)
        mins = int(total_minutes % 60)
        formatted_time = f"{hours}h {mins}m" if hours > 0 else f"{mins}m"

        return CostEstimationResult(
            model_id=model_id,
            model_volume_cm3=round(model_vol_cm3, 2),
            shell_volume_cm3=round(shell_vol_cm3, 2),
            infill_volume_cm3=round(infill_vol_cm3, 2),
            total_printed_volume_cm3=round(total_printed_vol_cm3, 2),
            mass_grams=round(mass_grams, 1),
            estimated_mass_grams=round(mass_grams, 1),
            filament_length_m=round(filament_length_m, 2),
            estimated_filament_length_m=round(filament_length_m, 2),
            material_cost_usd=round(material_cost, 2),
            estimated_cost_usd=round(material_cost, 2),
            estimated_time_minutes=round(total_minutes, 1),
            estimated_print_time_min=round(total_minutes, 1),
            estimated_time_formatted=formatted_time,
            material_type=payload.material_type or "PLA",
        )


# Singleton instance and module-level function aliases
mesh_service = MeshService()
load_mesh = MeshService.load_mesh
analyze_mesh = MeshService.analyze_mesh
scale_mesh = MeshService.scale_mesh
export_mesh = MeshService.export_mesh
rotate_mesh = MeshService.rotate_mesh
center_mesh_on_bed = MeshService.center_mesh_on_bed
lay_flat_mesh = MeshService.lay_flat_mesh
analyze_overhangs = MeshService.analyze_overhangs
slice_mesh = MeshService.slice_mesh
repair_mesh = MeshService.repair_mesh
hollow_mesh = MeshService.hollow_mesh
arrange_models_on_bed = MeshService.arrange_models_on_bed
export_project_3mf = MeshService.export_project_3mf
analyze_thin_walls = MeshService.analyze_thin_walls
analyze_floating_islands = MeshService.analyze_floating_islands
estimate_cost_and_time = MeshService.estimate_cost_and_time

