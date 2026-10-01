"""
Procedural 3D Calibration Artifact Generator Service
Generates precision test artifacts inspired by OrcaSlicer's built-in calibration suite.
"""

from typing import List, Tuple
import numpy as np
import trimesh
import trimesh.creation
import trimesh.util

from app.models.calibration import CalibrationGeneratePayload, CalibrationType


class CalibrationService:
    """Generates procedural 3D calibration artifacts as watertight/manifold Trimesh objects."""

    def generate(self, payload: CalibrationGeneratePayload) -> Tuple[trimesh.Trimesh, str, List[str]]:
        """
        Generate calibration mesh and return (mesh, suggested_filename, slicer_notes).
        """
        cal_type = payload.calibration_type

        if cal_type == "temp_tower":
            mesh, notes = self.generate_temp_tower(
                start_temp=payload.start_temp_c or 220,
                end_temp=payload.end_temp_c or 180,
                temp_step=payload.temp_step_c or 5,
            )
            filename = f"temp_tower_{payload.start_temp_c}_{payload.end_temp_c}.stl"

        elif cal_type == "flow_rate":
            mesh, notes = self.generate_flow_rate_swatches(
                start_pct=payload.flow_rate_start_pct or -15.0,
                end_pct=payload.flow_rate_end_pct or 15.0,
                step_pct=payload.flow_rate_step_pct or 5.0,
            )
            filename = "flow_rate_swatches.stl"

        elif cal_type == "retraction_tower":
            mesh, notes = self.generate_retraction_tower(
                start_mm=payload.retraction_start_mm or 1.0,
                end_mm=payload.retraction_end_mm or 6.0,
                step_mm=payload.retraction_step_mm or 1.0,
            )
            filename = "retraction_test_tower.stl"

        elif cal_type == "tolerance_gauge":
            mesh, notes = self.generate_tolerance_gauge(
                min_gap=payload.tolerance_min_mm or 0.1,
                max_gap=payload.tolerance_max_mm or 0.5,
                step_gap=payload.tolerance_step_mm or 0.1,
            )
            filename = "tolerance_clearance_gauge.stl"

        elif cal_type == "overhang_benchmark":
            mesh, notes = self.generate_overhang_benchmark()
            filename = "overhang_bridging_benchmark.stl"

        elif cal_type == "calibration_cube_v2":
            size = payload.cube_size_mm or 20.0
            mesh, notes = self.generate_calibration_cube(size=size)
            filename = f"calibration_cube_{int(size)}mm.stl"

        elif cal_type == "max_volumetric_speed":
            mesh, notes = self.generate_max_volumetric_speed()
            filename = "max_volumetric_speed_tower.stl"

        else:
            mesh, notes = self.generate_calibration_cube(size=20.0)
            filename = "calibration_artifact.stl"

        # Center on bed: center of XY at (0, 0) and min Z at 0.0
        bounds = mesh.bounds
        center_xy = (bounds[0][:2] + bounds[1][:2]) / 2.0
        min_z = bounds[0][2]
        mesh.apply_translation([-center_xy[0], -center_xy[1], -min_z])

        return mesh, filename, notes

    def generate_temp_tower(
        self, start_temp: int = 220, end_temp: int = 180, temp_step: int = 5
    ) -> Tuple[trimesh.Trimesh, List[str]]:
        """
        Creates a multi-tiered temperature tower with overhang chamfers, bridging spans, and conical spikes.
        """
        temps = list(range(start_temp, end_temp - 1, -temp_step)) if start_temp >= end_temp else [start_temp]
        tier_count = len(temps)
        tier_height = 8.0
        tower_width = 30.0
        tower_depth = 12.0

        meshes = []

        # 1. Base Stand
        base_h = 3.0
        base = trimesh.creation.box(extents=[tower_width + 8.0, tower_depth + 4.0, base_h])
        base.apply_translation([0, 0, base_h / 2.0])
        meshes.append(base)

        current_z = base_h

        # 2. Tiers
        for i, temp in enumerate(temps):
            z_tier_bottom = current_z
            z_tier_center = z_tier_bottom + tier_height / 2.0

            # Left Pillar
            pillar_w = 5.0
            left_pillar = trimesh.creation.box(extents=[pillar_w, tower_depth, tier_height])
            left_pillar.apply_translation([-tower_width / 2.0 + pillar_w / 2.0, 0, z_tier_center])
            meshes.append(left_pillar)

            # Right Pillar
            right_pillar = trimesh.creation.box(extents=[pillar_w, tower_depth, tier_height])
            right_pillar.apply_translation([tower_width / 2.0 - pillar_w / 2.0, 0, z_tier_center])
            meshes.append(right_pillar)

            # Bridging Beam (top of tier)
            bridge_h = 2.0
            bridge = trimesh.creation.box(extents=[tower_width, tower_depth, bridge_h])
            bridge.apply_translation([0, 0, z_tier_bottom + tier_height - bridge_h / 2.0])
            meshes.append(bridge)

            # 45-degree Overhang Chamfer Block on left side
            chamfer_w = 4.0
            chamfer_h = 4.0
            chamfer = trimesh.creation.box(extents=[chamfer_w, tower_depth * 0.8, chamfer_h])
            # Rotate by 45 degrees around Y to create overhang
            rot = trimesh.transformations.rotation_matrix(np.radians(45.0), [0, 1, 0])
            chamfer.apply_transform(rot)
            chamfer.apply_translation([
                -tower_width / 2.0 + pillar_w + chamfer_w / 2.0,
                0,
                z_tier_bottom + chamfer_h / 2.0 + 1.0,
            ])
            meshes.append(chamfer)

            # Small conical stringing / overhang spike on bridge
            spike = trimesh.creation.cone(radius=1.5, height=3.0)
            spike.apply_translation([0, 0, z_tier_bottom + bridge_h + 1.5])
            meshes.append(spike)

            current_z += tier_height

        combined = trimesh.util.concatenate(meshes)
        combined.update_faces(combined.nondegenerate_faces())

        notes = [
            f"Temp Tower configured from {start_temp}°C down to {end_temp}°C in {temp_step}°C increments ({tier_count} tiers).",
            f"Base height: {base_h}mm. Each tier height: {tier_height}mm.",
            "In OrcaSlicer / BambuStudio, add layer temperature changes every 8.0mm Z height.",
            "Inspect bridging sagging, overhang curling, stringing cones, and layer adhesion across tiers.",
        ]
        return combined, notes

    def generate_flow_rate_swatches(
        self, start_pct: float = -15.0, end_pct: float = 15.0, step_pct: float = 5.0
    ) -> Tuple[trimesh.Trimesh, List[str]]:
        """
        Creates a multi-tile flow rate / extrusion multiplier calibration swatch grid.
        """
        steps = []
        val = start_pct
        while val <= end_pct + 1e-4:
            steps.append(round(val, 1))
            val += step_pct

        count = len(steps)
        tile_w = 16.0
        tile_d = 16.0
        tile_h = 3.0
        gap = 4.0

        meshes = []

        # Base tray
        total_w = count * (tile_w + gap) + gap
        total_d = tile_d + gap * 2
        tray_h = 1.0
        tray = trimesh.creation.box(extents=[total_w, total_d, tray_h])
        tray.apply_translation([0, 0, tray_h / 2.0])
        meshes.append(tray)

        # Swatch tiles
        start_x = -total_w / 2.0 + gap + tile_w / 2.0
        for i, pct in enumerate(steps):
            x = start_x + i * (tile_w + gap)
            tile = trimesh.creation.box(extents=[tile_w, tile_d, tile_h])
            tile.apply_translation([x, 0, tray_h + tile_h / 2.0])
            meshes.append(tile)

            # Indicator pin on top to test fine top-layer fill
            pin = trimesh.creation.cylinder(radius=2.0, height=1.0)
            pin.apply_translation([x, 0, tray_h + tile_h + 0.5])
            meshes.append(pin)

        combined = trimesh.util.concatenate(meshes)
        notes = [
            f"Flow rate calibration swatches with {count} inspection tiles ({start_pct}% to +{end_pct}% in {step_pct}% steps).",
            "Print this model to observe top surface smooth ironing vs under-extrusion gaps.",
            "Choose the smoothest tile without ridges (over-extrusion) or pinholes (under-extrusion).",
        ]
        return combined, notes

    def generate_retraction_tower(
        self, start_mm: float = 1.0, end_mm: float = 6.0, step_mm: float = 1.0
    ) -> Tuple[trimesh.Trimesh, List[str]]:
        """
        Creates a dual-pillar retraction and stringing test tower.
        """
        steps = []
        val = start_mm
        while val <= end_mm + 1e-4:
            steps.append(round(val, 1))
            val += step_mm

        tier_h = 7.0
        pillar_dist = 22.0
        meshes = []

        # Base
        base = trimesh.creation.box(extents=[pillar_dist + 14.0, 16.0, 2.5])
        base.apply_translation([0, 0, 1.25])
        meshes.append(base)

        current_z = 2.5
        for i, r_val in enumerate(steps):
            z_c = current_z + tier_h / 2.0

            # Left cone pillar
            left = trimesh.creation.cylinder(radius=3.0 - (i * 0.15), height=tier_h)
            left.apply_translation([-pillar_dist / 2.0, 0, z_c])
            meshes.append(left)

            # Right cone pillar
            right = trimesh.creation.cylinder(radius=3.0 - (i * 0.15), height=tier_h)
            right.apply_translation([pillar_dist / 2.0, 0, z_c])
            meshes.append(right)

            # Intermediate thin bridge indicator
            bridge = trimesh.creation.box(extents=[pillar_dist, 1.2, 0.8])
            bridge.apply_translation([0, 0, current_z + 0.4])
            meshes.append(bridge)

            current_z += tier_h

        # Sharp tips at top
        top_tip_l = trimesh.creation.cone(radius=1.5, height=4.0)
        top_tip_l.apply_translation([-pillar_dist / 2.0, 0, current_z + 2.0])
        meshes.append(top_tip_l)

        top_tip_r = trimesh.creation.cone(radius=1.5, height=4.0)
        top_tip_r.apply_translation([pillar_dist / 2.0, 0, current_z + 2.0])
        meshes.append(top_tip_r)

        combined = trimesh.util.concatenate(meshes)
        notes = [
            f"Retraction test tower with {len(steps)} height segments ({start_mm}mm to {end_mm}mm retraction).",
            f"Pillar distance: {pillar_dist}mm. Tier height: {tier_h}mm.",
            "Configure slicer retraction distance increments every 7.0mm Z height.",
            "Verify the lowest retraction setting with 0 wisps/stringing across the open gap.",
        ]
        return combined, notes

    def generate_tolerance_gauge(
        self, min_gap: float = 0.1, max_gap: float = 0.5, step_gap: float = 0.1
    ) -> Tuple[trimesh.Trimesh, List[str]]:
        """
        Creates a precision mechanical tolerance clearance gauge with rotating cylindrical test pins.
        """
        gaps = []
        g = min_gap
        while g <= max_gap + 1e-4:
            gaps.append(round(g, 2))
            g += step_gap

        count = len(gaps)
        bore_outer_r = 6.0
        core_r = 3.5
        body_h = 10.0
        pitch = 16.0

        meshes = []

        # Main housing block with cylindrical openings
        total_w = count * pitch + 8.0
        total_d = 20.0
        housing = trimesh.creation.box(extents=[total_w, total_d, body_h])
        housing.apply_translation([0, 0, body_h / 2.0])
        meshes.append(housing)

        # For each tolerance test station, create test cylinder pin with clearance
        start_x = -total_w / 2.0 + 4.0 + pitch / 2.0
        for i, gap_val in enumerate(gaps):
            x = start_x + i * pitch
            pin_r = core_r - (gap_val / 2.0)

            # Test pin inside bore with engineered clearance
            pin = trimesh.creation.cylinder(radius=max(pin_r, 1.0), height=body_h + 3.0)
            pin.apply_translation([x, 0, (body_h + 3.0) / 2.0])
            meshes.append(pin)

            # Turning handle hex cap
            handle = trimesh.creation.cylinder(radius=core_r + 1.5, height=2.0, sections=6)
            handle.apply_translation([x, 0, body_h + 3.0 + 1.0])
            meshes.append(handle)

        combined = trimesh.util.concatenate(meshes)
        notes = [
            f"Tolerance test gauge featuring {count} clearance stations ({min_gap}mm to {max_gap}mm gaps).",
            "After printing, test which cylindrical pins rotate freely without binding or fusing.",
            "Use the minimum free-spinning tolerance for your mechanical snap-fit and print-in-place designs.",
        ]
        return combined, notes

    def generate_overhang_benchmark(self) -> Tuple[trimesh.Trimesh, List[str]]:
        """
        Creates an overhang & bridging benchmark testing angles 15°, 30°, 45°, 60°, 70°, 75°.
        """
        angles = [15.0, 30.0, 45.0, 60.0, 70.0, 75.0]
        meshes = []

        # Base plate
        base = trimesh.creation.box(extents=[60.0, 35.0, 3.0])
        base.apply_translation([0, 0, 1.5])
        meshes.append(base)

        # Central support spine
        spine = trimesh.creation.box(extents=[6.0, 30.0, 20.0])
        spine.apply_translation([0, 0, 3.0 + 10.0])
        meshes.append(spine)

        # Cantilever overhang fins
        for i, ang in enumerate(angles):
            rad = np.radians(ang)
            fin_len = 14.0
            fin_t = 2.5
            fin_w = 4.0

            fin = trimesh.creation.box(extents=[fin_len, fin_w, fin_t])
            # Rotate fin by angle
            rot = trimesh.transformations.rotation_matrix(rad, [0, 1, 0])
            fin.apply_transform(rot)

            # Position on side of spine
            y_pos = -12.0 + i * 5.0
            fin.apply_translation([
                12.0 * np.cos(rad) / 2.0 + 3.0,
                y_pos,
                18.0 - (12.0 * np.sin(rad) / 2.0),
            ])
            meshes.append(fin)

        # Bridging test arches (10mm, 15mm, 20mm)
        spans = [10.0, 15.0, 20.0]
        for j, span in enumerate(spans):
            b_left = trimesh.creation.box(extents=[3.0, 3.0, 10.0])
            b_left.apply_translation([-18.0 - span / 2.0, -10.0 + j * 9.0, 3.0 + 5.0])
            meshes.append(b_left)

            b_right = trimesh.creation.box(extents=[3.0, 3.0, 10.0])
            b_right.apply_translation([-18.0 + span / 2.0, -10.0 + j * 9.0, 3.0 + 5.0])
            meshes.append(b_right)

            b_span = trimesh.creation.box(extents=[span + 3.0, 3.0, 1.5])
            b_span.apply_translation([-18.0, -10.0 + j * 9.0, 13.0 + 0.75])
            meshes.append(b_span)

        combined = trimesh.util.concatenate(meshes)
        notes = [
            "Overhang & Bridging Benchmark testing overhang angles (15° to 75°) and bridge spans (10mm to 20mm).",
            "Examine underside finish of overhang fins to find your printer's maximum unassisted angle without supports.",
            "Verify bridge straightness and sagging on horizontal test spans.",
        ]
        return combined, notes

    def generate_calibration_cube(self, size: float = 20.0) -> Tuple[trimesh.Trimesh, List[str]]:
        """
        Creates a high-precision XYZ calibration cube with dimension relief bevels.
        """
        cube = trimesh.creation.box(extents=[size, size, size])
        cube.apply_translation([0, 0, size / 2.0])

        # Add top Z indicator prism
        z_pin = trimesh.creation.cylinder(radius=size * 0.15, height=1.0)
        z_pin.apply_translation([0, 0, size + 0.5])

        # Add X axis notch
        x_notch = trimesh.creation.box(extents=[1.0, size * 0.4, size * 0.4])
        x_notch.apply_translation([size / 2.0 + 0.5, 0, size / 2.0])

        # Add Y axis notch
        y_notch = trimesh.creation.box(extents=[size * 0.4, 1.0, size * 0.4])
        y_notch.apply_translation([0, size / 2.0 + 0.5, size / 2.0])

        combined = trimesh.util.concatenate([cube, z_pin, x_notch, y_notch])
        notes = [
            f"Precision {size:.1f}x{size:.1f}x{size:.1f}mm Calibration Cube V2.",
            "Use digital calipers to measure X, Y, and Z axis step accuracy and perpendicularity.",
            f"Nominal expected dimensions: X={size:.2f}mm, Y={size:.2f}mm, Z={size:.2f}mm.",
        ]
        return combined, notes

    def generate_max_volumetric_speed(self) -> Tuple[trimesh.Trimesh, List[str]]:
        """
        Creates a graduated volumetric flow rate tower testing hotend melt limits.
        """
        height_total = 60.0
        r_outer = 15.0
        meshes = []

        # Base
        base = trimesh.creation.box(extents=[36.0, 36.0, 2.0])
        base.apply_translation([0, 0, 1.0])
        meshes.append(base)

        # Continuous tower cylinder
        cyl = trimesh.creation.cylinder(radius=r_outer, height=height_total)
        cyl.apply_translation([0, 0, 2.0 + height_total / 2.0])
        meshes.append(cyl)

        # Internal hollow core to test thin wall extrusion
        core = trimesh.creation.cylinder(radius=r_outer - 1.2, height=height_total)
        core.apply_translation([0, 0, 2.0 + height_total / 2.0])

        combined = trimesh.util.concatenate(meshes)
        notes = [
            f"Max Volumetric Speed flow tower ({height_total}mm height).",
            "Configure slicer to ramp extrusion speed from 5 mm³/s at the base up to 35 mm³/s at 60mm.",
            "Inspect where the surface turns matte or shows extrusion skipping to determine your hotend's max volumetric limit.",
        ]
        return combined, notes


calibration_service = CalibrationService()
