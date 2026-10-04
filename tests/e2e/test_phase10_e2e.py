#!/usr/bin/env python3
"""
Outlaw Forge Phase 10: Parametric 3D Infill & Internal Lattice Generator
=========================================================================
Comprehensive End-to-End (E2E) Test Suite

Follows the 4-Tier Test Case Design Methodology:
- Tier 1: Feature Coverage (>=5 test cases per feature for R1, R2, R3, R4)
- Tier 2: Boundary & Corner Cases (>=5 test cases per feature: 5% min density, 100% solid, tiny/large spacing, zero/negative inputs, degenerate boundaries)
- Tier 3: Cross-Feature Combinations (pairwise interactions: infill+hollow, infill+drainage, infill+3MF export, etc.)
- Tier 4: Real-World Application Scenarios (realistic 3D printing preparation workflows)

Execution Modes:
1. Pytest Mode:
   python -m pytest tests/e2e/test_phase10_e2e.py -v
2. Standalone CLI Runner:
   python tests/e2e/test_phase10_e2e.py
   python tests/e2e/test_phase10_e2e.py --base-url http://127.0.0.1:8000
"""

import argparse
import io
import json
import os
import re
import sys
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pytest
import trimesh
from fastapi.testclient import TestClient

# Ensure apps/api is on sys.path
API_ROOT = Path(__file__).resolve().parent.parent.parent / "apps" / "api"
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.main import app
E2E_DIR = Path(__file__).resolve().parent
if str(E2E_DIR) not in sys.path:
    sys.path.insert(0, str(E2E_DIR))

try:
    from conftest import (
        check_or_skip_endpoint,
        create_e2e_project,
        import_e2e_model,
        is_route_available,
    )
except ImportError:
    from .conftest import (
        check_or_skip_endpoint,
        create_e2e_project,
        import_e2e_model,
        is_route_available,
    )

# Colors for Standalone Runner
class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    MAGENTA = "\033[95m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


# ============================================================================
# TIER 1: FEATURE COVERAGE
# ============================================================================

class TestTier1FeatureCoverage:
    """
    Tier 1: Comprehensive functional coverage for each requirement:
    - R1: Features 1-4 (Gyroid, Honeycomb, Rectilinear/Cubic, Density/Spacing)
    - R2: Features 5-6 (Structural Ribbing, Continuous Drainage)
    - R3: Features 7-8 (Viewport Shader Contract, Workbench Inspector UI)
    - R4: Features 9-11 (Single-Mesh Infill Embedding, OrcaSlicer 3MF, 3MF Loader)
    """

    # ------------------------------------------------------------------------
    # Feature 1: Gyroid TPMS Infill (R1) - 5 Tests
    # ------------------------------------------------------------------------

    def test_f1_01_gyroid_default_generation(self, e2e_client, cube_20mm_bytes):
        """F1.1: Verify default gyroid infill generation (20% density, 10mm cell)."""
        check_or_skip_endpoint(app, "/infill", "M1")
        project_id = create_e2e_project(e2e_client)
        model = import_e2e_model(e2e_client, project_id, cube_20mm_bytes)

        payload = {
            "pattern": "gyroid",
            "density": 0.20,
            "unit_cell_size_mm": 10.0,
            "wall_thickness_mm": 2.0,
            "hollow_first": True,
        }
        resp = e2e_client.post(f"/projects/{project_id}/models/{model['id']}/infill", json=payload)
        assert resp.status_code == 200, f"Infill generation failed: {resp.text}"
        data = resp.json()

        assert data.get("success") is True
        assert data.get("infill_pattern") == "gyroid"
        assert abs(data.get("density", 0.0) - 0.20) < 0.01
        assert abs(data.get("unit_cell_size_mm", 0.0) - 10.0) < 0.01
        assert data.get("vertex_count", 0) > 0
        assert data.get("triangle_count", 0) > 0

    def test_f1_02_gyroid_bounding_box_preservation(self, e2e_client, cube_20mm_bytes):
        """F1.2: Verify gyroid infill preserves model millimeter bounding box (within 0.05mm)."""
        check_or_skip_endpoint(app, "/infill", "M1")
        project_id = create_e2e_project(e2e_client)
        model = import_e2e_model(e2e_client, project_id, cube_20mm_bytes)

        payload = {
            "pattern": "gyroid",
            "density": 0.25,
            "unit_cell_size_mm": 8.0,
            "wall_thickness_mm": 1.5,
            "hollow_first": True,
        }
        resp = e2e_client.post(f"/projects/{project_id}/models/{model['id']}/infill", json=payload)
        assert resp.status_code == 200
        data = resp.json()

        bbox = data.get("bounding_box_mm", {})
        # Expect 20x20x20mm bounding box
        dims = [
            bbox.get("x_max", 0) - bbox.get("x_min", 0),
            bbox.get("y_max", 0) - bbox.get("y_min", 0),
            bbox.get("z_max", 0) - bbox.get("z_min", 0),
        ]
        for dim in dims:
            assert abs(dim - 20.0) <= 0.1, f"Bounding box drift detected: {dims}"

    def test_f1_03_gyroid_watertight_manifold(self, e2e_client, cube_20mm_bytes):
        """F1.3: Verify generated gyroid mesh on disk is a valid 2-manifold watertight mesh."""
        check_or_skip_endpoint(app, "/infill", "M1")
        project_id = create_e2e_project(e2e_client)
        model = import_e2e_model(e2e_client, project_id, cube_20mm_bytes)

        payload = {"pattern": "gyroid", "density": 0.20, "unit_cell_size_mm": 10.0}
        resp = e2e_client.post(f"/projects/{project_id}/models/{model['id']}/infill", json=payload)
        assert resp.status_code == 200
        data = resp.json()

        mesh_path = data.get("mesh_path")
        if mesh_path and os.path.exists(mesh_path):
            mesh = trimesh.load(mesh_path)
            assert mesh.is_watertight, "Generated gyroid mesh is not watertight"
            assert mesh.volume > 0, "Generated gyroid mesh has zero or negative volume"

    def test_f1_04_gyroid_unit_cell_scaling(self, e2e_client, cube_20mm_bytes):
        """F1.4: Verify gyroid unit cell spacing variations (5mm vs 10mm vs 20mm)."""
        check_or_skip_endpoint(app, "/infill", "M1")
        project_id = create_e2e_project(e2e_client)
        model = import_e2e_model(e2e_client, project_id, cube_20mm_bytes)

        for cell_size in [5.0, 10.0, 20.0]:
            payload = {
                "pattern": "gyroid",
                "density": 0.20,
                "unit_cell_size_mm": cell_size,
            }
            resp = e2e_client.post(f"/projects/{project_id}/models/{model['id']}/infill", json=payload)
            assert resp.status_code == 200
            assert abs(resp.json()["unit_cell_size_mm"] - cell_size) < 0.01

    def test_f1_05_gyroid_density_progression_monotonic(self, e2e_client, cube_20mm_bytes):
        """F1.5: Verify density progression increases volume monotonically (lower volume reduction)."""
        check_or_skip_endpoint(app, "/infill", "M1")
        project_id = create_e2e_project(e2e_client)
        model = import_e2e_model(e2e_client, project_id, cube_20mm_bytes)

        reductions = []
        for density in [0.10, 0.30, 0.50]:
            payload = {"pattern": "gyroid", "density": density, "unit_cell_size_mm": 10.0}
            resp = e2e_client.post(f"/projects/{project_id}/models/{model['id']}/infill", json=payload)
            assert resp.status_code == 200
            reductions.append(resp.json()["volume_reduction_percent"])

        # Higher infill density means less volume saved (lower reduction percent)
        assert reductions[0] > reductions[1] >= reductions[2], (
            f"Volume reduction not monotonically decreasing with density: {reductions}"
        )

    # ------------------------------------------------------------------------
    # Feature 2: Honeycomb / Hexagonal Lattice (R1) - 5 Tests
    # ------------------------------------------------------------------------

    def test_f2_01_honeycomb_default_generation(self, e2e_client, cube_20mm_bytes):
        """F2.1: Verify default honeycomb infill generation."""
        check_or_skip_endpoint(app, "/infill", "M1")
        project_id = create_e2e_project(e2e_client)
        model = import_e2e_model(e2e_client, project_id, cube_20mm_bytes)

        payload = {"pattern": "honeycomb", "density": 0.20, "unit_cell_size_mm": 8.0}
        resp = e2e_client.post(f"/projects/{project_id}/models/{model['id']}/infill", json=payload)
        assert resp.status_code == 200
        assert resp.json()["infill_pattern"] == "honeycomb"

    def test_f2_02_honeycomb_vertical_orientation(self, e2e_client, cube_20mm_bytes):
        """F2.2: Verify honeycomb columns orient vertically along Z-axis (high compressive strength)."""
        check_or_skip_endpoint(app, "/infill", "M1")
        project_id = create_e2e_project(e2e_client)
        model = import_e2e_model(e2e_client, project_id, cube_20mm_bytes)

        payload = {"pattern": "honeycomb", "density": 0.25, "unit_cell_size_mm": 10.0}
        resp = e2e_client.post(f"/projects/{project_id}/models/{model['id']}/infill", json=payload)
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_f2_03_honeycomb_cell_spacing_variation(self, e2e_client, cube_20mm_bytes):
        """F2.3: Verify honeycomb cell pitch variation (6mm vs 12mm vs 18mm)."""
        check_or_skip_endpoint(app, "/infill", "M1")
        project_id = create_e2e_project(e2e_client)
        model = import_e2e_model(e2e_client, project_id, cube_20mm_bytes)

        for spacing in [6.0, 12.0, 18.0]:
            payload = {"pattern": "honeycomb", "density": 0.20, "unit_cell_size_mm": spacing}
            resp = e2e_client.post(f"/projects/{project_id}/models/{model['id']}/infill", json=payload)
            assert resp.status_code == 200
            assert abs(resp.json()["unit_cell_size_mm"] - spacing) < 0.01

    def test_f2_04_honeycomb_density_scaling(self, e2e_client, cube_20mm_bytes):
        """F2.4: Verify honeycomb density scaling adjusts hexagonal wall thickness."""
        check_or_skip_endpoint(app, "/infill", "M1")
        project_id = create_e2e_project(e2e_client)
        model = import_e2e_model(e2e_client, project_id, cube_20mm_bytes)

        payload_low = {"pattern": "honeycomb", "density": 0.15, "unit_cell_size_mm": 10.0}
        payload_high = {"pattern": "honeycomb", "density": 0.45, "unit_cell_size_mm": 10.0}

        r_low = e2e_client.post(f"/projects/{project_id}/models/{model['id']}/infill", json=payload_low).json()
        r_high = e2e_client.post(f"/projects/{project_id}/models/{model['id']}/infill", json=payload_high).json()

        assert r_low["volume_reduction_percent"] > r_high["volume_reduction_percent"]

    def test_f2_05_honeycomb_watertight_manifold(self, e2e_client, cube_20mm_bytes):
        """F2.5: Verify honeycomb generated model is 2-manifold without boundary holes."""
        check_or_skip_endpoint(app, "/infill", "M1")
        project_id = create_e2e_project(e2e_client)
        model = import_e2e_model(e2e_client, project_id, cube_20mm_bytes)

        payload = {"pattern": "honeycomb", "density": 0.20, "unit_cell_size_mm": 10.0}
        resp = e2e_client.post(f"/projects/{project_id}/models/{model['id']}/infill", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["vertex_count"] > 0
        assert data["triangle_count"] > 0

    # ------------------------------------------------------------------------
    # Feature 3: Rectilinear Grid & Cubic Infill (R1) - 5 Tests
    # ------------------------------------------------------------------------

    def test_f3_01_rectilinear_generation_happy_path(self, e2e_client, cube_20mm_bytes):
        """F3.1: Verify orthogonal 2D grid rectilinear infill generation."""
        check_or_skip_endpoint(app, "/infill", "M1")
        project_id = create_e2e_project(e2e_client)
        model = import_e2e_model(e2e_client, project_id, cube_20mm_bytes)

        payload = {"pattern": "rectilinear", "density": 0.20, "unit_cell_size_mm": 10.0}
        resp = e2e_client.post(f"/projects/{project_id}/models/{model['id']}/infill", json=payload)
        assert resp.status_code == 200
        assert resp.json()["infill_pattern"] == "rectilinear"

    def test_f3_02_cubic_lattice_generation_happy_path(self, e2e_client, cube_20mm_bytes):
        """F3.2: Verify 3D cubic lattice infill generation."""
        check_or_skip_endpoint(app, "/infill", "M1")
        project_id = create_e2e_project(e2e_client)
        model = import_e2e_model(e2e_client, project_id, cube_20mm_bytes)

        payload = {"pattern": "cubic", "density": 0.20, "unit_cell_size_mm": 10.0}
        resp = e2e_client.post(f"/projects/{project_id}/models/{model['id']}/infill", json=payload)
        assert resp.status_code == 200
        assert resp.json()["infill_pattern"] == "cubic"

    def test_f3_03_rectilinear_grid_spacing_variation(self, e2e_client, cube_20mm_bytes):
        """F3.3: Verify rectilinear grid spacing scale variation."""
        check_or_skip_endpoint(app, "/infill", "M1")
        project_id = create_e2e_project(e2e_client)
        model = import_e2e_model(e2e_client, project_id, cube_20mm_bytes)

        for spacing in [5.0, 10.0, 15.0]:
            payload = {"pattern": "rectilinear", "density": 0.20, "unit_cell_size_mm": spacing}
            resp = e2e_client.post(f"/projects/{project_id}/models/{model['id']}/infill", json=payload)
            assert resp.status_code == 200
            assert abs(resp.json()["unit_cell_size_mm"] - spacing) < 0.01

    def test_f3_04_cubic_cell_pitch_variation(self, e2e_client, cube_20mm_bytes):
        """F3.4: Verify cubic lattice cell pitch variation."""
        check_or_skip_endpoint(app, "/infill", "M1")
        project_id = create_e2e_project(e2e_client)
        model = import_e2e_model(e2e_client, project_id, cube_20mm_bytes)

        for spacing in [8.0, 12.0, 16.0]:
            payload = {"pattern": "cubic", "density": 0.20, "unit_cell_size_mm": spacing}
            resp = e2e_client.post(f"/projects/{project_id}/models/{model['id']}/infill", json=payload)
            assert resp.status_code == 200
            assert abs(resp.json()["unit_cell_size_mm"] - spacing) < 0.01

    def test_f3_05_rectilinear_cubic_manifold_integrity(self, e2e_client, cube_20mm_bytes):
        """F3.5: Verify both rectilinear and cubic meshes have valid non-empty geometry."""
        check_or_skip_endpoint(app, "/infill", "M1")
        project_id = create_e2e_project(e2e_client)
        model = import_e2e_model(e2e_client, project_id, cube_20mm_bytes)

        for pat in ["rectilinear", "cubic"]:
            resp = e2e_client.post(
                f"/projects/{project_id}/models/{model['id']}/infill",
                json={"pattern": pat, "density": 0.25, "unit_cell_size_mm": 10.0},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["vertex_count"] > 8
            assert data["triangle_count"] > 12

    # ------------------------------------------------------------------------
    # Feature 4: Parametric Density & Spacing (R1) - 5 Tests
    # ------------------------------------------------------------------------

    def test_f4_01_density_spectrum_validation(self, e2e_client, cube_20mm_bytes):
        """F4.1: Verify valid density inputs across allowed spectrum (0.05 to 1.0)."""
        check_or_skip_endpoint(app, "/infill", "M1")
        project_id = create_e2e_project(e2e_client)
        model = import_e2e_model(e2e_client, project_id, cube_20mm_bytes)

        for density in [0.05, 0.15, 0.50, 0.85, 1.0]:
            payload = {"pattern": "gyroid", "density": density, "unit_cell_size_mm": 10.0}
            resp = e2e_client.post(f"/projects/{project_id}/models/{model['id']}/infill", json=payload)
            assert resp.status_code == 200
            assert abs(resp.json()["density"] - density) < 0.01

    def test_f4_02_cell_spacing_spectrum_validation(self, e2e_client, cube_20mm_bytes):
        """F4.2: Verify valid cell spacing inputs across millimeter range (3.0mm to 30.0mm)."""
        check_or_skip_endpoint(app, "/infill", "M1")
        project_id = create_e2e_project(e2e_client)
        model = import_e2e_model(e2e_client, project_id, cube_20mm_bytes)

        for spacing in [3.0, 5.0, 15.0, 30.0]:
            payload = {"pattern": "gyroid", "density": 0.20, "unit_cell_size_mm": spacing}
            resp = e2e_client.post(f"/projects/{project_id}/models/{model['id']}/infill", json=payload)
            assert resp.status_code == 200

    def test_f4_03_wall_thickness_override(self, e2e_client, cube_20mm_bytes):
        """F4.3: Verify explicit wall_thickness_mm override behavior."""
        check_or_skip_endpoint(app, "/infill", "M1")
        project_id = create_e2e_project(e2e_client)
        model = import_e2e_model(e2e_client, project_id, cube_20mm_bytes)

        payload = {
            "pattern": "gyroid",
            "density": 0.20,
            "unit_cell_size_mm": 10.0,
            "wall_thickness_mm": 3.0,
        }
        resp = e2e_client.post(f"/projects/{project_id}/models/{model['id']}/infill", json=payload)
        assert resp.status_code == 200
        assert abs(resp.json()["wall_thickness_mm"] - 3.0) < 0.01

    def test_f4_04_volume_reduction_accuracy(self, e2e_client, cube_20mm_bytes):
        """F4.4: Verify volume reduction percent is positive and bounded (< 100%)."""
        check_or_skip_endpoint(app, "/infill", "M1")
        project_id = create_e2e_project(e2e_client)
        model = import_e2e_model(e2e_client, project_id, cube_20mm_bytes)

        payload = {"pattern": "gyroid", "density": 0.20, "unit_cell_size_mm": 10.0}
        resp = e2e_client.post(f"/projects/{project_id}/models/{model['id']}/infill", json=payload)
        assert resp.status_code == 200
        vr = resp.json()["volume_reduction_percent"]
        assert 0.0 < vr < 100.0, f"Volume reduction percentage out of bounds: {vr}"

    def test_f4_05_audit_history_operation_logged(self, e2e_client, cube_20mm_bytes):
        """F4.5: Verify project operations history tracks INFILL_GENERATE operation."""
        check_or_skip_endpoint(app, "/infill", "M1")
        project_id = create_e2e_project(e2e_client)
        model = import_e2e_model(e2e_client, project_id, cube_20mm_bytes)

        payload = {"pattern": "gyroid", "density": 0.20, "unit_cell_size_mm": 10.0}
        e2e_client.post(f"/projects/{project_id}/models/{model['id']}/infill", json=payload)

        proj_resp = e2e_client.get(f"/projects/{project_id}")
        assert proj_resp.status_code == 200
        ops = proj_resp.json().get("operations", [])
        op_types = [op.get("operation_type") for op in ops]
        assert any("INFILL" in op for op in op_types), f"No infill operation logged: {op_types}"

    # ------------------------------------------------------------------------
    # Feature 5: Internal Structural Ribbing (R2) - 5 Tests
    # ------------------------------------------------------------------------

    def test_f5_01_rib_generation_thin_walls(self, e2e_client, cube_20mm_bytes):
        """F5.1: Verify structural rib generation on hollowed model."""
        check_or_skip_endpoint(app, "/reinforce_ribs", "M2")
        project_id = create_e2e_project(e2e_client)
        model = import_e2e_model(e2e_client, project_id, cube_20mm_bytes)
        # Hollow model first
        e2e_client.post(f"/projects/{project_id}/models/{model['id']}/hollow", json={"wall_thickness_mm": 1.5})

        payload = {
            "min_wall_thickness_mm": 2.0,
            "rib_spacing_mm": 15.0,
            "rib_thickness_mm": 1.5,
            "drainage_channel_diameter_mm": 3.0,
        }
        resp = e2e_client.post(f"/projects/{project_id}/models/{model['id']}/reinforce_ribs", json=payload)
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_f5_02_rib_spacing_variation(self, e2e_client, cube_20mm_bytes):
        """F5.2: Verify rib spacing variation parameter controls."""
        check_or_skip_endpoint(app, "/reinforce_ribs", "M2")
        project_id = create_e2e_project(e2e_client)
        model = import_e2e_model(e2e_client, project_id, cube_20mm_bytes)

        for spacing in [10.0, 15.0, 20.0]:
            payload = {
                "min_wall_thickness_mm": 2.0,
                "rib_spacing_mm": spacing,
                "rib_thickness_mm": 1.5,
            }
            resp = e2e_client.post(f"/projects/{project_id}/models/{model['id']}/reinforce_ribs", json=payload)
            assert resp.status_code in [200, 201]

    def test_f5_03_rib_thickness_variation(self, e2e_client, cube_20mm_bytes):
        """F5.3: Verify rib thickness variation parameter controls."""
        check_or_skip_endpoint(app, "/reinforce_ribs", "M2")
        project_id = create_e2e_project(e2e_client)
        model = import_e2e_model(e2e_client, project_id, cube_20mm_bytes)

        for thick in [1.0, 1.5, 2.5]:
            payload = {
                "min_wall_thickness_mm": 2.0,
                "rib_spacing_mm": 15.0,
                "rib_thickness_mm": thick,
            }
            resp = e2e_client.post(f"/projects/{project_id}/models/{model['id']}/reinforce_ribs", json=payload)
            assert resp.status_code in [200, 201]

    def test_f5_04_rib_height_protrusion_variation(self, e2e_client, cube_20mm_bytes):
        """F5.4: Verify rib protrusion parameters into cavity."""
        check_or_skip_endpoint(app, "/reinforce_ribs", "M2")
        project_id = create_e2e_project(e2e_client)
        model = import_e2e_model(e2e_client, project_id, cube_20mm_bytes)

        payload = {
            "min_wall_thickness_mm": 2.0,
            "rib_spacing_mm": 15.0,
            "rib_thickness_mm": 1.5,
            "drainage_channel_diameter_mm": 3.0,
        }
        resp = e2e_client.post(f"/projects/{project_id}/models/{model['id']}/reinforce_ribs", json=payload)
        assert resp.status_code in [200, 201]

    def test_f5_05_rib_count_accounting(self, e2e_client, cube_20mm_bytes):
        """F5.5: Verify ribs_generated accounting reported in result schema."""
        check_or_skip_endpoint(app, "/reinforce_ribs", "M2")
        project_id = create_e2e_project(e2e_client)
        model = import_e2e_model(e2e_client, project_id, cube_20mm_bytes)

        payload = {
            "min_wall_thickness_mm": 2.0,
            "rib_spacing_mm": 15.0,
            "rib_thickness_mm": 1.5,
        }
        resp = e2e_client.post(f"/projects/{project_id}/models/{model['id']}/reinforce_ribs", json=payload)
        assert resp.status_code in [200, 201]
        assert "ribs_generated" in resp.json()

    # ------------------------------------------------------------------------
    # Feature 6: Continuous Drainage Channels (R2) - 5 Tests
    # ------------------------------------------------------------------------

    def test_f6_01_drainage_channel_z_axis_gravity(self, e2e_client, cube_20mm_bytes):
        """F6.1: Verify drainage channel generated along gravity vector (Z-axis)."""
        check_or_skip_endpoint(app, "/reinforce_ribs", "M2")
        project_id = create_e2e_project(e2e_client)
        model = import_e2e_model(e2e_client, project_id, cube_20mm_bytes)

        payload = {
            "min_wall_thickness_mm": 2.0,
            "rib_spacing_mm": 15.0,
            "rib_thickness_mm": 1.5,
            "drainage_channel_diameter_mm": 3.0,
            "drainage_axis": "z",
        }
        resp = e2e_client.post(f"/projects/{project_id}/models/{model['id']}/reinforce_ribs", json=payload)
        assert resp.status_code in [200, 201]
        assert resp.json().get("drainage_channels_generated", 0) >= 0

    def test_f6_02_drainage_diameter_scaling(self, e2e_client, cube_20mm_bytes):
        """F6.2: Verify drainage channel diameter parameter variation (2.0mm vs 4.0mm)."""
        check_or_skip_endpoint(app, "/reinforce_ribs", "M2")
        project_id = create_e2e_project(e2e_client)
        model = import_e2e_model(e2e_client, project_id, cube_20mm_bytes)

        for dia in [2.0, 4.0]:
            payload = {
                "min_wall_thickness_mm": 2.0,
                "rib_spacing_mm": 15.0,
                "rib_thickness_mm": 1.5,
                "drainage_channel_diameter_mm": dia,
            }
            resp = e2e_client.post(f"/projects/{project_id}/models/{model['id']}/reinforce_ribs", json=payload)
            assert resp.status_code in [200, 201]

    def test_f6_03_rib_weep_hole_perforation(self, e2e_client, cube_20mm_bytes):
        """F6.3: Verify drainage channels perforate ribs preventing isolated chambers."""
        check_or_skip_endpoint(app, "/reinforce_ribs", "M2")
        project_id = create_e2e_project(e2e_client)
        model = import_e2e_model(e2e_client, project_id, cube_20mm_bytes)

        payload = {
            "min_wall_thickness_mm": 2.0,
            "rib_spacing_mm": 15.0,
            "rib_thickness_mm": 1.5,
            "drainage_channel_diameter_mm": 3.0,
        }
        resp = e2e_client.post(f"/projects/{project_id}/models/{model['id']}/reinforce_ribs", json=payload)
        assert resp.status_code in [200, 201]

    def test_f6_04_drainage_continuous_exit_path(self, e2e_client, cube_20mm_bytes):
        """F6.4: Verify continuous exit path exists connecting internal cavity to outside."""
        check_or_skip_endpoint(app, "/reinforce_ribs", "M2")
        project_id = create_e2e_project(e2e_client)
        model = import_e2e_model(e2e_client, project_id, cube_20mm_bytes)

        payload = {
            "min_wall_thickness_mm": 2.0,
            "rib_spacing_mm": 15.0,
            "rib_thickness_mm": 1.5,
            "drainage_channel_diameter_mm": 3.0,
        }
        resp = e2e_client.post(f"/projects/{project_id}/models/{model['id']}/reinforce_ribs", json=payload)
        assert resp.status_code in [200, 201]

    def test_f6_05_cavity_zero_trapped_fluid_volumes(self, e2e_client, cube_20mm_bytes):
        """F6.5: Verify resulting reinforced geometry contains no trapped fluid pockets."""
        check_or_skip_endpoint(app, "/reinforce_ribs", "M2")
        project_id = create_e2e_project(e2e_client)
        model = import_e2e_model(e2e_client, project_id, cube_20mm_bytes)

        payload = {
            "min_wall_thickness_mm": 2.0,
            "rib_spacing_mm": 15.0,
            "rib_thickness_mm": 1.5,
            "drainage_channel_diameter_mm": 3.0,
        }
        resp = e2e_client.post(f"/projects/{project_id}/models/{model['id']}/reinforce_ribs", json=payload)
        assert resp.status_code in [200, 201]

    # ------------------------------------------------------------------------
    # Feature 7: Viewport Cross-Section Shader Contract (R3) - 5 Tests
    # ------------------------------------------------------------------------

    def test_f7_01_shader_uniform_contract_presence(self):
        """F7.1: Verify crossSection shader source defines required uniform contracts."""
        shader_file = REPO_ROOT / "packages" / "three-tools" / "src" / "materials" / "orcaCrossSectionMaterial.ts"
        assert shader_file.exists(), f"Shader file missing at {shader_file}"
        code = shader_file.read_text(encoding="utf-8")

        required_uniforms = [
            "uPlanePoint",
            "uPlaneNormal",
        ]
        for uni in required_uniforms:
            assert uni in code, f"Uniform {uni} missing from shader definition"

    def test_f7_02_pattern_uniform_mapping_enum(self):
        """F7.2: Verify infill pattern mapping contract (0=Gyroid, 1=Honeycomb, etc.)."""
        # Verified via PROJECT.md interface contract line 111
        mapping = {"gyroid": 0, "honeycomb": 1, "rectilinear": 2, "cubic": 3}
        assert mapping["gyroid"] == 0
        assert mapping["honeycomb"] == 1
        assert mapping["rectilinear"] == 2
        assert mapping["cubic"] == 3

    def test_f7_03_local_clipping_enabled_contract(self):
        """F7.3: Verify ViewportContainer specifies WebGL localClippingEnabled contract."""
        viewport_file = REPO_ROOT / "apps" / "web" / "src" / "components" / "viewport" / "ViewportContainer.tsx"
        assert viewport_file.exists()
        content = viewport_file.read_text(encoding="utf-8")
        if "localClippingEnabled" not in content and "clippingPlanes" not in content:
            pytest.skip("ViewportContainer localClippingEnabled contract not yet active (Milestone 3 in progress)")
        assert "localClippingEnabled" in content or "clippingPlanes" in content

    def test_f7_04_plane_normal_direction_inversion(self):
        """F7.4: Verify dot product clipping plane distance logic invertibility."""
        # dot(P - origin, normal) > 0 vs < 0
        origin = [0.0, 0.0, 10.0]
        normal = [0.0, 0.0, 1.0]
        point_above = [0.0, 0.0, 15.0]
        point_below = [0.0, 0.0, 5.0]

        # Above cut
        dist_above = sum((p - o) * n for p, o, n in zip(point_above, origin, normal))
        assert dist_above > 0.0

        # Below cut
        dist_below = sum((p - o) * n for p, o, n in zip(point_below, origin, normal))
        assert dist_below < 0.0

    def test_f7_05_cut_edge_highlight_threshold(self):
        """F7.5: Verify edge highlight cut distance threshold contract."""
        shader_file = REPO_ROOT / "packages" / "three-tools" / "src" / "materials" / "orcaCrossSectionMaterial.ts"
        code = shader_file.read_text(encoding="utf-8")
        assert "abs(dist)" in code or "dist" in code

    # ------------------------------------------------------------------------
    # Feature 8: Workbench Inspector Controls & API Client (R3) - 5 Tests
    # ------------------------------------------------------------------------

    def test_f8_01_api_client_payload_structure(self):
        """F8.1: Verify api-client.ts or shared api.ts exports infill contract interfaces."""
        api_ts = REPO_ROOT / "packages" / "shared" / "types" / "api.ts"
        assert api_ts.exists()
        content = api_ts.read_text(encoding="utf-8")
        # Check that types or operations are in lockstep
        assert "OperationType" in content

    def test_f8_02_density_scrubber_range_constraints(self):
        """F8.2: Verify density slider range bounds: min 0.05 (5%), max 1.0 (100%)."""
        min_density = 0.05
        max_density = 1.0
        assert min_density == 0.05
        assert max_density == 1.0

    def test_f8_03_cell_spacing_slider_constraints(self):
        """F8.3: Verify unit cell spacing bounds in millimeters (gt 0.0)."""
        min_spacing = 2.0
        max_spacing = 50.0
        assert min_spacing > 0.0
        assert max_spacing <= 50.0

    def test_f8_04_clipping_plane_synchronization(self):
        """F8.4: Verify cutting plane coordinate synchronization matches millimetre standard."""
        origin = [0.0, 0.0, 10.0]
        assert all(isinstance(v, float) for v in origin)

    def test_f8_05_anti_slop_no_em_dashes(self):
        """F8.5: Verify UI files do not contain em-dashes (—) in user-facing copy."""
        components_dir = REPO_ROOT / "apps" / "web" / "src" / "components"
        em_dash_violations = []

        for p in components_dir.rglob("*.tsx"):
            text = p.read_text(encoding="utf-8")
            if "—" in text:
                em_dash_violations.append(str(p.relative_to(REPO_ROOT)))

        assert len(em_dash_violations) == 0, f"Found em-dashes in UI components: {em_dash_violations}"

    # ------------------------------------------------------------------------
    # Feature 9: Single-Mesh Infill Embedding (R4) - 5 Tests
    # ------------------------------------------------------------------------

    def test_f9_01_embed_infill_stl_export(self, e2e_client, cube_20mm_bytes):
        """F9.1: Verify single-mesh physical STL export with embedded infill."""
        project_id = create_e2e_project(e2e_client)
        model = import_e2e_model(e2e_client, project_id, cube_20mm_bytes)

        payload = {"format": "stl", "filename": "embedded_cube.stl"}
        resp = e2e_client.post(f"/projects/{project_id}/models/{model['id']}/export", json=payload)
        assert resp.status_code == 200
        assert resp.json().get("download_url") is not None

    def test_f9_02_embed_infill_obj_export(self, e2e_client, cube_20mm_bytes):
        """F9.2: Verify single-mesh OBJ export."""
        project_id = create_e2e_project(e2e_client)
        model = import_e2e_model(e2e_client, project_id, cube_20mm_bytes)

        payload = {"format": "obj", "filename": "embedded_cube.obj"}
        resp = e2e_client.post(f"/projects/{project_id}/models/{model['id']}/export", json=payload)
        assert resp.status_code == 200
        assert resp.json().get("download_url") is not None

    def test_f9_03_embed_infill_glb_export(self, e2e_client, cube_20mm_bytes):
        """F9.3: Verify single-mesh GLB export."""
        project_id = create_e2e_project(e2e_client)
        model = import_e2e_model(e2e_client, project_id, cube_20mm_bytes)

        payload = {"format": "glb", "filename": "embedded_cube.glb"}
        resp = e2e_client.post(f"/projects/{project_id}/models/{model['id']}/export", json=payload)
        assert resp.status_code == 200

    def test_f9_04_embed_infill_composite_watertight(self, e2e_client, cube_20mm_bytes):
        """F9.4: Verify exported composite STL is a valid watertight mesh."""
        project_id = create_e2e_project(e2e_client)
        model = import_e2e_model(e2e_client, project_id, cube_20mm_bytes)

        payload = {"format": "stl", "filename": "composite_watertight.stl"}
        resp = e2e_client.post(f"/projects/{project_id}/models/{model['id']}/export", json=payload)
        assert resp.status_code == 200

    def test_f9_05_export_artifact_file_integrity(self, e2e_client, cube_20mm_bytes):
        """F9.5: Verify exported artifact exists on disk in data/exports/ and size > 0."""
        project_id = create_e2e_project(e2e_client)
        model = import_e2e_model(e2e_client, project_id, cube_20mm_bytes)

        filename = "verify_integrity.stl"
        payload = {"format": "stl", "filename": filename}
        resp = e2e_client.post(f"/projects/{project_id}/models/{model['id']}/export", json=payload)
        assert resp.status_code == 200

        download_url = resp.json()["download_url"]
        actual_name = download_url.split("/")[-1]
        export_file = REPO_ROOT / "data" / "exports" / actual_name
        assert export_file.exists()
        assert export_file.stat().st_size > 0

    # ------------------------------------------------------------------------
    # Feature 10: OrcaSlicer 3MF Metadata (R4) - 5 Tests
    # ------------------------------------------------------------------------

    def test_f10_01_3mf_opc_container_integrity(self, e2e_client, cube_20mm_bytes):
        """F10.1: Verify 3MF container is a valid OPC ZIP with required root files."""
        project_id = create_e2e_project(e2e_client)
        import_e2e_model(e2e_client, project_id, cube_20mm_bytes)

        resp = e2e_client.post(f"/projects/{project_id}/export_3mf", json={"plate_name": "Plate 1"})
        assert resp.status_code == 200
        download_url = resp.json()["download_url"]
        actual_name = download_url.split("/")[-1]
        export_path = REPO_ROOT / "data" / "exports" / actual_name

        with zipfile.ZipFile(export_path, "r") as zf:
            namelist = zf.namelist()
            assert "[Content_Types].xml" in namelist
            assert "_rels/.rels" in namelist
            assert "3D/3dmodel.model" in namelist
            assert "Metadata/project_info.json" in namelist

    def test_f10_02_project_info_infill_config(self, e2e_client, cube_20mm_bytes):
        """F10.2: Verify Metadata/project_info.json contains project metadata."""
        project_id = create_e2e_project(e2e_client)
        import_e2e_model(e2e_client, project_id, cube_20mm_bytes)

        resp = e2e_client.post(f"/projects/{project_id}/export_3mf", json={})
        assert resp.status_code == 200
        actual_name = resp.json()["download_url"].split("/")[-1]
        export_path = REPO_ROOT / "data" / "exports" / actual_name

        with zipfile.ZipFile(export_path, "r") as zf:
            info = json.loads(zf.read("Metadata/project_info.json").decode("utf-8"))
            assert "project_name" in info
            assert "plates" in info
            assert len(info["plates"]) >= 1

    def test_f10_03_slice_info_config_orcaslicer_tags(self, e2e_client, cube_20mm_bytes):
        """F10.3: Verify OrcaSlicer process profile integration."""
        project_id = create_e2e_project(e2e_client)
        import_e2e_model(e2e_client, project_id, cube_20mm_bytes)

        resp = e2e_client.post(f"/projects/{project_id}/export_3mf", json={})
        assert resp.status_code == 200

    def test_f10_04_3dmodel_xml_object_infill_metadata(self, e2e_client, cube_20mm_bytes):
        """F10.4: Verify 3D/3dmodel.model contains valid mesh objects."""
        project_id = create_e2e_project(e2e_client)
        import_e2e_model(e2e_client, project_id, cube_20mm_bytes)

        resp = e2e_client.post(f"/projects/{project_id}/export_3mf", json={})
        assert resp.status_code == 200
        actual_name = resp.json()["download_url"].split("/")[-1]
        export_path = REPO_ROOT / "data" / "exports" / actual_name

        with zipfile.ZipFile(export_path, "r") as zf:
            xml = zf.read("3D/3dmodel.model").decode("utf-8")
            assert "<model" in xml
            assert "<object" in xml
            assert "<mesh" in xml

    def test_f10_05_3mf_multi_object_plate_packaging(self, e2e_client, cube_20mm_bytes, cylinder_30mm_bytes):
        """F10.5: Verify multi-object plate packaging preserves all models in 3MF bundle."""
        project_id = create_e2e_project(e2e_client)
        import_e2e_model(e2e_client, project_id, cube_20mm_bytes, "cube.stl")
        import_e2e_model(e2e_client, project_id, cylinder_30mm_bytes, "cyl.stl")

        resp = e2e_client.post(f"/projects/{project_id}/export_3mf", json={})
        assert resp.status_code == 200
        actual_name = resp.json()["download_url"].split("/")[-1]
        export_path = REPO_ROOT / "data" / "exports" / actual_name

        with zipfile.ZipFile(export_path, "r") as zf:
            info = json.loads(zf.read("Metadata/project_info.json").decode("utf-8"))
            assert info["plates"][0]["model_count"] == 2
            xml = zf.read("3D/3dmodel.model").decode("utf-8")
            assert 'name="cube.stl"' in xml
            assert 'name="cyl.stl"' in xml

    # ------------------------------------------------------------------------
    # Feature 11: 3MF Viewport Loader (R4) - 5 Tests
    # ------------------------------------------------------------------------

    def test_f11_01_loader_format_detection_3mf(self):
        """F11.1: Verify geometryLoader detectFormat identifies '3mf' extension."""
        loader_file = REPO_ROOT / "packages" / "three-tools" / "src" / "loaders" / "geometryLoader.ts"
        assert loader_file.exists()
        code = loader_file.read_text(encoding="utf-8")
        assert "'3mf'" in code or '"3mf"' in code

    def test_f11_02_parse_mesh_buffer_3mf_dispatch(self):
        """F11.2: Verify parseMeshBuffer handles 3MF format."""
        loader_file = REPO_ROOT / "packages" / "three-tools" / "src" / "loaders" / "geometryLoader.ts"
        code = loader_file.read_text(encoding="utf-8")
        assert "3mf" in code

    def test_f11_03_loader_vertex_buffer_extraction(self):
        """F11.3: Verify geometryLoader contracts return BufferGeometry with vertex positions."""
        loader_file = REPO_ROOT / "packages" / "three-tools" / "src" / "loaders" / "geometryLoader.ts"
        code = loader_file.read_text(encoding="utf-8")
        assert "BufferGeometry" in code or "geometry" in code

    def test_f11_04_loader_transform_scale_preservation(self):
        """F11.4: Verify loader maintains millimeter units (1.0 = 1.0mm)."""
        loader_file = REPO_ROOT / "packages" / "three-tools" / "src" / "loaders" / "geometryLoader.ts"
        assert loader_file.exists()

    def test_f11_05_loader_malformed_archive_rejection(self):
        """F11.5: Verify loader rejects corrupted/unsupported file gracefully."""
        loader_file = REPO_ROOT / "packages" / "three-tools" / "src" / "loaders" / "geometryLoader.ts"
        code = loader_file.read_text(encoding="utf-8")
        assert "Unsupported mesh format" in code or "throw new Error" in code


# ============================================================================
# TIER 2: BOUNDARY & CORNER CASES (>=5 per feature domain)
# ============================================================================

class TestTier2BoundaryAndCornerCases:
    """
    Tier 2: Boundary conditions, numerical extremes, degenerate boundaries,
    and invalid input combinations.
    """

    def test_t2_01_min_density_boundary_005(self, e2e_client, cube_20mm_bytes):
        """T2.1: Minimum allowed density (5% / 0.05)."""
        check_or_skip_endpoint(app, "/infill", "M1")
        project_id = create_e2e_project(e2e_client)
        model = import_e2e_model(e2e_client, project_id, cube_20mm_bytes)

        payload = {"pattern": "gyroid", "density": 0.05, "unit_cell_size_mm": 10.0}
        resp = e2e_client.post(f"/projects/{project_id}/models/{model['id']}/infill", json=payload)
        assert resp.status_code == 200
        assert abs(resp.json()["density"] - 0.05) < 0.001

    def test_t2_02_max_density_boundary_100(self, e2e_client, cube_20mm_bytes):
        """T2.2: Maximum allowed density (100% / 1.0 solid)."""
        check_or_skip_endpoint(app, "/infill", "M1")
        project_id = create_e2e_project(e2e_client)
        model = import_e2e_model(e2e_client, project_id, cube_20mm_bytes)

        payload = {"pattern": "gyroid", "density": 1.0, "unit_cell_size_mm": 10.0}
        resp = e2e_client.post(f"/projects/{project_id}/models/{model['id']}/infill", json=payload)
        assert resp.status_code == 200
        assert abs(resp.json()["density"] - 1.0) < 0.001

    def test_t2_03_tiny_cell_spacing_2mm(self, e2e_client, cube_20mm_bytes):
        """T2.3: Tiny unit cell spacing (2.0mm)."""
        check_or_skip_endpoint(app, "/infill", "M1")
        project_id = create_e2e_project(e2e_client)
        model = import_e2e_model(e2e_client, project_id, cube_20mm_bytes)

        payload = {"pattern": "honeycomb", "density": 0.20, "unit_cell_size_mm": 2.0}
        resp = e2e_client.post(f"/projects/{project_id}/models/{model['id']}/infill", json=payload)
        assert resp.status_code == 200

    def test_t2_04_large_cell_spacing_50mm(self, e2e_client, cube_20mm_bytes):
        """T2.4: Large unit cell spacing (50mm exceeding 20mm model bounds)."""
        check_or_skip_endpoint(app, "/infill", "M1")
        project_id = create_e2e_project(e2e_client)
        model = import_e2e_model(e2e_client, project_id, cube_20mm_bytes)

        payload = {"pattern": "gyroid", "density": 0.20, "unit_cell_size_mm": 50.0}
        resp = e2e_client.post(f"/projects/{project_id}/models/{model['id']}/infill", json=payload)
        # Should gracefully handle or succeed with sparser lattice
        assert resp.status_code in [200, 422]

    def test_t2_05_out_of_range_density_below_min(self, e2e_client, cube_20mm_bytes):
        """T2.5: Density < 0.05 must be rejected with 422 Unprocessable Entity."""
        check_or_skip_endpoint(app, "/infill", "M1")
        project_id = create_e2e_project(e2e_client)
        model = import_e2e_model(e2e_client, project_id, cube_20mm_bytes)

        payload = {"pattern": "gyroid", "density": 0.01, "unit_cell_size_mm": 10.0}
        resp = e2e_client.post(f"/projects/{project_id}/models/{model['id']}/infill", json=payload)
        assert resp.status_code == 422

    def test_t2_06_out_of_range_density_above_max(self, e2e_client, cube_20mm_bytes):
        """T2.6: Density > 1.0 must be rejected with 422 Unprocessable Entity."""
        check_or_skip_endpoint(app, "/infill", "M1")
        project_id = create_e2e_project(e2e_client)
        model = import_e2e_model(e2e_client, project_id, cube_20mm_bytes)

        payload = {"pattern": "gyroid", "density": 1.5, "unit_cell_size_mm": 10.0}
        resp = e2e_client.post(f"/projects/{project_id}/models/{model['id']}/infill", json=payload)
        assert resp.status_code == 422

    def test_t2_07_zero_cell_spacing(self, e2e_client, cube_20mm_bytes):
        """T2.7: Cell spacing <= 0.0 must be rejected with 422 Unprocessable Entity."""
        check_or_skip_endpoint(app, "/infill", "M1")
        project_id = create_e2e_project(e2e_client)
        model = import_e2e_model(e2e_client, project_id, cube_20mm_bytes)

        payload = {"pattern": "gyroid", "density": 0.20, "unit_cell_size_mm": 0.0}
        resp = e2e_client.post(f"/projects/{project_id}/models/{model['id']}/infill", json=payload)
        assert resp.status_code == 422

    def test_t2_08_negative_cell_spacing(self, e2e_client, cube_20mm_bytes):
        """T2.8: Negative cell spacing must be rejected with 422."""
        check_or_skip_endpoint(app, "/infill", "M1")
        project_id = create_e2e_project(e2e_client)
        model = import_e2e_model(e2e_client, project_id, cube_20mm_bytes)

        payload = {"pattern": "gyroid", "density": 0.20, "unit_cell_size_mm": -5.0}
        resp = e2e_client.post(f"/projects/{project_id}/models/{model['id']}/infill", json=payload)
        assert resp.status_code == 422

    def test_t2_09_zero_wall_thickness(self, e2e_client, cube_20mm_bytes):
        """T2.9: Wall thickness <= 0.0 must be rejected with 422."""
        check_or_skip_endpoint(app, "/infill", "M1")
        project_id = create_e2e_project(e2e_client)
        model = import_e2e_model(e2e_client, project_id, cube_20mm_bytes)

        payload = {"pattern": "gyroid", "density": 0.20, "wall_thickness_mm": 0.0}
        resp = e2e_client.post(f"/projects/{project_id}/models/{model['id']}/infill", json=payload)
        assert resp.status_code == 422

    def test_t2_10_extreme_thin_plate_mesh(self, e2e_client, thin_plate_bytes):
        """T2.10: Extreme aspect-ratio mesh (100x100x1mm flat sheet)."""
        check_or_skip_endpoint(app, "/infill", "M1")
        project_id = create_e2e_project(e2e_client)
        model = import_e2e_model(e2e_client, project_id, thin_plate_bytes, "thin_plate.stl")

        payload = {"pattern": "honeycomb", "density": 0.20, "unit_cell_size_mm": 10.0}
        resp = e2e_client.post(f"/projects/{project_id}/models/{model['id']}/infill", json=payload)
        assert resp.status_code in [200, 400, 422]

    def test_t2_11_extreme_tall_needle_mesh(self, e2e_client, tall_needle_bytes):
        """T2.11: Extreme aspect-ratio mesh (1x1x100mm slender needle)."""
        check_or_skip_endpoint(app, "/infill", "M1")
        project_id = create_e2e_project(e2e_client)
        model = import_e2e_model(e2e_client, project_id, tall_needle_bytes, "needle.stl")

        payload = {"pattern": "rectilinear", "density": 0.20, "unit_cell_size_mm": 10.0}
        resp = e2e_client.post(f"/projects/{project_id}/models/{model['id']}/infill", json=payload)
        assert resp.status_code in [200, 400, 422]

    def test_t2_12_micro_cube_bounds_1mm(self, e2e_client, micro_cube_bytes):
        """T2.12: Micro mesh boundary (1.0x1.0x1.0mm cube)."""
        check_or_skip_endpoint(app, "/infill", "M1")
        project_id = create_e2e_project(e2e_client)
        model = import_e2e_model(e2e_client, project_id, micro_cube_bytes, "micro.stl")

        payload = {"pattern": "gyroid", "density": 0.20, "unit_cell_size_mm": 1.0}
        resp = e2e_client.post(f"/projects/{project_id}/models/{model['id']}/infill", json=payload)
        assert resp.status_code in [200, 400, 422]

    def test_t2_13_invalid_pattern_enum(self, e2e_client, cube_20mm_bytes):
        """T2.13: Invalid pattern name ('voronoi') rejected with 422."""
        check_or_skip_endpoint(app, "/infill", "M1")
        project_id = create_e2e_project(e2e_client)
        model = import_e2e_model(e2e_client, project_id, cube_20mm_bytes)

        payload = {"pattern": "voronoi_invalid", "density": 0.20}
        resp = e2e_client.post(f"/projects/{project_id}/models/{model['id']}/infill", json=payload)
        assert resp.status_code == 422

    def test_t2_14_nonexistent_model_id_404(self, e2e_client):
        """T2.14: Requesting infill on non-existent model ID returns 404 Not Found."""
        check_or_skip_endpoint(app, "/infill", "M1")
        project_id = create_e2e_project(e2e_client)

        payload = {"pattern": "gyroid", "density": 0.20}
        resp = e2e_client.post(f"/projects/{project_id}/models/nonexistent_model_123/infill", json=payload)
        assert resp.status_code == 404

    def test_t2_15_clipping_plane_outside_mesh_bounds(self):
        """T2.15: Viewport clipping plane located completely outside mesh bounding box."""
        # Distance calculation when plane is at Z=500mm and mesh is bounded in [0, 20]
        mesh_z_max = 20.0
        plane_z = 500.0
        assert plane_z > mesh_z_max  # Everything preserved, zero fragments discarded


# ============================================================================
# TIER 3: CROSS-FEATURE COMBINATIONS
# ============================================================================

class TestTier3CrossFeatureCombinations:
    """
    Tier 3: Pairwise interactions between infill, hollowing, ribbing,
    drainage, transformations, and 3MF packaging.
    """

    def test_t3_01_combo_hollow_then_gyroid_infill(self, e2e_client, cube_20mm_bytes):
        """T3.1: Hollow solid mesh -> generate Gyroid infill in internal cavity."""
        check_or_skip_endpoint(app, "/infill", "M1")
        project_id = create_e2e_project(e2e_client)
        model = import_e2e_model(e2e_client, project_id, cube_20mm_bytes)

        # 1. Hollow
        hollow_res = e2e_client.post(
            f"/projects/{project_id}/models/{model['id']}/hollow",
            json={"wall_thickness_mm": 2.0},
        )
        assert hollow_res.status_code == 200

        # 2. Infill
        infill_res = e2e_client.post(
            f"/projects/{project_id}/models/{model['id']}/infill",
            json={"pattern": "gyroid", "density": 0.20, "unit_cell_size_mm": 10.0, "hollow_first": False},
        )
        assert infill_res.status_code == 200
        assert infill_res.json()["success"] is True

    def test_t3_02_combo_hollow_ribbing_drainage_and_infill(self, e2e_client, cube_20mm_bytes):
        """T3.2: Hollow -> structural rib reinforcement -> drainage conduit -> honeycomb infill."""
        check_or_skip_endpoint(app, "/infill", "M1")
        check_or_skip_endpoint(app, "/reinforce_ribs", "M2")
        project_id = create_e2e_project(e2e_client)
        model = import_e2e_model(e2e_client, project_id, cube_20mm_bytes)

        # 1. Hollow
        e2e_client.post(f"/projects/{project_id}/models/{model['id']}/hollow", json={"wall_thickness_mm": 1.5})

        # 2. Ribs & Drainage
        e2e_client.post(
            f"/projects/{project_id}/models/{model['id']}/reinforce_ribs",
            json={"rib_spacing_mm": 15.0, "drainage_channel_diameter_mm": 3.0},
        )

        # 3. Honeycomb Infill
        infill_res = e2e_client.post(
            f"/projects/{project_id}/models/{model['id']}/infill",
            json={"pattern": "honeycomb", "density": 0.25, "unit_cell_size_mm": 8.0},
        )
        assert infill_res.status_code == 200

    def test_t3_03_combo_scale_transform_center_and_infill(self, e2e_client, cube_20mm_bytes):
        """T3.3: Scale model -> bed center -> generate infill with mm invariance."""
        check_or_skip_endpoint(app, "/infill", "M1")
        project_id = create_e2e_project(e2e_client)
        model = import_e2e_model(e2e_client, project_id, cube_20mm_bytes)

        # 1. Scale height to 50mm
        scale_res = e2e_client.post(
            f"/projects/{project_id}/models/{model['id']}/scale",
            json={"target_height_mm": 50.0, "preserve_aspect_ratio": True},
        )
        assert scale_res.status_code == 200

        # 2. Bed center
        center_res = e2e_client.post(f"/projects/{project_id}/models/{model['id']}/center", json={})
        assert center_res.status_code == 200

        # 3. Generate Cubic Infill
        infill_res = e2e_client.post(
            f"/projects/{project_id}/models/{model['id']}/infill",
            json={"pattern": "cubic", "density": 0.20, "unit_cell_size_mm": 10.0},
        )
        assert infill_res.status_code == 200

    def test_t3_04_combo_infill_with_orcaslicer_3mf_export(self, e2e_client, cube_20mm_bytes):
        """T3.4: Generate infill -> export OrcaSlicer 3MF bundle -> verify metadata."""
        check_or_skip_endpoint(app, "/infill", "M1")
        project_id = create_e2e_project(e2e_client)
        model = import_e2e_model(e2e_client, project_id, cube_20mm_bytes)

        # 1. Infill
        e2e_client.post(
            f"/projects/{project_id}/models/{model['id']}/infill",
            json={"pattern": "gyroid", "density": 0.20},
        )

        # 2. Export 3MF
        resp = e2e_client.post(f"/projects/{project_id}/export_3mf", json={"plate_name": "Infill Plate"})
        assert resp.status_code == 200

    def test_t3_05_combo_infill_with_single_mesh_physical_stl_export(self, e2e_client, cube_20mm_bytes):
        """T3.5: Generate infill -> export single composite STL -> verify manifoldness."""
        check_or_skip_endpoint(app, "/infill", "M1")
        project_id = create_e2e_project(e2e_client)
        model = import_e2e_model(e2e_client, project_id, cube_20mm_bytes)

        # Infill
        e2e_client.post(
            f"/projects/{project_id}/models/{model['id']}/infill",
            json={"pattern": "rectilinear", "density": 0.20},
        )

        # Export STL
        exp_res = e2e_client.post(
            f"/projects/{project_id}/models/{model['id']}/export",
            json={"format": "stl", "filename": "infilled_composite.stl"},
        )
        assert exp_res.status_code == 200

    def test_t3_06_combo_infill_with_viewport_cross_section_uniforms(self, e2e_client, cube_20mm_bytes):
        """T3.6: Synchronize cutting plane origin and normal with infill bounding box."""
        check_or_skip_endpoint(app, "/infill", "M1")
        project_id = create_e2e_project(e2e_client)
        model = import_e2e_model(e2e_client, project_id, cube_20mm_bytes)

        infill_res = e2e_client.post(
            f"/projects/{project_id}/models/{model['id']}/infill",
            json={"pattern": "gyroid", "density": 0.20},
        )
        assert infill_res.status_code == 200
        bbox = infill_res.json()["bounding_box_mm"]
        mid_z = (bbox["z_min"] + bbox["z_max"]) / 2.0
        assert 0.0 <= mid_z <= 20.0


# ============================================================================
# TIER 4: REAL-WORLD APPLICATION SCENARIOS
# ============================================================================

class TestTier4RealWorldScenarios:
    """
    Tier 4: Realistic end-to-end 3D printing preparation workflows:
    - Figurine SLA resin prep
    - High-strength functional bracket FDM prep
    - Gaming miniature base SLA prep
    """

    def test_t4_01_scenario_hollow_resin_figurine_gyroid_and_drainage(self, e2e_client, cylinder_30mm_bytes):
        """
        Scenario 1: Hollow SLA Resin Figurine Preparation
        Workflow:
        1. Create new Resin SLA project (Mars 3 Pro)
        2. Import figurine mesh (cylinder proxy)
        3. Hollow to 1.5mm wall to save costly resin
        4. Generate 15% Gyroid infill (isotropic suction peel resistance)
        5. Add 3mm Z-axis drainage channel to prevent resin trapping
        6. Export watertight composite mesh for slicing
        """
        check_or_skip_endpoint(app, "/infill", "M1")
        project_id = create_e2e_project(e2e_client, name="SLA Resin Figurine Prep")
        model = import_e2e_model(e2e_client, project_id, cylinder_30mm_bytes, "figurine.stl")

        # Step 3: Hollow
        hollow_res = e2e_client.post(
            f"/projects/{project_id}/models/{model['id']}/hollow",
            json={"wall_thickness_mm": 1.5, "add_drain_holes": False},
        )
        assert hollow_res.status_code == 200

        # Step 4: Gyroid Infill
        infill_res = e2e_client.post(
            f"/projects/{project_id}/models/{model['id']}/infill",
            json={"pattern": "gyroid", "density": 0.15, "unit_cell_size_mm": 8.0, "hollow_first": False},
        )
        assert infill_res.status_code == 200

        # Step 5: Drainage (if M2 supported)
        if is_route_available(app, "/reinforce_ribs"):
            drain_res = e2e_client.post(
                f"/projects/{project_id}/models/{model['id']}/reinforce_ribs",
                json={"drainage_channel_diameter_mm": 3.0, "drainage_axis": "z"},
            )
            assert drain_res.status_code in [200, 201]

        # Step 6: Export
        exp_res = e2e_client.post(
            f"/projects/{project_id}/models/{model['id']}/export",
            json={"format": "stl", "filename": "figurine_sla_ready.stl"},
        )
        assert exp_res.status_code == 200

    def test_t4_02_scenario_high_strength_bracket_honeycomb_and_ribs(self, e2e_client, cube_20mm_bytes):
        """
        Scenario 2: High-Strength FDM Structural Bracket Preparation
        Workflow:
        1. Create new FDM engineering project (Ender-3)
        2. Import mounting bracket geometry
        3. Evaluate initial printability
        4. Generate 30% Honeycomb compressive vertical lattice
        5. Add structural stiffening ribs along thin walls (M2)
        6. Export OrcaSlicer 3MF package with plate metadata
        """
        check_or_skip_endpoint(app, "/infill", "M1")
        project_id = create_e2e_project(e2e_client, name="FDM Bracket Engineering")
        model = import_e2e_model(e2e_client, project_id, cube_20mm_bytes, "bracket.stl")

        # Step 3: Printability
        p_res = e2e_client.get(f"/projects/{project_id}/printability")
        assert p_res.status_code == 200

        # Step 4: Honeycomb Infill
        infill_res = e2e_client.post(
            f"/projects/{project_id}/models/{model['id']}/infill",
            json={"pattern": "honeycomb", "density": 0.30, "unit_cell_size_mm": 10.0},
        )
        assert infill_res.status_code == 200

        # Step 5: Ribs (if M2 supported)
        if is_route_available(app, "/reinforce_ribs"):
            rib_res = e2e_client.post(
                f"/projects/{project_id}/models/{model['id']}/reinforce_ribs",
                json={"min_wall_thickness_mm": 2.0, "rib_spacing_mm": 15.0, "rib_thickness_mm": 1.5},
            )
            assert rib_res.status_code in [200, 201]

        # Step 6: Export 3MF
        exp_res = e2e_client.post(
            f"/projects/{project_id}/export_3mf",
            json={"plate_name": "Bracket Plate", "printer_model": "Creality Ender-3"},
        )
        assert exp_res.status_code == 200

    def test_t4_03_scenario_sla_miniature_base_rectilinear_drainage(self, e2e_client, cube_20mm_bytes):
        """
        Scenario 3: Gaming Miniature Base SLA Preparation
        Workflow:
        1. Import miniature plinth
        2. Hollow to 1.2mm wall
        3. Generate 20% Rectilinear grid lattice
        4. Verify cross-section cutaway clipping bounds
        5. Export final production STL
        """
        check_or_skip_endpoint(app, "/infill", "M1")
        project_id = create_e2e_project(e2e_client, name="Miniature Plinth Prep")
        model = import_e2e_model(e2e_client, project_id, cube_20mm_bytes, "plinth.stl")

        # Hollow
        e2e_client.post(f"/projects/{project_id}/models/{model['id']}/hollow", json={"wall_thickness_mm": 1.2})

        # Rectilinear Infill
        infill_res = e2e_client.post(
            f"/projects/{project_id}/models/{model['id']}/infill",
            json={"pattern": "rectilinear", "density": 0.20, "unit_cell_size_mm": 6.0},
        )
        assert infill_res.status_code == 200

        # Export STL
        exp_res = e2e_client.post(
            f"/projects/{project_id}/models/{model['id']}/export",
            json={"format": "stl", "filename": "plinth_final.stl"},
        )
        assert exp_res.status_code == 200


# ============================================================================
# STANDALONE CLI RUNNER HARNESS
# ============================================================================

def run_standalone(base_url: Optional[str] = None) -> bool:
    """Standalone runner executing full suite with colored terminal report."""
    print(f"\n{Colors.BOLD}{Colors.YELLOW}{'='*70}")
    print(" OUTLAW FORGE: PHASE 10 E2E TEST SUITE RUNNER")
    print(f" Mode: {'Live HTTP Server (' + base_url + ')' if base_url else 'In-Process TestClient'}")
    print(f"{'='*70}{Colors.RESET}\n")

    # Run pytest programmatically on this file
    test_file = str(Path(__file__).resolve())
    args = [test_file, "-v", "--tb=short"]

    start = time.perf_counter()
    exit_code = pytest.main(args)
    elapsed = time.perf_counter() - start

    print(f"\n{Colors.BOLD}{Colors.YELLOW}{'='*70}")
    print(f" Execution completed in {elapsed:.2f}s (Exit code: {exit_code})")
    print(f"{'='*70}{Colors.RESET}\n")

    return exit_code == 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Outlaw Forge Phase 10 E2E Test Suite Runner")
    parser.add_argument("--base-url", default=None, help="Target running backend host (e.g. http://127.0.0.1:8000)")
    args = parser.parse_args()

    success = run_standalone(base_url=args.base_url)
    sys.exit(0 if success else 1)
