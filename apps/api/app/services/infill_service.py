"""
Parametric 3D Infill & Lattice Generator Service for Outlaw Forge.
Generates deterministic, watertight 2-manifold procedural 3D infill lattices
using manifold3d: Gyroid (TPMS), Honeycomb, Rectilinear, and Cubic.
Strict millimetre standard (1.0 unit = 1.0 mm).
"""

from enum import Enum
import math
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union
import numpy as np
import trimesh
from manifold3d import CrossSection, Manifold, Mesh, OpType

from app.models.mesh import InfillPattern


class InfillServiceError(Exception):
    """Base exception for infill generation failures."""
    pass


class InfillService:
    """
    Parametric volumetric infill engine using manifold3d exact CSG booleans,
    SDF level-set extraction (Marching Tetrahedra), and 2D CrossSection extrusions.
    """

    @staticmethod
    def trimesh_to_manifold(mesh: trimesh.Trimesh) -> Manifold:
        """
        Convert a trimesh.Trimesh into a manifold3d.Manifold instance.
        Ensures 32-bit contiguous vertex and index arrays.
        """
        if mesh is None or len(mesh.faces) == 0:
            raise InfillServiceError("Cannot convert empty mesh to Manifold.")

        clean_mesh = mesh.copy()
        clean_mesh.remove_unreferenced_vertices()

        verts = np.ascontiguousarray(clean_mesh.vertices, dtype=np.float32)
        faces = np.ascontiguousarray(clean_mesh.faces, dtype=np.int32)

        m_mesh = Mesh(vert_properties=verts, tri_verts=faces)
        manifold = Manifold(m_mesh)
        if manifold.is_empty():
            raise InfillServiceError("Generated Manifold is empty or degenerate.")
        return manifold

    @staticmethod
    def manifold_to_trimesh(manifold: Manifold) -> trimesh.Trimesh:
        """
        Convert a manifold3d.Manifold back to a watertight trimesh.Trimesh.
        """
        if manifold.is_empty():
            raise InfillServiceError("Manifold is empty, cannot convert to Trimesh.")

        raw_mesh = manifold.to_mesh()
        result_mesh = trimesh.Trimesh(
            vertices=np.array(raw_mesh.vert_properties, dtype=np.float64),
            faces=np.array(raw_mesh.tri_verts, dtype=np.int64),
            process=False,
        )
        result_mesh.remove_unreferenced_vertices()
        result_mesh.fix_normals()
        return result_mesh

    @staticmethod
    def create_inner_cavity(mesh: trimesh.Trimesh, wall_thickness_mm: float) -> Manifold:
        """
        Generate a watertight inner cavity manifold for shell hollowing.
        Uses inward normal displacement with automatic fallback to centroid scaling.
        """
        extents = mesh.extents
        min_extent = float(min(extents))
        safe_thickness = min(float(wall_thickness_mm), max(0.5, min_extent * 0.45))
        centroid = mesh.centroid

        # 1. Attempt inward vertex normal displacement
        try:
            inner_norm = mesh.copy()
            if len(inner_norm.vertex_normals) == len(inner_norm.vertices):
                inner_norm.vertices -= inner_norm.vertex_normals * safe_thickness
                m_norm = InfillService.trimesh_to_manifold(inner_norm)
                if not m_norm.is_empty() and m_norm.volume() > 0:
                    return m_norm
        except Exception:
            pass

        # 2. Fallback to centroid / anisotropic bounding box scaling
        inner_scale = mesh.copy()
        scales = np.maximum(0.05, (extents - 2.0 * safe_thickness) / np.maximum(1e-4, extents))
        inner_scale.vertices = centroid + (inner_scale.vertices - centroid) * scales
        return InfillService.trimesh_to_manifold(inner_scale)

    @staticmethod
    def generate_gyroid(
        bounds: Sequence[float],
        unit_cell_size_mm: float = 10.0,
        density: float = 0.20,
    ) -> Manifold:
        """
        Generate Gyroid TPMS (Triply Periodic Minimal Surface) infill using
        manifold3d.Manifold.level_set (Marching Tetrahedra).
        SDF equation: t - abs(sin(kx)*cos(ky) + sin(ky)*cos(kz) + sin(kz)*cos(kx))
        where k = 2 * pi / unit_cell_size_mm.
        """
        x_min, y_min, z_min, x_max, y_max, z_max = bounds
        pad = 0.5
        padded_bounds = [
            x_min - pad,
            y_min - pad,
            z_min - pad,
            x_max + pad,
            y_max + pad,
            z_max + pad,
        ]

        L = max(1.0, float(unit_cell_size_mm))
        D = min(1.0, max(0.05, float(density)))
        k = (2.0 * math.pi) / L

        # Calibrated thickness parameter mapping for monotonic volume fraction
        if D >= 0.95:
            t = 1.5
        else:
            t = 0.08 + 1.25 * D

        def gyroid_sdf(x: float, y: float, z: float) -> float:
            f = (
                math.sin(k * x) * math.cos(k * y)
                + math.sin(k * y) * math.cos(k * z)
                + math.sin(k * z) * math.cos(k * x)
            )
            return t - abs(f)

        # Resolution scaling
        edge_len = min(1.5, max(0.4, L / 12.0))
        max_extent = max(x_max - x_min, y_max - y_min, z_max - z_min)
        if max_extent / edge_len > 100.0:
            edge_len = max_extent / 100.0

        return Manifold.level_set(gyroid_sdf, padded_bounds, edge_len)

    @staticmethod
    def generate_honeycomb(
        bounds: Sequence[float],
        unit_cell_size_mm: float = 10.0,
        density: float = 0.20,
    ) -> Manifold:
        """
        Generate Honeycomb / Hexagonal vertical compressive cell lattice.
        Constructed via 2D CrossSection boolean hole subtraction and extruded along Z.
        """
        x_min, y_min, z_min, x_max, y_max, z_max = bounds
        pad = 0.5
        W = (x_max - x_min) + 2.0 * pad
        Yd = (y_max - y_min) + 2.0 * pad
        H = (z_max - z_min) + 2.0 * pad
        cx = (x_min + x_max) / 2.0
        cy = (y_min + y_max) / 2.0
        cz = (z_min + z_max) / 2.0

        if density >= 0.999:
            return Manifold.cube([W, Yd, H], center=True).translate([cx, cy, cz])

        L = max(1.0, float(unit_cell_size_mm))
        D = min(0.999, max(0.01, float(density)))

        # Hexagonal inner void radius
        r_inner = (L * math.sqrt(max(0.001, 1.0 - D))) / math.sqrt(3.0)

        dx = L
        dy = L * math.sqrt(3.0) / 2.0

        nx = int(math.ceil(W / dx)) + 2
        ny = int(math.ceil(Yd / dy)) + 2

        holes = []
        for j in range(-ny, ny + 1):
            yj = cy + j * dy
            row_shift = (j % 2) * (dx / 2.0)
            for i in range(-nx, nx + 1):
                xi = cx + i * dx + row_shift
                if (x_min - pad - L) <= xi <= (x_max + pad + L) and (y_min - pad - L) <= yj <= (y_max + pad + L):
                    holes.append(CrossSection.circle(r_inner, 6).translate([xi, yj]))

        all_holes = CrossSection.batch_boolean(holes, OpType.Add)
        base = CrossSection.square([W, Yd], center=True).translate([cx, cy])
        honeycomb_2d = base - all_holes
        m_lattice = honeycomb_2d.extrude(H).translate([0.0, 0.0, z_min - pad])
        return m_lattice

    @staticmethod
    def generate_rectilinear(
        bounds: Sequence[float],
        unit_cell_size_mm: float = 10.0,
        density: float = 0.20,
    ) -> Manifold:
        """
        Generate 2D orthogonal grid lattice extruded along Z.
        Constructed via CrossSection square void subtraction and extruded along Z.
        """
        x_min, y_min, z_min, x_max, y_max, z_max = bounds
        pad = 0.5
        W = (x_max - x_min) + 2.0 * pad
        Yd = (y_max - y_min) + 2.0 * pad
        H = (z_max - z_min) + 2.0 * pad
        cx = (x_min + x_max) / 2.0
        cy = (y_min + y_max) / 2.0
        cz = (z_min + z_max) / 2.0

        if density >= 0.999:
            return Manifold.cube([W, Yd, H], center=True).translate([cx, cy, cz])

        L = max(1.0, float(unit_cell_size_mm))
        D = min(0.999, max(0.01, float(density)))
        s = L * math.sqrt(max(0.001, 1.0 - D))

        nx = int(math.ceil(W / L)) + 2
        ny = int(math.ceil(Yd / L)) + 2

        holes = []
        for j in range(-ny, ny + 1):
            yj = cy + j * L
            for i in range(-nx, nx + 1):
                xi = cx + i * L
                if (x_min - pad - L) <= xi <= (x_max + pad + L) and (y_min - pad - L) <= yj <= (y_max + pad + L):
                    holes.append(CrossSection.square([s, s], center=True).translate([xi, yj]))

        all_holes = CrossSection.batch_boolean(holes, OpType.Add)
        base = CrossSection.square([W, Yd], center=True).translate([cx, cy])
        grid_2d = base - all_holes
        m_lattice = grid_2d.extrude(H).translate([0.0, 0.0, z_min - pad])
        return m_lattice

    @staticmethod
    def generate_cubic(
        bounds: Sequence[float],
        unit_cell_size_mm: float = 10.0,
        density: float = 0.20,
    ) -> Manifold:
        """
        Generate 3D orthogonal volumetric grid lattice unified with Manifold.batch_boolean.
        Constructed from intersecting orthogonal planar slabs across X, Y, and Z axes.
        """
        x_min, y_min, z_min, x_max, y_max, z_max = bounds
        pad = 0.5
        W = (x_max - x_min) + 2.0 * pad
        Yd = (y_max - y_min) + 2.0 * pad
        H = (z_max - z_min) + 2.0 * pad
        cx = (x_min + x_max) / 2.0
        cy = (y_min + y_max) / 2.0
        cz = (z_min + z_max) / 2.0

        if density >= 0.999:
            return Manifold.cube([W, Yd, H], center=True).translate([cx, cy, cz])

        L = max(1.0, float(unit_cell_size_mm))
        D = min(0.999, max(0.01, float(density)))
        w = max(0.1, L * (1.0 - (1.0 - D) ** (1.0 / 3.0)))

        nx = int(math.ceil(W / (2.0 * L))) + 1
        ny = int(math.ceil(Yd / (2.0 * L))) + 1
        nz = int(math.ceil(H / (2.0 * L))) + 1

        slabs = []
        # X-normal slabs
        for i in range(-nx, nx + 1):
            xi = cx + i * L
            if (x_min - pad) <= xi <= (x_max + pad):
                slabs.append(Manifold.cube([w, Yd, H], center=True).translate([xi, cy, cz]))

        # Y-normal slabs
        for j in range(-ny, ny + 1):
            yj = cy + j * L
            if (y_min - pad) <= yj <= (y_max + pad):
                slabs.append(Manifold.cube([W, w, H], center=True).translate([cx, yj, cz]))

        # Z-normal slabs
        for k in range(-nz, nz + 1):
            zk = cz + k * L
            if (z_min - pad) <= zk <= (z_max + pad):
                slabs.append(Manifold.cube([W, Yd, w], center=True).translate([cx, cy, zk]))

        if not slabs:
            return Manifold.cube([W, Yd, H], center=True).translate([cx, cy, cz])

        return Manifold.batch_boolean(slabs, OpType.Add)

    def generate_lattice(
        self,
        pattern: Union[InfillPattern, str],
        bounds: Sequence[float],
        unit_cell_size_mm: float = 10.0,
        density: float = 0.20,
    ) -> Manifold:
        """
        Dispatch procedural lattice generation for the specified pattern.
        """
        pattern_str = pattern.value if isinstance(pattern, InfillPattern) else str(pattern).lower()

        if pattern_str == InfillPattern.GYROID.value:
            return self.generate_gyroid(bounds, unit_cell_size_mm, density)
        elif pattern_str == InfillPattern.HONEYCOMB.value:
            return self.generate_honeycomb(bounds, unit_cell_size_mm, density)
        elif pattern_str == InfillPattern.RECTILINEAR.value:
            return self.generate_rectilinear(bounds, unit_cell_size_mm, density)
        elif pattern_str == InfillPattern.CUBIC.value:
            return self.generate_cubic(bounds, unit_cell_size_mm, density)
        else:
            raise InfillServiceError(f"Unsupported infill pattern: '{pattern_str}'")

    def generate_infill(
        self,
        mesh: trimesh.Trimesh,
        pattern: Union[InfillPattern, str] = InfillPattern.GYROID,
        density: float = 0.20,
        unit_cell_size_mm: float = 10.0,
        wall_thickness_mm: float = 2.0,
        hollow_first: bool = True,
    ) -> Tuple[trimesh.Trimesh, float]:
        """
        Generate volumetric internal infill inside solid or hollowed mesh geometry.
        Returns: (resulting_trimesh, volume_reduction_percent)
        """
        if mesh is None or len(mesh.faces) == 0:
            raise InfillServiceError("Cannot generate infill for empty mesh.")

        m_mesh = self.trimesh_to_manifold(mesh)
        original_volume = m_mesh.volume()

        # Handle 100% solid density edge case
        if density >= 0.999:
            return mesh.copy(), 0.0

        # Check if the mesh is already hollowed (contains multiple decomposed components)
        decomposed = m_mesh.decompose()
        is_already_hollowed = len(decomposed) >= 2

        if is_already_hollowed:
            # Sort components by volume descending (outer shell is largest, cavity void is inside)
            sorted_comps = sorted(decomposed, key=lambda c: c.volume(), reverse=True)
            outer_shell = sorted_comps[0]
            cavity_void = sorted_comps[1]

            cavity_bounds = list(cavity_void.bounding_box())
            lattice = self.generate_lattice(pattern, cavity_bounds, unit_cell_size_mm, density)

            # Trim lattice to cavity void
            infill_core = lattice ^ cavity_void
            wall_shell = outer_shell - cavity_void
            m_final = wall_shell + infill_core

        elif hollow_first:
            # Solid mesh: generate outer perimeter shell and inner void cavity
            m_cavity = self.create_inner_cavity(mesh, wall_thickness_mm)
            cavity_bounds = list(m_cavity.bounding_box())

            lattice = self.generate_lattice(pattern, cavity_bounds, unit_cell_size_mm, density)

            infill_core = lattice ^ m_cavity
            m_shell = m_mesh - m_cavity
            m_final = m_shell + infill_core

        else:
            # Full solid lattice without outer shell
            mesh_bounds = list(m_mesh.bounding_box())
            lattice = self.generate_lattice(pattern, mesh_bounds, unit_cell_size_mm, density)
            m_final = lattice ^ m_mesh

        if m_final.is_empty():
            raise InfillServiceError("Boolean operation yielded empty infill mesh.")

        final_volume = m_final.volume()
        volume_reduction_percent = 0.0
        if original_volume > 0:
            volume_reduction_percent = max(
                0.0,
                round(((original_volume - final_volume) / original_volume) * 100.0, 2),
            )

        result_mesh = self.manifold_to_trimesh(m_final)
        return result_mesh, volume_reduction_percent

    def reinforce_internal_ribs(
        self,
        mesh: trimesh.Trimesh,
        rib_thickness_mm: float = 1.5,
        rib_spacing_mm: float = 12.0,
        rib_height_mm: float = 3.0,
        drainage_hole_radius_mm: float = 2.0,
        add_drainage_channel: bool = True,
        drainage_axis: str = "z",
        wall_thickness_mm: float = 2.0,
    ) -> Tuple[trimesh.Trimesh, int, int]:
        """
        Generate parametric internal structural rib reinforcement along hollow interior walls
        to prevent print buckling, and continuous drainage channels to eliminate trapped resin/air.
        Returns: (resulting_trimesh, rib_count, drainage_holes_count)
        """
        if mesh is None or len(mesh.faces) == 0:
            raise InfillServiceError("Cannot reinforce empty mesh.")

        m_mesh = self.trimesh_to_manifold(mesh)
        decomposed = m_mesh.decompose()
        is_already_hollowed = len(decomposed) >= 2

        if is_already_hollowed:
            sorted_comps = sorted(decomposed, key=lambda c: c.volume(), reverse=True)
            outer_shell = sorted_comps[0] - sorted_comps[1]
            cavity_void = sorted_comps[1]
        else:
            cavity_void = self.create_inner_cavity(mesh, wall_thickness_mm)
            outer_shell = m_mesh - cavity_void

        if cavity_void.is_empty() or cavity_void.volume() <= 0:
            raise InfillServiceError("Mesh internal cavity is too small for rib reinforcement.")

        cavity_bounds = list(cavity_void.bounding_box())
        x_min, y_min, z_min, x_max, y_max, z_max = cavity_bounds
        W = max(0.1, x_max - x_min)
        Yd = max(0.1, y_max - y_min)
        H = max(0.1, z_max - z_min)
        cx = (x_min + x_max) / 2.0
        cy = (y_min + y_max) / 2.0
        cz = (z_min + z_max) / 2.0

        L = max(1.0, float(rib_spacing_mm))
        t = max(0.4, float(rib_thickness_mm))

        nx = int(math.ceil(W / (2.0 * L))) + 1
        ny = int(math.ceil(Yd / (2.0 * L))) + 1

        slabs = []
        rib_count = 0

        # X-perpendicular rib slabs (along Y-Z plane)
        for i in range(-nx, nx + 1):
            xi = cx + i * L
            if (x_min + t) <= xi <= (x_max - t):
                slabs.append(Manifold.cube([t, Yd + 2.0, H + 2.0], center=True).translate([xi, cy, cz]))
                rib_count += 1

        # Y-perpendicular rib slabs (along X-Z plane)
        for j in range(-ny, ny + 1):
            yj = cy + j * L
            if (y_min + t) <= yj <= (y_max - t):
                slabs.append(Manifold.cube([W + 2.0, t, H + 2.0], center=True).translate([cx, yj, cz]))
                rib_count += 1

        if rib_count == 0 or not slabs:
            slabs.append(Manifold.cube([t, Yd + 2.0, H + 2.0], center=True).translate([cx, cy, cz]))
            slabs.append(Manifold.cube([W + 2.0, t, H + 2.0], center=True).translate([cx, cy, cz]))
            rib_count = 2

        all_slabs = Manifold.batch_boolean(slabs, OpType.Add)
        m_ribs = all_slabs ^ cavity_void

        m_reinforced = outer_shell + m_ribs

        drainage_holes_count = 0
        if add_drainage_channel:
            r_hole = max(0.5, float(drainage_hole_radius_mm))
            axis = str(drainage_axis).lower()
            h_cyl = (wall_thickness_mm * 4.0) + 20.0

            if axis == "z":
                z_base = mesh.bounds[0][2] - 2.0
                cyl = CrossSection.circle(r_hole, 32).extrude(h_cyl).translate([cx, cy, z_base])
                m_reinforced = m_reinforced - cyl
                drainage_holes_count = 1
            elif axis == "x":
                x_base = mesh.bounds[0][0] - 2.0
                cyl = CrossSection.circle(r_hole, 32).extrude(h_cyl).rotate([0.0, 90.0, 0.0]).translate([x_base, cy, cz])
                m_reinforced = m_reinforced - cyl
                drainage_holes_count = 1
            elif axis == "y":
                y_base = mesh.bounds[0][1] - 2.0
                cyl = CrossSection.circle(r_hole, 32).extrude(h_cyl).rotate([-90.0, 0.0, 0.0]).translate([cx, y_base, cz])
                m_reinforced = m_reinforced - cyl
                drainage_holes_count = 1

        if m_reinforced.is_empty():
            raise InfillServiceError("Reinforcement operation resulted in empty geometry.")

        result_mesh = self.manifold_to_trimesh(m_reinforced)
        return result_mesh, rib_count, drainage_holes_count


infill_service = InfillService()
