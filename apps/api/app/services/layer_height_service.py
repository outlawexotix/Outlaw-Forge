"""
Adaptive Layer Height Profiler Service
Optimizes layer thickness distribution based on surface slope angle across Z height.
Inspired by OrcaSlicer / PrusaSlicer adaptive variable layer height engine.
"""

from typing import List, Tuple
import numpy as np
import trimesh

from app.models.calibration import AdaptiveLayerCurvePoint, AdaptiveLayerPayload, AdaptiveLayerResult


class LayerHeightService:
    """Analyzes mesh curvature per Z-height to generate optimized adaptive layer height profile."""

    def compute_adaptive_profile(
        self, mesh: trimesh.Trimesh, model_id: str, payload: AdaptiveLayerPayload
    ) -> AdaptiveLayerResult:
        """
        Computes the adaptive layer curve and print time savings metrics.
        """
        h_min = payload.min_layer_height_mm
        h_max = payload.max_layer_height_mm
        h_nom = payload.nominal_layer_height_mm
        step = payload.step_size_mm
        smoothness = payload.smoothness_factor

        bounds = mesh.bounds
        z_min = float(bounds[0][2])
        z_max = float(bounds[1][2])
        total_height = max(0.1, z_max - z_min)

        # 1. Sample Z heights and compute local facet slope
        # Face centers and face normal z components
        triangles = mesh.triangles
        face_centers_z = np.mean(triangles[:, :, 2], axis=1)
        face_normals = mesh.face_normals
        face_areas = mesh.area_faces

        # Normal |nz| component: |nz| ~ 1 is flat horizontal; |nz| ~ 0 is vertical wall
        abs_nz = np.abs(face_normals[:, 2])
        # Slope angle from horizontal in degrees (90 = vertical wall, 0 = flat top/bottom)
        slope_deg_arr = np.degrees(np.arccos(np.clip(abs_nz, 0.0, 1.0)))

        # 2. Build adaptive layers from z_min to z_max
        curr_z = z_min
        layer_curve: List[AdaptiveLayerCurvePoint] = []
        layer_idx = 0

        # Discretization sampling window
        sample_window = max(1.0, h_nom * 4)

        while curr_z < z_max - 1e-4:
            # Find faces intersecting or near current Z window
            mask = (face_centers_z >= curr_z - sample_window / 2) & (face_centers_z <= curr_z + sample_window / 2)

            if np.any(mask) and np.sum(face_areas[mask]) > 1e-6:
                weights = face_areas[mask]
                avg_slope = float(np.average(slope_deg_arr[mask], weights=weights))
            else:
                avg_slope = 45.0

            # Vertical walls (slope near 90) -> max layer height (coarser, faster)
            # Shallow curves / domes (slope 10 - 60) -> min layer height (finer, smoother)
            slope_factor = np.clip(avg_slope / 90.0, 0.0, 1.0)
            target_h = h_min + (h_max - h_min) * (slope_factor ** 1.5)

            # Quantize to step size
            quantized_h = h_min + np.round((target_h - h_min) / step) * step
            quantized_h = float(np.clip(quantized_h, h_min, h_max))

            # Apply smoothing with previous layer if available
            if layer_curve and smoothness > 0:
                prev_h = layer_curve[-1].layer_height_mm
                quantized_h = float(prev_h * smoothness + quantized_h * (1.0 - smoothness))
                quantized_h = float(np.clip(quantized_h, h_min, h_max))

            layer_curve.append(
                AdaptiveLayerCurvePoint(
                    z_height_mm=round(curr_z - z_min, 3),
                    layer_height_mm=round(quantized_h, 3),
                    slope_deg=round(avg_slope, 1),
                    layer_index=layer_idx,
                )
            )

            curr_z += quantized_h
            layer_idx += 1

        total_layers_adaptive = len(layer_curve)
        total_layers_nominal = max(1, int(np.ceil(total_height / h_nom)))

        # Time estimation heuristic: nominal print time is proportional to total layers
        # with average layer duration base
        base_sec_per_layer = 25.0
        est_time_nominal_min = round((total_layers_nominal * base_sec_per_layer) / 60.0, 1)
        est_time_adaptive_min = round((total_layers_adaptive * base_sec_per_layer) / 60.0, 1)

        if est_time_nominal_min > 0:
            time_savings_pct = round(
                ((est_time_nominal_min - est_time_adaptive_min) / est_time_nominal_min) * 100.0, 1
            )
        else:
            time_savings_pct = 0.0

        message = (
            f"Adaptive layer profiling complete: {total_layers_adaptive} adaptive layers vs "
            f"{total_layers_nominal} nominal layers ({abs(time_savings_pct):.1f}% "
            f"{'time savings' if time_savings_pct >= 0 else 'fidelity increase'})."
        )

        return AdaptiveLayerResult(
            model_id=model_id,
            total_layers_nominal=total_layers_nominal,
            total_layers_adaptive=total_layers_adaptive,
            estimated_time_nominal_min=est_time_nominal_min,
            estimated_time_adaptive_min=est_time_adaptive_min,
            time_savings_pct=time_savings_pct,
            layer_curve=layer_curve,
            message=message,
        )


layer_height_service = LayerHeightService()
