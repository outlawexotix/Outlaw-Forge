import math
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import trimesh

from app.models.studios import (
    CenterOfMassAnalysis,
    PlinthShape,
)


class FigureForgeService:
    @staticmethod
    def analyze_center_of_mass(mesh: trimesh.Trimesh, model_id: str = "") -> CenterOfMassAnalysis:
        """
        Calculates center of mass (gravity), ground contact footprint,
        tipping/topple angle, and stability safety margin for collectible figures and statues.
        """
        if mesh is None or len(mesh.faces) == 0:
            raise ValueError("Cannot analyze empty mesh.")

        bounds_min = mesh.bounds[0]
        bounds_max = mesh.bounds[1]
        min_x, min_y, min_z = [float(v) for v in bounds_min]
        max_x, max_y, max_z = [float(v) for v in bounds_max]

        width = max_x - min_x
        depth = max_y - min_y
        height = max_z - min_z

        base_cx = (min_x + max_x) / 2.0
        base_cy = (min_y + max_y) / 2.0
        base_cz = min_z
        base_centroid = [round(base_cx, 2), round(base_cy, 2), round(base_cz, 2)]

        # Calculate Center of Mass
        try:
            if mesh.is_watertight and mesh.volume > 0:
                com_raw = mesh.center_mass
            else:
                com_raw = mesh.centroid
        except Exception:
            com_raw = mesh.centroid

        com_x = float(com_raw[0])
        com_y = float(com_raw[1])
        com_z = float(com_raw[2])
        center_of_mass = [round(com_x, 2), round(com_y, 2), round(com_z, 2)]
        ground_projection = [round(com_x, 2), round(com_y, 2), round(min_z, 2)]

        # Contact base radius approx
        base_contact_radius = max(width, depth) / 2.0

        # Center-of-mass lateral offset from base centroid
        dx = com_x - base_cx
        dy = com_y - base_cy
        com_offset = math.sqrt(dx * dx + dy * dy)
        com_offset = round(com_offset, 2)

        # Height of COM above ground
        com_height_above_base = max(com_z - min_z, 1.0)

        # Calculate tipping angle
        remaining_base_margin = max(base_contact_radius - com_offset, 0.1)
        tipping_angle_rad = math.atan2(remaining_base_margin, com_height_above_base)
        tipping_angle_deg = round(math.degrees(tipping_angle_rad), 1)

        # Stability classification
        ratio = com_offset / max(base_contact_radius, 0.1)
        if ratio <= 0.25 and tipping_angle_deg >= 25.0:
            status = "STABLE"
            is_freestanding = True
            notes = "Figure has a balanced center of gravity and will stand stably on flat surfaces without a base."
        elif ratio <= 0.60 and tipping_angle_deg >= 12.0:
            status = "MARGINAL"
            is_freestanding = True
            notes = "Figure is moderately stable but sensitive to vibrations. A weighted display plinth is recommended."
        else:
            status = "TOPPLE_RISK"
            is_freestanding = False
            notes = "Figure center of gravity overhangs base perimeter. Figure will topple over without a display plinth and foot key-pegs."

        recommended_plinth_dia = round(max(width, depth) * 1.35 + 10.0, 1)

        return CenterOfMassAnalysis(
            model_id=model_id,
            center_of_mass=center_of_mass,
            ground_projection=ground_projection,
            base_centroid=base_centroid,
            com_offset_from_center_mm=com_offset,
            base_contact_radius_mm=round(base_contact_radius, 2),
            tipping_angle_deg=tipping_angle_deg,
            stability_status=status,
            is_freestanding=is_freestanding,
            recommended_plinth_diameter_mm=recommended_plinth_dia,
            notes=notes,
        )

    @staticmethod
    def generate_plinth(
        shape: PlinthShape = "cylinder",
        diameter_mm: float = 80.0,
        height_mm: float = 15.0,
        chamfer_height_mm: float = 3.0,
        add_nameplate_recess: bool = False,
        add_figure_sockets: bool = True,
        socket_diameter_mm: float = 5.0,
        socket_depth_mm: float = 8.0,
        socket_spacing_mm: float = 25.0,
    ) -> trimesh.Trimesh:
        """
        Generates a 3D display plinth mesh (Cylinder, Hexagon, Octagon, Stepped, or Chamfered)
        with optional figure key-peg sockets and nameplate slot.
        """
        radius = float(diameter_mm) / 2.0
        h = float(height_mm)

        if shape == "hexagon":
            # 6-sided prism
            plinth = trimesh.creation.cylinder(radius=radius, height=h, sections=6)
        elif shape == "octagon":
            # 8-sided prism
            plinth = trimesh.creation.cylinder(radius=radius, height=h, sections=8)
        elif shape == "stepped_round":
            # Tier 1 (Base): 60% height, 100% radius
            h1 = h * 0.6
            h2 = h * 0.4
            r2 = radius * 0.88
            tier1 = trimesh.creation.cylinder(radius=radius, height=h1, sections=64)
            tier1.apply_translation([0, 0, h1 / 2.0])

            tier2 = trimesh.creation.cylinder(radius=r2, height=h2, sections=64)
            tier2.apply_translation([0, 0, h1 + h2 / 2.0])

            plinth = trimesh.util.concatenate([tier1, tier2])
            plinth.fix_normals()
            # Already base at Z=0
        elif shape == "square_chamfered":
            # Square base
            plinth = trimesh.creation.box(extents=[diameter_mm, diameter_mm, h])
        else:  # cylinder
            plinth = trimesh.creation.cylinder(radius=radius, height=h, sections=64)

        # Center X, Y and place bottom at Z=0
        bounds_min = plinth.bounds[0]
        bounds_max = plinth.bounds[1]
        cx = (bounds_min[0] + bounds_max[0]) / 2.0
        cy = (bounds_min[1] + bounds_max[1]) / 2.0
        cz = bounds_min[2]
        plinth.apply_translation([-cx, -cy, -cz])

        # Top surface is at Z = h
        cutters = []

        # Optional figure mounting sockets on top face
        if add_figure_sockets and socket_diameter_mm > 0 and socket_depth_mm > 0:
            hole_r = float(socket_diameter_mm) / 2.0
            hole_h = float(socket_depth_mm) + 1.0
            dx = float(socket_spacing_mm) / 2.0

            sock1 = trimesh.creation.cylinder(radius=hole_r, height=hole_h, sections=32)
            sock1.apply_translation([-dx, 0.0, h - hole_h / 2.0 + 0.5])
            cutters.append(sock1)

            sock2 = trimesh.creation.cylinder(radius=hole_r, height=hole_h, sections=32)
            sock2.apply_translation([dx, 0.0, h - hole_h / 2.0 + 0.5])
            cutters.append(sock2)

        # Optional nameplate slot recess on front (-Y) face
        if add_nameplate_recess:
            np_w = min(diameter_mm * 0.6, 50.0)
            np_h = min(h * 0.5, 10.0)
            np_d = 2.5
            slot = trimesh.creation.box(extents=[np_w, np_d * 2.0, np_h])
            slot.apply_translation([0.0, -radius, h * 0.45])
            cutters.append(slot)

        if cutters:
            try:
                cutter_union = trimesh.util.concatenate(cutters) if len(cutters) > 1 else cutters[0]
                diff = trimesh.boolean.difference([plinth, cutter_union])
                if diff is not None and len(diff.faces) > 0:
                    plinth = diff
                    plinth.fix_normals()
            except Exception:
                pass

        return plinth

    @staticmethod
    def create_key_pegs(
        mesh: trimesh.Trimesh,
        peg_shape: str = "cylinder",
        peg_diameter_mm: float = 4.8,
        peg_length_mm: float = 8.0,
        foot_offset_mm: float = 12.0,
        dual_feet_pegs: bool = True,
    ) -> Tuple[trimesh.Trimesh, List[List[float]], float, float]:
        """
        Unions dowel key-pegs extending downwards from the base of figure feet for plinth mounting.
        """
        if mesh is None or len(mesh.faces) == 0:
            raise ValueError("Cannot add key-pegs to empty mesh.")

        peg_r = float(peg_diameter_mm) / 2.0
        peg_h = float(peg_length_mm)

        bounds_min = mesh.bounds[0]
        bounds_max = mesh.bounds[1]
        min_z = float(bounds_min[2])
        center_x = (float(bounds_min[0]) + float(bounds_max[0])) / 2.0
        center_y = (float(bounds_min[1]) + float(bounds_max[1])) / 2.0

        positions: List[List[float]] = []
        pegs = []

        if dual_feet_pegs:
            dx = float(foot_offset_mm)
            pos1 = [center_x - dx, center_y, min_z - peg_h / 2.0]
            pos2 = [center_x + dx, center_y, min_z - peg_h / 2.0]
            positions = [[center_x - dx, center_y, min_z], [center_x + dx, center_y, min_z]]

            if peg_shape == "square":
                peg1 = trimesh.creation.box(extents=[peg_diameter_mm, peg_diameter_mm, peg_h + 2.0])
                peg2 = trimesh.creation.box(extents=[peg_diameter_mm, peg_diameter_mm, peg_h + 2.0])
            else:
                peg1 = trimesh.creation.cylinder(radius=peg_r, height=peg_h + 2.0, sections=32)
                peg2 = trimesh.creation.cylinder(radius=peg_r, height=peg_h + 2.0, sections=32)

            peg1.apply_translation([center_x - dx, center_y, min_z - peg_h / 2.0 + 1.0])
            peg2.apply_translation([center_x + dx, center_y, min_z - peg_h / 2.0 + 1.0])
            pegs.extend([peg1, peg2])
        else:
            positions = [[center_x, center_y, min_z]]
            if peg_shape == "square":
                peg = trimesh.creation.box(extents=[peg_diameter_mm, peg_diameter_mm, peg_h + 2.0])
            else:
                peg = trimesh.creation.cylinder(radius=peg_r, height=peg_h + 2.0, sections=32)
            peg.apply_translation([center_x, center_y, min_z - peg_h / 2.0 + 1.0])
            pegs.append(peg)

        output_mesh = mesh.copy()
        if pegs:
            try:
                peg_union = trimesh.util.concatenate(pegs) if len(pegs) > 1 else pegs[0]
                merged = trimesh.boolean.union([output_mesh, peg_union])
                if merged is not None and len(merged.faces) > 0:
                    output_mesh = merged
                    output_mesh.fix_normals()
                else:
                    output_mesh = trimesh.util.concatenate([output_mesh, peg_union])
            except Exception:
                output_mesh = trimesh.util.concatenate([output_mesh, trimesh.util.concatenate(pegs)])

        return output_mesh, positions, peg_diameter_mm, peg_length_mm


figureforge_service = FigureForgeService()
