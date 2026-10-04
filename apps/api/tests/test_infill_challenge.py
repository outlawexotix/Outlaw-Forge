"""
Empirical Challenge & Stress Test Suite for InfillService (Milestone 1).
Exhaustively tests:
1. Nominal Stress Matrix: All 4 patterns (Gyroid, Honeycomb, Rectilinear, Cubic)
   under supported densities and unit cell sizes.
2. Large Unit Cell Boundary Condition (Bug 1):
   Honeycomb and Rectilinear void hole larger than bounding box causing empty mesh.
3. Pre-Hollowed Geometry Volume Ballooning (Bug 2):
   Pre-hollowed mesh handling decomposing negative-volume cavity voids.
4. Multi-Body Part Dropping & Infill Asymmetry (Bug 3):
   Multi-component models where bodies are discarded or left solid.
"""

import numpy as np
import pytest
import trimesh
from manifold3d import Error, Manifold, Mesh

from app.models.mesh import InfillPattern
from app.services.infill_service import InfillService, infill_service, InfillServiceError


def verify_mesh_integrity(mesh: trimesh.Trimesh, label: str) -> dict:
    """Verifies that a mesh is non-empty, watertight, 2-manifold, and has positive volume."""
    assert mesh is not None, f"[{label}] Mesh is None"
    assert len(mesh.vertices) > 0, f"[{label}] Vertex count is 0"
    assert len(mesh.faces) > 0, f"[{label}] Face count is 0"
    assert mesh.is_watertight, f"[{label}] Mesh is NOT watertight (open boundary edges)"
    assert mesh.volume > 0, f"[{label}] Mesh volume is non-positive: {mesh.volume}"

    # Verify 2-manifold roundtrip via manifold3d
    m_recheck = InfillService.trimesh_to_manifold(mesh)
    assert not m_recheck.is_empty(), f"[{label}] Manifold3d roundtrip produced empty manifold"
    assert m_recheck.status() == Error.NoError, f"[{label}] Manifold3d status check failed: {m_recheck.status()}"

    return {
        "vertices": len(mesh.vertices),
        "faces": len(mesh.faces),
        "volume": float(mesh.volume),
        "watertight": mesh.is_watertight,
        "extents": [round(float(x), 3) for x in mesh.extents],
    }


# ============================================================================
# Section 1: Nominal Stress Tests (Verified Passing Geometries)
# ============================================================================

PATTERNS = [
    InfillPattern.GYROID,
    InfillPattern.HONEYCOMB,
    InfillPattern.RECTILINEAR,
    InfillPattern.CUBIC,
]


@pytest.mark.parametrize("pattern", PATTERNS)
@pytest.mark.parametrize("density", [0.05, 0.50, 1.0])
@pytest.mark.parametrize("unit_cell_size_mm", [3.0, 10.0])
@pytest.mark.parametrize("hollow_first", [True, False])
def test_nominal_parameter_matrix(pattern, density, unit_cell_size_mm, hollow_first):
    """Verify nominal parameter space (cell sizes 3mm & 10mm) generates valid 2-manifold meshes."""
    cube = trimesh.creation.box(extents=(20.0, 20.0, 20.0))
    label = f"{pattern.value}_d{density}_s{unit_cell_size_mm}_h{hollow_first}"

    res_mesh, vol_reduction = infill_service.generate_infill(
        mesh=cube,
        pattern=pattern,
        density=density,
        unit_cell_size_mm=unit_cell_size_mm,
        wall_thickness_mm=2.0,
        hollow_first=hollow_first,
    )

    verify_mesh_integrity(res_mesh, label)
    if density >= 0.999:
        assert vol_reduction == 0.0
    else:
        assert vol_reduction >= 0.0


@pytest.mark.parametrize("pattern", PATTERNS)
def test_large_cube_50mm_with_30mm_cells(pattern):
    """Verify 30mm unit cell generates valid meshes when geometry (50mm cube) exceeds cell size."""
    cube_50 = trimesh.creation.box(extents=(50.0, 50.0, 50.0))
    res_mesh, vol_reduction = infill_service.generate_infill(
        mesh=cube_50,
        pattern=pattern,
        density=0.20,
        unit_cell_size_mm=30.0,
        wall_thickness_mm=2.0,
        hollow_first=True,
    )
    verify_mesh_integrity(res_mesh, f"50mm_{pattern.value}_30mm")


@pytest.mark.parametrize("pattern", PATTERNS)
def test_curved_geometry_icosphere(pattern):
    """Verify non-planar curved geometry generates valid watertight meshes."""
    sphere = trimesh.creation.icosphere(subdivisions=2, radius=15.0)
    res_mesh, vol_reduction = infill_service.generate_infill(
        mesh=sphere,
        pattern=pattern,
        density=0.20,
        unit_cell_size_mm=8.0,
        wall_thickness_mm=2.0,
        hollow_first=True,
    )
    verify_mesh_integrity(res_mesh, f"sphere_{pattern.value}")


# ============================================================================
# Section 2: Empirical Bug Repruducers (Targeted for Fix in Worker M1)
# ============================================================================


def test_bug1_large_cell_spacing_empty_mesh_honeycomb():
    """
    Bug 1 Reproducer:
    When unit_cell_size_mm (30mm) >= model extent (20mm) on Honeycomb with low density,
    the subtracted void hole is larger than the 2D cross section, leaving an empty
    CrossSection. Extruding empty CrossSection causes Error.InvalidConstruction, which
    poisons boolean operations and raises InfillServiceError.
    """
    cube = trimesh.creation.box(extents=(20.0, 20.0, 20.0))
    # This should generate a valid fallback or bounded lattice, but currently raises InfillServiceError
    with pytest.raises(InfillServiceError, match="Boolean operation yielded empty infill mesh"):
        infill_service.generate_infill(
            mesh=cube,
            pattern=InfillPattern.HONEYCOMB,
            density=0.05,
            unit_cell_size_mm=30.0,
            wall_thickness_mm=2.0,
            hollow_first=True,
        )


def test_bug1_large_cell_spacing_empty_mesh_rectilinear():
    """
    Bug 1 Reproducer:
    When unit_cell_size_mm (30mm) >= model extent (20mm) on Rectilinear,
    the square void hole covers the entire cross section, crashing with InfillServiceError.
    """
    cube = trimesh.creation.box(extents=(20.0, 20.0, 20.0))
    with pytest.raises(InfillServiceError, match="Boolean operation yielded empty infill mesh"):
        infill_service.generate_infill(
            mesh=cube,
            pattern=InfillPattern.RECTILINEAR,
            density=0.20,
            unit_cell_size_mm=30.0,
            wall_thickness_mm=2.0,
            hollow_first=True,
        )


def test_bug2_pre_hollowed_mesh_volume_inflation():
    """
    Bug 2 Reproducer:
    When input mesh is already hollowed, InfillService sorts decomposed components
    and executes: wall_shell = outer_shell - cavity_void.
    In Manifold3d, cavity_void has negative volume (inverted normals).
    Subtracting negative volume unions the cavity void, inflating rather than
    infilling the part.
    """
    outer_box = trimesh.creation.box(extents=(30.0, 30.0, 30.0))
    inner_box = trimesh.creation.box(extents=(20.0, 20.0, 20.0))
    m_outer = InfillService.trimesh_to_manifold(outer_box)
    m_inner = InfillService.trimesh_to_manifold(inner_box)
    m_hollow = m_outer - m_inner
    raw_mesh = m_hollow.to_mesh()
    hollow_mesh = trimesh.Trimesh(
        vertices=np.array(raw_mesh.vert_properties, dtype=np.float64),
        faces=np.array(raw_mesh.tri_verts, dtype=np.int64),
        process=False,
    )

    orig_volume = hollow_mesh.volume  # 30^3 - 20^3 = 27000 - 8000 = 19000 mm^3
    assert np.isclose(orig_volume, 19000.0, atol=10.0)

    res_mesh, vol_reduction = infill_service.generate_infill(
        mesh=hollow_mesh,
        pattern=InfillPattern.CUBIC,
        density=0.20,
        unit_cell_size_mm=10.0,
    )

    # BUG: Volume actually inflates to > 30000 mm^3 instead of reducing or staying <= 19000!
    assert res_mesh.volume > orig_volume, (
        f"Demonstrates Bug 2: Volume inflated from {orig_volume} to {res_mesh.volume}"
    )


def test_bug3_multi_body_part_loss():
    """
    Bug 3 Reproducer:
    When a model contains multiple separate solid bodies (e.g., 3 separate parts on build plate),
    InfillService incorrectly treats len(decomposed) >= 2 as a hollowed mesh,
    keeps only component 0 & 1, discards component 2+, leaves component 0 solid,
    and strips the shell of component 1.
    """
    c1 = trimesh.creation.box(extents=(20.0, 20.0, 20.0))
    c2 = trimesh.creation.box(extents=(20.0, 20.0, 20.0)).apply_translation([30.0, 0.0, 0.0])
    c3 = trimesh.creation.box(extents=(20.0, 20.0, 20.0)).apply_translation([60.0, 0.0, 0.0])
    multi_mesh = trimesh.util.concatenate([c1, c2, c3])

    orig_volume = multi_mesh.volume  # 3 * 8000 = 24000 mm^3
    orig_extents = multi_mesh.extents  # [80, 20, 20]

    res_mesh, vol_reduction = infill_service.generate_infill(
        mesh=multi_mesh,
        pattern=InfillPattern.CUBIC,
        density=0.20,
        unit_cell_size_mm=10.0,
    )

    # BUG: Component 3 is discarded! Bounding extent x drops from 80mm to 50mm.
    assert res_mesh.extents[0] < orig_extents[0] - 10.0, (
        f"Demonstrates Bug 3: Multi-body model lost third component! Extent: {res_mesh.extents}"
    )
