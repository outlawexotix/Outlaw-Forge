import io
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union
import numpy as np
import trimesh
from fastapi import HTTPException, status

from app.models.mesh import (
    ExportModelPayload,
    ExportResult,
    MeshAnalysisResult,
    MeshRepairReport,
    OverhangAnalysisResult,
    RotateModelPayload,
    ScaleModelPayload,
    SliceModelPayload,
    SliceModelResult,
)
from app.models.project import MeshBounds, MeshTransform

ALLOWED_EXTENSIONS: Set[str] = {"stl", "obj", "glb", "gltf", "3mf"}
MAX_FILE_SIZE_BYTES: int = 100 * 1024 * 1024  # 100 MB


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
        top_slice = trimesh.intersections.slice_mesh_plane(
            mesh=mesh,
            plane_normal=normal,
            plane_origin=origin,
            cap=cap_faces,
        )

        # Slice negative half (below cut plane)
        bottom_slice = trimesh.intersections.slice_mesh_plane(
            mesh=mesh,
            plane_normal=-normal,
            plane_origin=origin,
            cap=cap_faces,
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
