import io
import os
import tempfile
from pathlib import Path
import numpy as np
import pytest
import trimesh

from app.models.mesh import (
    ExportModelPayload,
    MeshRepairReport,
    OverhangAnalysisResult,
    RepairModelPayload,
    RepairModelResult,
    RotateModelPayload,
    ScaleModelPayload,
    SliceModelPayload,
    SliceModelResult,
)
from app.services.mesh_service import (
    ALLOWED_EXTENSIONS,
    MAX_FILE_SIZE_BYTES,
    MeshProcessingError,
    MeshValidationError,
    analyze_mesh,
    analyze_overhangs,
    center_mesh_on_bed,
    export_mesh,
    lay_flat_mesh,
    load_mesh,
    repair_mesh,
    rotate_mesh,
    sanitize_and_validate_filename,
    scale_mesh,
    slice_mesh,
)


class TestMeshSecurityAndValidation:
    """Security and input validation test suite for mesh handling."""

    @pytest.mark.parametrize(
        "malicious_filename",
        [
            "../../etc/passwd",
            "../../../evil.stl",
            "..\\..\\system32\\calc.exe",
            "/absolute/path/file.stl",
            "C:\\Windows\\win.stl",
            "mesh..stl",
            "mesh/nested/file.stl",
            "mesh\\nested\\file.stl",
            "file\x00name.stl",
            "",
            None,
        ],
    )
    def test_reject_path_traversal_and_invalid_filenames(self, malicious_filename):
        """Must reject directory traversal attempts and illegal filename formats."""
        with pytest.raises(MeshValidationError):
            sanitize_and_validate_filename(malicious_filename)

    @pytest.mark.parametrize(
        "invalid_ext_filename",
        [
            "payload.exe",
            "script.sh",
            "run.bat",
            "exploit.py",
            "picture.png",
            "document.pdf",
            "archive.zip",
            "no_extension",
        ],
    )
    def test_reject_disallowed_extensions(self, invalid_ext_filename):
        """Must reject executable or non-3D file extensions."""
        with pytest.raises(MeshValidationError):
            sanitize_and_validate_filename(invalid_ext_filename)

    @pytest.mark.parametrize(
        "valid_filename",
        [
            "calibration_cube.stl",
            "figure_model.OBJ",
            "scene.glb",
            "part-1_v2.gltf",
            "custom mesh 10.3mf",
        ],
    )
    def test_accept_valid_filenames(self, valid_filename):
        """Accepts clean, valid 3D mesh filenames."""
        sanitized = sanitize_and_validate_filename(valid_filename)
        assert sanitized == valid_filename

    def test_reject_empty_file_or_stream(self, tmp_path):
        """Must reject 0-byte empty files or streams."""
        empty_file = tmp_path / "empty.stl"
        empty_file.write_bytes(b"")

        with pytest.raises(MeshValidationError, match="empty"):
            load_mesh(empty_file)

        with pytest.raises(MeshValidationError, match="empty"):
            load_mesh(b"")

        with pytest.raises(MeshValidationError, match="empty"):
            load_mesh(io.BytesIO(b""))

    def test_reject_malformed_garbage_bytes(self):
        """Must reject corrupted or random binary content that cannot be parsed as a 3D mesh."""
        garbage_bytes = b"CORRUPTED_NOT_A_VALID_3D_MESH_HEADER_DATA_1234567890"
        with pytest.raises((MeshProcessingError, MeshValidationError)):
            load_mesh(garbage_bytes, filename="bad.stl")


class TestMeshAnalysis:
    """Test suite for mesh geometry analysis, precision dimensions, and volume calculations."""

    def test_calibration_cube_dimensions_and_bounding_box(self, cube_20mm_mesh):
        """
        Verify precision 20x20x20 mm calibration cube:
        - Extents: exactly 20.0 x 20.0 x 20.0 mm
        - Surface area: 6 * (20 * 20) mm2 = 2400 mm2 = 24.0 cm2
        - Watertight: True
        - Volume: 20 * 20 * 20 mm3 = 8000 mm3 = 8.0 cm3
        """
        analysis = analyze_mesh(cube_20mm_mesh)

        # Dimension checks
        assert pytest.approx(analysis.bounds.dimensions_mm[0], rel=1e-3) == 20.0
        assert pytest.approx(analysis.bounds.dimensions_mm[1], rel=1e-3) == 20.0
        assert pytest.approx(analysis.bounds.dimensions_mm[2], rel=1e-3) == 20.0

        # Surface Area: 24.0 cm2
        assert pytest.approx(analysis.surface_area_cm2, rel=1e-3) == 24.0

        # Watertight & Volume: 8.0 cm3
        assert analysis.is_watertight is True
        assert analysis.volume_cm3 is not None
        assert pytest.approx(analysis.volume_cm3, rel=1e-3) == 8.0

        # Face/Vertex count validity
        assert analysis.triangle_count >= 12
        assert analysis.vertex_count >= 8

    def test_oversized_mesh_analysis(self, cube_300mm_mesh):
        """
        Verify oversized 300x300x300 mm mesh:
        - Dimensions: 300 x 300 x 300 mm
        - Surface area: 6 * (300^2) = 540,000 mm2 = 5400.0 cm2
        - Volume: 300^3 = 27,000,000 mm3 = 27,000.0 cm3
        """
        analysis = analyze_mesh(cube_300mm_mesh)
        assert pytest.approx(analysis.bounds.dimensions_mm[0], rel=1e-3) == 300.0
        assert pytest.approx(analysis.bounds.dimensions_mm[1], rel=1e-3) == 300.0
        assert pytest.approx(analysis.bounds.dimensions_mm[2], rel=1e-3) == 300.0
        assert pytest.approx(analysis.surface_area_cm2, rel=1e-3) == 5400.0
        assert analysis.volume_cm3 is not None
        assert pytest.approx(analysis.volume_cm3, rel=1e-3) == 27000.0

    def test_load_mesh_from_filepath_and_bytes(self, cube_20mm_path):
        """Verify loading mesh from file path, bytes, and BytesIO stream."""
        # Load from Path
        mesh_from_path = load_mesh(cube_20mm_path)
        assert len(mesh_from_path.faces) > 0

        # Load from bytes
        raw_bytes = cube_20mm_path.read_bytes()
        mesh_from_bytes = load_mesh(raw_bytes, filename="cube.stl")
        assert len(mesh_from_bytes.faces) == len(mesh_from_path.faces)

        # Load from BytesIO
        stream = io.BytesIO(raw_bytes)
        mesh_from_stream = load_mesh(stream, filename="cube.stl")
        assert len(mesh_from_stream.faces) == len(mesh_from_path.faces)


class TestMeshScaling:
    """Test suite for deterministic uniform and target dimension scaling."""

    def test_uniform_scaling_200_percent(self, cube_20mm_mesh):
        """
        Scaling 20x20x20mm cube uniformly by 200%:
        - Dimensions: 40.0 x 40.0 x 40.0 mm
        - Volume: 40^3 = 64,000 mm3 = 64.0 cm3
        """
        payload = ScaleModelPayload(uniform_scale_percent=200.0)
        scaled = scale_mesh(cube_20mm_mesh, payload)
        analysis = analyze_mesh(scaled)

        assert pytest.approx(analysis.bounds.dimensions_mm[0], rel=1e-3) == 40.0
        assert pytest.approx(analysis.bounds.dimensions_mm[1], rel=1e-3) == 40.0
        assert pytest.approx(analysis.bounds.dimensions_mm[2], rel=1e-3) == 40.0
        assert analysis.volume_cm3 is not None
        assert pytest.approx(analysis.volume_cm3, rel=1e-3) == 64.0

    def test_uniform_scaling_50_percent(self, cube_20mm_mesh):
        """
        Scaling 20x20x20mm cube uniformly by 50%:
        - Dimensions: 10.0 x 10.0 x 10.0 mm
        - Volume: 10^3 = 1000 mm3 = 1.0 cm3
        """
        payload = ScaleModelPayload(uniform_scale_percent=50.0)
        scaled = scale_mesh(cube_20mm_mesh, payload)
        analysis = analyze_mesh(scaled)

        assert pytest.approx(analysis.bounds.dimensions_mm[0], rel=1e-3) == 10.0
        assert pytest.approx(analysis.bounds.dimensions_mm[1], rel=1e-3) == 10.0
        assert pytest.approx(analysis.bounds.dimensions_mm[2], rel=1e-3) == 10.0
        assert analysis.volume_cm3 is not None
        assert pytest.approx(analysis.volume_cm3, rel=1e-3) == 1.0

    def test_target_height_scaling_with_aspect_lock(self, cube_20mm_mesh):
        """
        Target height (Z) = 50.0 mm with preserve_aspect_ratio=True:
        - Scale factor = 50 / 20 = 2.5
        - Resulting dimensions: 50.0 x 50.0 x 50.0 mm
        - Volume: 50^3 = 125,000 mm3 = 125.0 cm3
        """
        payload = ScaleModelPayload(target_height_mm=50.0, preserve_aspect_ratio=True)
        scaled = scale_mesh(cube_20mm_mesh, payload)
        analysis = analyze_mesh(scaled)

        assert pytest.approx(analysis.bounds.dimensions_mm[0], rel=1e-3) == 50.0
        assert pytest.approx(analysis.bounds.dimensions_mm[1], rel=1e-3) == 50.0
        assert pytest.approx(analysis.bounds.dimensions_mm[2], rel=1e-3) == 50.0
        assert analysis.volume_cm3 is not None
        assert pytest.approx(analysis.volume_cm3, rel=1e-3) == 125.0

    def test_target_height_scaling_without_aspect_lock(self, cube_20mm_mesh):
        """
        Target height (Z) = 50.0 mm with preserve_aspect_ratio=False:
        - Resulting dimensions: 20.0 x 20.0 x 50.0 mm
        - Volume: 20 * 20 * 50 = 20,000 mm3 = 20.0 cm3
        """
        payload = ScaleModelPayload(target_height_mm=50.0, preserve_aspect_ratio=False)
        scaled = scale_mesh(cube_20mm_mesh, payload)
        analysis = analyze_mesh(scaled)

        assert pytest.approx(analysis.bounds.dimensions_mm[0], rel=1e-3) == 20.0
        assert pytest.approx(analysis.bounds.dimensions_mm[1], rel=1e-3) == 20.0
        assert pytest.approx(analysis.bounds.dimensions_mm[2], rel=1e-3) == 50.0
        assert analysis.volume_cm3 is not None
        assert pytest.approx(analysis.volume_cm3, rel=1e-3) == 20.0

    def test_target_width_and_depth_scaling_without_aspect_lock(self, cube_20mm_mesh):
        """
        Non-uniform target width and depth scaling.
        """
        # Target width = 60mm
        scaled_w = scale_mesh(cube_20mm_mesh, ScaleModelPayload(target_width_mm=60.0, preserve_aspect_ratio=False))
        analysis_w = analyze_mesh(scaled_w)
        assert pytest.approx(analysis_w.bounds.dimensions_mm[0], rel=1e-3) == 60.0
        assert pytest.approx(analysis_w.bounds.dimensions_mm[1], rel=1e-3) == 20.0
        assert pytest.approx(analysis_w.bounds.dimensions_mm[2], rel=1e-3) == 20.0

        # Target depth = 45mm
        scaled_d = scale_mesh(cube_20mm_mesh, ScaleModelPayload(target_depth_mm=45.0, preserve_aspect_ratio=False))
        analysis_d = analyze_mesh(scaled_d)
        assert pytest.approx(analysis_d.bounds.dimensions_mm[0], rel=1e-3) == 20.0
        assert pytest.approx(analysis_d.bounds.dimensions_mm[1], rel=1e-3) == 45.0
        assert pytest.approx(analysis_d.bounds.dimensions_mm[2], rel=1e-3) == 20.0

    def test_invalid_scale_parameters_raise_error(self, cube_20mm_mesh):
        """Must reject negative or zero scaling factors."""
        with pytest.raises(MeshValidationError):
            scale_mesh(cube_20mm_mesh, ScaleModelPayload(uniform_scale_percent=0.0))

        with pytest.raises(MeshValidationError):
            scale_mesh(cube_20mm_mesh, ScaleModelPayload(uniform_scale_percent=-50.0))

        with pytest.raises(MeshValidationError):
            scale_mesh(cube_20mm_mesh, ScaleModelPayload(target_height_mm=-10.0))


class TestMeshExport:
    """Test suite for mesh export generation (STL, OBJ, GLB)."""

    def test_export_to_stl(self, cube_20mm_mesh, tmp_path):
        """Export mesh to STL and verify re-import integrity."""
        payload = ExportModelPayload(format="stl", filename="exported_cube.stl")
        result = export_mesh(cube_20mm_mesh, tmp_path, payload)

        assert os.path.exists(result.export_path)
        assert result.filename == "exported_cube.stl"
        assert result.format == "stl"
        assert result.file_size_bytes > 0

        # Reload exported mesh and verify dimensions
        reloaded = trimesh.load(result.export_path)
        assert pytest.approx(reloaded.extents[0], rel=1e-3) == 20.0
        assert pytest.approx(reloaded.extents[1], rel=1e-3) == 20.0
        assert pytest.approx(reloaded.extents[2], rel=1e-3) == 20.0

    def test_export_to_obj(self, cube_20mm_mesh, tmp_path):
        """Export mesh to OBJ and verify re-import integrity."""
        payload = ExportModelPayload(format="obj", filename="exported_cube.obj")
        result = export_mesh(cube_20mm_mesh, tmp_path, payload)

        assert os.path.exists(result.export_path)
        assert result.filename == "exported_cube.obj"
        assert result.format == "obj"
        assert result.file_size_bytes > 0

        reloaded = trimesh.load(result.export_path)
        assert pytest.approx(reloaded.extents[0], rel=1e-3) == 20.0
        assert pytest.approx(reloaded.extents[1], rel=1e-3) == 20.0
        assert pytest.approx(reloaded.extents[2], rel=1e-3) == 20.0

    def test_export_to_glb(self, cube_20mm_mesh, tmp_path):
        """Export mesh to GLB format."""
        payload = ExportModelPayload(format="glb", filename="exported_cube.glb")
        result = export_mesh(cube_20mm_mesh, tmp_path, payload)

        assert os.path.exists(result.export_path)
        assert result.filename == "exported_cube.glb"
        assert result.format == "glb"
        assert result.file_size_bytes > 0

    def test_export_rejects_path_traversal_in_filename(self, cube_20mm_mesh, tmp_path):
        """Export must reject malicious traversal in requested export filename."""
        payload = ExportModelPayload(format="stl", filename="../../outside.stl")
        with pytest.raises(MeshValidationError):
            export_mesh(cube_20mm_mesh, tmp_path, payload)


class TestMeshRotation:
    """Test suite for deterministic mesh rotation around Euler axes (X, Y, Z) and bounds recalculation."""

    @pytest.fixture
    def asymmetric_box(self):
        """Create an asymmetric 10 x 20 x 30 mm test box mesh."""
        return trimesh.creation.box(extents=[10.0, 20.0, 30.0])

    def test_rotation_90_deg_around_x_axis(self, asymmetric_box):
        """
        Rotating 10x20x30mm box 90 degrees around X-axis:
        - X extent remains 10.0 mm
        - Y extent becomes 30.0 mm (previous Z)
        - Z extent becomes 20.0 mm (previous Y)
        """
        rotated = rotate_mesh(asymmetric_box, rx_deg=90.0, ry_deg=0.0, rz_deg=0.0)
        analysis = analyze_mesh(rotated)

        assert pytest.approx(analysis.bounds.dimensions_mm[0], rel=1e-3) == 10.0
        assert pytest.approx(analysis.bounds.dimensions_mm[1], rel=1e-3) == 30.0
        assert pytest.approx(analysis.bounds.dimensions_mm[2], rel=1e-3) == 20.0
        assert analysis.is_watertight is True
        assert analysis.volume_cm3 is not None
        assert pytest.approx(analysis.volume_cm3, rel=1e-3) == 6.0  # 10*20*30 / 1000 = 6.0 cm3

    def test_rotation_90_deg_around_y_axis(self, asymmetric_box):
        """
        Rotating 10x20x30mm box 90 degrees around Y-axis:
        - X extent becomes 30.0 mm (previous Z)
        - Y extent remains 20.0 mm
        - Z extent becomes 10.0 mm (previous X)
        """
        rotated = rotate_mesh(asymmetric_box, rx_deg=0.0, ry_deg=90.0, rz_deg=0.0)
        analysis = analyze_mesh(rotated)

        assert pytest.approx(analysis.bounds.dimensions_mm[0], rel=1e-3) == 30.0
        assert pytest.approx(analysis.bounds.dimensions_mm[1], rel=1e-3) == 20.0
        assert pytest.approx(analysis.bounds.dimensions_mm[2], rel=1e-3) == 10.0
        assert pytest.approx(analysis.volume_cm3, rel=1e-3) == 6.0

    def test_rotation_90_deg_around_z_axis(self, asymmetric_box):
        """
        Rotating 10x20x30mm box 90 degrees around Z-axis:
        - X extent becomes 20.0 mm (previous Y)
        - Y extent becomes 10.0 mm (previous X)
        - Z extent remains 30.0 mm
        """
        rotated = rotate_mesh(asymmetric_box, rx_deg=0.0, ry_deg=0.0, rz_deg=90.0)
        analysis = analyze_mesh(rotated)

        assert pytest.approx(analysis.bounds.dimensions_mm[0], rel=1e-3) == 20.0
        assert pytest.approx(analysis.bounds.dimensions_mm[1], rel=1e-3) == 10.0
        assert pytest.approx(analysis.bounds.dimensions_mm[2], rel=1e-3) == 30.0
        assert pytest.approx(analysis.volume_cm3, rel=1e-3) == 6.0

    def test_rotation_360_deg_identity(self, asymmetric_box):
        """Full 360 degree rotation returns identical extents."""
        rotated = rotate_mesh(asymmetric_box, rx_deg=360.0, ry_deg=360.0, rz_deg=360.0)
        analysis = analyze_mesh(rotated)

        assert pytest.approx(analysis.bounds.dimensions_mm[0], rel=1e-3) == 10.0
        assert pytest.approx(analysis.bounds.dimensions_mm[1], rel=1e-3) == 20.0
        assert pytest.approx(analysis.bounds.dimensions_mm[2], rel=1e-3) == 30.0

    def test_rotation_preserves_area_and_volume(self, cube_20mm_mesh):
        """Rigid rotation must strictly preserve surface area and signed volume."""
        orig_analysis = analyze_mesh(cube_20mm_mesh)
        rotated = rotate_mesh(cube_20mm_mesh, rx_deg=45.0, ry_deg=45.0, rz_deg=45.0)
        rot_analysis = analyze_mesh(rotated)

        assert pytest.approx(rot_analysis.surface_area_cm2, rel=1e-3) == orig_analysis.surface_area_cm2
        assert pytest.approx(rot_analysis.volume_cm3, rel=1e-3) == orig_analysis.volume_cm3
        assert rot_analysis.triangle_count == orig_analysis.triangle_count
        assert rot_analysis.vertex_count == orig_analysis.vertex_count


class TestMeshCenteringOnBed:
    """Test suite for centering meshes on the build bed (Z_min = 0, Center X, Y = 0, 0)."""

    def test_centering_off_center_mesh(self):
        """
        Create a 20x30x40mm box translated far off-center:
        min = [100, 200, 50], max = [120, 230, 90].
        After centering on bed:
        - Z_min must be 0.0
        - Center X must be 0.0 (min X = -10.0, max X = 10.0)
        - Center Y must be 0.0 (min Y = -15.0, max Y = 15.0)
        """
        box = trimesh.creation.box(extents=[20.0, 30.0, 40.0])
        box.apply_translation([110.0, 215.0, 70.0])

        centered = center_mesh_on_bed(box)
        analysis = analyze_mesh(centered)

        assert pytest.approx(analysis.bounds.min[2], abs=1e-4) == 0.0
        assert pytest.approx(analysis.bounds.max[2], abs=1e-4) == 40.0

        # Center in X and Y must be 0.0
        center_x = (analysis.bounds.min[0] + analysis.bounds.max[0]) / 2.0
        center_y = (analysis.bounds.min[1] + analysis.bounds.max[1]) / 2.0
        assert pytest.approx(center_x, abs=1e-4) == 0.0
        assert pytest.approx(center_y, abs=1e-4) == 0.0

        assert pytest.approx(analysis.bounds.min[0], abs=1e-4) == -10.0
        assert pytest.approx(analysis.bounds.max[0], abs=1e-4) == 10.0
        assert pytest.approx(analysis.bounds.min[1], abs=1e-4) == -15.0
        assert pytest.approx(analysis.bounds.max[1], abs=1e-4) == 15.0

        # Extents preserved
        assert pytest.approx(analysis.bounds.dimensions_mm[0], rel=1e-3) == 20.0
        assert pytest.approx(analysis.bounds.dimensions_mm[1], rel=1e-3) == 30.0
        assert pytest.approx(analysis.bounds.dimensions_mm[2], rel=1e-3) == 40.0

    def test_centering_idempotent(self, cube_20mm_mesh):
        """Centering an already centered mesh does not shift its coordinates."""
        centered_once = center_mesh_on_bed(cube_20mm_mesh)
        centered_twice = center_mesh_on_bed(centered_once)

        assert pytest.approx(centered_once.bounds[0], abs=1e-4) == centered_twice.bounds[0]
        assert pytest.approx(centered_once.bounds[1], abs=1e-4) == centered_twice.bounds[1]


class TestMeshLayFlat:
    """Test suite for lay flat orientation (aligning largest planar face to Z=0 plane)."""

    def test_lay_flat_tilted_rectangular_box(self):
        """
        Create a 10x20x40mm box (largest faces are 20x40mm with area 800mm2).
        Tilt by 45 deg around X and 30 deg around Y.
        Lay flat should orient the 20x40 face parallel to the bed,
        resulting in height Z = 10.0 mm and Z_min = 0.0.
        """
        box = trimesh.creation.box(extents=[10.0, 20.0, 40.0])
        tilted = rotate_mesh(box, rx_deg=45.0, ry_deg=30.0, rz_deg=15.0)

        flat = lay_flat_mesh(tilted)
        analysis = analyze_mesh(flat)

        # Z_min must be 0.0
        assert pytest.approx(analysis.bounds.min[2], abs=1e-2) == 0.0

        # Smallest dimension (10mm) should be the vertical height Z
        assert pytest.approx(analysis.bounds.dimensions_mm[2], abs=0.5) == 10.0

        # Volume and watertightness preserved
        assert analysis.is_watertight is True
        assert analysis.volume_cm3 is not None
        assert pytest.approx(analysis.volume_cm3, rel=1e-2) == 8.0  # 10*20*40 = 8000 mm3 = 8.0 cm3

    def test_lay_flat_preserves_topology(self, cube_20mm_mesh):
        """Lay flat operation preserves vertex count, face count, and volume."""
        flat = lay_flat_mesh(cube_20mm_mesh)
        analysis = analyze_mesh(flat)

        assert analysis.is_watertight is True
        assert pytest.approx(analysis.volume_cm3, rel=1e-3) == 8.0
        assert pytest.approx(analysis.bounds.min[2], abs=1e-4) == 0.0


class TestMeshOverhangAnalysis:
    """Test suite for overhang analysis on meshes and support requirement diagnostics."""

    def test_overhang_analysis_calibration_cube(self, cube_20mm_mesh):
        """
        Upright 20mm cube with default critical angle 45 deg:
        - 6 faces of 400 mm2 = 2400 mm2 total area = 24.0 cm2
        - Bottom face normal is [0, 0, -1] -> downward normal nz = -1.0 <= -sin(45 deg) = -0.7071
        - Bottom face area = 400 mm2 = 4.0 cm2 (2 triangles)
        - Overhang percentage = 4.0 / 24.0 * 100 = 16.67%
        """
        result = analyze_overhangs(cube_20mm_mesh, critical_angle_deg=45.0)

        assert isinstance(result, OverhangAnalysisResult)
        assert result.critical_angle_deg == 45.0
        assert pytest.approx(result.total_area_cm2, rel=1e-3) == 24.0
        assert pytest.approx(result.overhang_area_cm2, rel=1e-3) == 4.0
        assert pytest.approx(result.overhang_percentage, rel=1e-2) == 16.67
        assert result.overhang_face_count == 2
        assert result.total_face_count == 12
        assert result.requires_support is True

    def test_overhang_analysis_varying_critical_angles(self, cube_20mm_mesh):
        """
        Test overhang diagnostics across different critical angles:
        - At 30 deg: threshold nz = -sin(30 deg) = -0.5 -> bottom face nz = -1.0 < -0.5 (detected)
        - At 90 deg: threshold nz = -sin(90 deg) = -1.0 -> bottom face nz = -1.0 is not strictly < -1.0 -> 0% overhang
        """
        res_30 = analyze_overhangs(cube_20mm_mesh, critical_angle_deg=30.0)
        assert res_30.requires_support is True
        assert pytest.approx(res_30.overhang_area_cm2, rel=1e-3) == 4.0

        res_90 = analyze_overhangs(cube_20mm_mesh, critical_angle_deg=90.0)
        assert res_90.overhang_face_count == 0
        assert res_90.overhang_percentage == 0.0
        assert res_90.requires_support is False

    def test_overhang_analysis_cantilever_t_shape(self):
        """
        Create a T-shaped overhang mesh:
        Base column (10x10x20mm) + Top bar (30x10x10mm) atop column.
        Under the overhang wings, there are downward-facing surfaces requiring support.
        """
        column = trimesh.creation.box(extents=[10.0, 10.0, 20.0])
        column.apply_translation([0.0, 0.0, 10.0])

        top_bar = trimesh.creation.box(extents=[30.0, 10.0, 10.0])
        top_bar.apply_translation([0.0, 0.0, 25.0])

        t_mesh = trimesh.util.concatenate([column, top_bar])
        result = analyze_overhangs(t_mesh, critical_angle_deg=45.0)

        assert result.requires_support is True
        assert result.overhang_face_count > 0
        assert result.overhang_area_cm2 > 0.0
        assert result.total_area_cm2 > result.overhang_area_cm2

    def test_overhang_analysis_empty_mesh(self):
        """Empty mesh gracefully returns 0 overhang metrics."""
        empty_mesh = trimesh.Trimesh()
        result = analyze_overhangs(empty_mesh)

        assert result.overhang_percentage == 0.0
        assert result.total_area_cm2 == 0.0
        assert result.overhang_area_cm2 == 0.0
        assert result.requires_support is False


class TestPlanarSlicing:
    """Test suite for planar slicing, mesh splitting, face capping, and alignment pegs."""

    def test_horizontal_slice_calibration_cube(self, cube_20mm_mesh):
        """
        Slice grounded 20x20x20mm cube (Z in [0, 20]) at Z=10mm (mid-height) with normal [0, 0, 1].
        - Top half: 20x20x10mm (Volume: 4.0 cm3, watertight)
        - Bottom half: 20x20x10mm (Volume: 4.0 cm3, watertight)
        - Total volume: 8.0 cm3 preserved
        - Cut area: 4.0 cm2 (20x20mm = 400 mm2)
        """
        grounded = center_mesh_on_bed(cube_20mm_mesh)
        top_slice, bottom_slice, cut_area = slice_mesh(
            mesh=grounded,
            plane_origin=[0.0, 0.0, 10.0],
            plane_normal=[0.0, 0.0, 1.0],
            cap_faces=True,
        )

        top_analysis = analyze_mesh(top_slice)
        bottom_analysis = analyze_mesh(bottom_slice)

        assert top_analysis.is_watertight is True
        assert bottom_analysis.is_watertight is True

        assert pytest.approx(top_analysis.volume_cm3, rel=1e-2) == 4.0
        assert pytest.approx(bottom_analysis.volume_cm3, rel=1e-2) == 4.0
        assert pytest.approx(top_analysis.volume_cm3 + bottom_analysis.volume_cm3, rel=1e-2) == 8.0

        assert pytest.approx(top_analysis.bounds.dimensions_mm[2], abs=1e-2) == 10.0
        assert pytest.approx(bottom_analysis.bounds.dimensions_mm[2], abs=1e-2) == 10.0
        assert pytest.approx(cut_area, rel=1e-1) == 4.0

    def test_sagittal_x_axis_slice(self, cube_20mm_mesh):
        """
        Slice 20x20x20mm cube along X-axis at X=0 (mid-width) with normal [1, 0, 0].
        Each half is 10x20x20mm.
        """
        grounded = center_mesh_on_bed(cube_20mm_mesh)
        top_slice, bottom_slice, cut_area = slice_mesh(
            mesh=grounded,
            plane_origin=[0.0, 0.0, 10.0],
            plane_normal=[1.0, 0.0, 0.0],
            cap_faces=True,
        )

        top_analysis = analyze_mesh(top_slice)
        bottom_analysis = analyze_mesh(bottom_slice)

        assert top_analysis.is_watertight is True
        assert bottom_analysis.is_watertight is True
        assert pytest.approx(top_analysis.bounds.dimensions_mm[0], abs=1e-2) == 10.0
        assert pytest.approx(bottom_analysis.bounds.dimensions_mm[0], abs=1e-2) == 10.0
        assert pytest.approx(top_analysis.volume_cm3, rel=1e-2) == 4.0

    def test_slice_with_alignment_pegs(self, cube_20mm_mesh):
        """
        Slice cube with alignment dowel pin/socket generation enabled.
        Produces valid split meshes.
        """
        grounded = center_mesh_on_bed(cube_20mm_mesh)
        top_slice, bottom_slice, cut_area = slice_mesh(
            mesh=grounded,
            plane_origin=[0.0, 0.0, 10.0],
            plane_normal=[0.0, 0.0, 1.0],
            cap_faces=True,
            create_pegs=True,
            peg_radius_mm=2.0,
            peg_height_mm=4.0,
            peg_clearance_mm=0.2,
        )

        assert top_slice is not None
        assert bottom_slice is not None
        assert len(top_slice.faces) > 0
        assert len(bottom_slice.faces) > 0

    def test_slice_out_of_bounds_raises_error(self, cube_20mm_mesh):
        """Plane entirely above or below mesh raises MeshProcessingError."""
        with pytest.raises(MeshProcessingError, match="empty"):
            slice_mesh(
                mesh=cube_20mm_mesh,
                plane_origin=[0.0, 0.0, 100.0], # Far above top Z=20
                plane_normal=[0.0, 0.0, 1.0],
            )

    def test_slice_empty_mesh_raises_validation_error(self):
        """Empty mesh raises MeshValidationError."""
        empty_mesh = trimesh.Trimesh()
        with pytest.raises(MeshValidationError, match="empty"):
            slice_mesh(empty_mesh)


class TestMeshRepair:
    """QA test suite for automated mesh repair, normal healing, and hole filling."""

    def test_repair_open_hole_mesh(self):
        """
        Create a box with a missing top face (open/non-watertight).
        Run repair_mesh to fill boundary hole and restore watertight manifold status.
        """
        # Create a cube and remove 2 triangular faces forming the top face
        box = trimesh.creation.box(extents=[20.0, 20.0, 20.0])
        # Remove top 2 faces (faces with +Z normals)
        top_face_mask = box.face_normals[:, 2] > 0.9
        non_top_faces = box.faces[~top_face_mask]
        open_box = trimesh.Trimesh(vertices=box.vertices, faces=non_top_faces, process=False)

        assert open_box.is_watertight is False

        repaired, report = repair_mesh(
            mesh=open_box,
            fill_holes=True,
            fix_normals=True,
            remove_degenerate=True,
            weld_vertices=True,
        )

        assert report.is_watertight_before is False
        assert report.is_watertight_after is True
        assert repaired.is_watertight is True
        assert report.holes_filled >= 1
        assert report.volume_restored_cm3 is not None
        assert pytest.approx(report.volume_restored_cm3, rel=1e-2) == 8.0

    def test_repair_degenerate_faces_and_duplicate_vertices(self):
        """
        Create a mesh with duplicate vertices and a zero-area degenerate face.
        Run repair_mesh and verify degenerate triangles are purged and duplicate vertices welded.
        """
        # Base cube
        box = trimesh.creation.box(extents=[10.0, 10.0, 10.0])
        v = box.vertices.copy()
        f = box.faces.copy()

        # Add a duplicate vertex at [0, 0, 0]
        v_extra = np.vstack([v, [0.0, 0.0, 0.0]])
        # Add a degenerate face with vertices [0, 0, 0]
        f_extra = np.vstack([f, [len(v), len(v), len(v)]])

        dirty_mesh = trimesh.Trimesh(vertices=v_extra, faces=f_extra, process=False)
        repaired, report = repair_mesh(
            mesh=dirty_mesh,
            fill_holes=True,
            fix_normals=True,
            remove_degenerate=True,
            weld_vertices=True,
        )

        assert report.degenerate_faces_removed >= 1 or report.duplicate_vertices_welded >= 1
        assert repaired.is_watertight is True

    def test_repair_already_watertight_mesh(self, cube_20mm_mesh):
        """Repairing an already valid watertight mesh preserves geometry and volume."""
        repaired, report = repair_mesh(cube_20mm_mesh)

        assert report.is_watertight_before is True
        assert report.is_watertight_after is True
        assert repaired.is_watertight is True
        assert pytest.approx(report.volume_restored_cm3, rel=1e-2) == 8.0

    def test_repair_empty_mesh_raises_validation_error(self):
        """Attempting to repair empty mesh raises MeshValidationError."""
        empty = trimesh.Trimesh()
        with pytest.raises(MeshValidationError, match="empty"):
            repair_mesh(empty)
