import tempfile
from pathlib import Path
import numpy as np
import pytest
import trimesh

from app.services.mesh_service import MeshService


class TestMeshService:
    @pytest.fixture
    def sample_box_stl(self):
        # Create a 20mm x 30mm x 40mm box mesh
        mesh = trimesh.creation.box(extents=[20.0, 30.0, 40.0])
        with tempfile.NamedTemporaryFile(suffix=".stl", delete=False) as f:
            temp_path = f.name
        mesh.export(temp_path, file_type="stl")
        yield Path(temp_path)
        if Path(temp_path).exists():
            Path(temp_path).unlink()

    def test_load_mesh(self, sample_box_stl: Path):
        mesh = MeshService.load_mesh(sample_box_stl)
        assert isinstance(mesh, trimesh.Trimesh)
        assert len(mesh.faces) > 0
        assert len(mesh.vertices) > 0

    def test_analyze_mesh(self, sample_box_stl: Path):
        mesh = MeshService.load_mesh(sample_box_stl)
        analysis = MeshService.analyze_mesh(mesh)

        dims = analysis.bounds.dimensions_mm
        assert np.isclose(dims[0], 20.0, atol=0.1)
        assert np.isclose(dims[1], 30.0, atol=0.1)
        assert np.isclose(dims[2], 40.0, atol=0.1)

        assert analysis.is_watertight is True
        assert analysis.triangle_count == 12  # Box has 12 triangles
        assert analysis.vertex_count == 8

        # Expected volume: 20 * 30 * 40 = 24,000 mm^3 = 24.0 cm^3
        assert np.isclose(analysis.volume_cm3, 24.0, atol=0.1)

        # Expected surface area: 2*(20*30 + 20*40 + 30*40) = 2*(600 + 800 + 1200) = 5200 mm^2 = 52.0 cm^2
        assert np.isclose(analysis.surface_area_cm2, 52.0, atol=0.1)

    def test_scale_mesh_uniform_percentage(self, sample_box_stl: Path):
        mesh = MeshService.load_mesh(sample_box_stl)
        scaled_mesh, transform = MeshService.scale_mesh_with_transform(mesh, payload_or_percent=200.0)

        dims = scaled_mesh.extents
        assert np.isclose(dims[0], 40.0, atol=0.1)
        assert np.isclose(dims[1], 60.0, atol=0.1)
        assert np.isclose(dims[2], 80.0, atol=0.1)
        assert transform.uniform_scale_percent == 200.0

    def test_scale_mesh_target_height_preserve_aspect(self, sample_box_stl: Path):
        mesh = MeshService.load_mesh(sample_box_stl)
        # Original height is 40mm, target 80mm -> 2x uniform scale
        scaled_mesh, transform = MeshService.scale_mesh_with_transform(
            mesh, target_h=80.0, preserve_aspect=True
        )

        dims = scaled_mesh.extents
        assert np.isclose(dims[2], 80.0, atol=0.1)
        assert np.isclose(dims[0], 40.0, atol=0.1)
        assert np.isclose(dims[1], 60.0, atol=0.1)
        assert transform.uniform_scale_percent == 200.0

    def test_scale_mesh_non_uniform(self, sample_box_stl: Path):
        mesh = MeshService.load_mesh(sample_box_stl)
        scaled_mesh, transform = MeshService.scale_mesh_with_transform(
            mesh, target_w=50.0, target_d=30.0, target_h=40.0, preserve_aspect=False
        )

        dims = scaled_mesh.extents
        assert np.isclose(dims[0], 50.0, atol=0.1)
        assert np.isclose(dims[1], 30.0, atol=0.1)
        assert np.isclose(dims[2], 40.0, atol=0.1)

    def test_export_mesh_formats(self, sample_box_stl: Path):
        mesh = MeshService.load_mesh(sample_box_stl)

        with tempfile.TemporaryDirectory() as tmpdir:
            stl_out = Path(tmpdir) / "out.stl"
            obj_out = Path(tmpdir) / "out.obj"
            glb_out = Path(tmpdir) / "out.glb"

            MeshService.export_mesh(mesh, stl_out, "stl")
            assert stl_out.exists() and stl_out.stat().st_size > 0

            MeshService.export_mesh(mesh, obj_out, "obj")
            assert obj_out.exists() and obj_out.stat().st_size > 0

            MeshService.export_mesh(mesh, glb_out, "glb")
            assert glb_out.exists() and glb_out.stat().st_size > 0

    def test_rotate_mesh_euler_angles(self, sample_box_stl: Path):
        mesh = MeshService.load_mesh(sample_box_stl)
        # Original box extents: [20.0, 30.0, 40.0]
        # Rotate 90 deg around Z: X and Y swap extents -> [30.0, 20.0, 40.0]
        rotated_z = MeshService.rotate_mesh(mesh, rz_deg=90.0)
        dims_z = rotated_z.extents
        assert np.isclose(dims_z[0], 30.0, atol=0.1)
        assert np.isclose(dims_z[1], 20.0, atol=0.1)
        assert np.isclose(dims_z[2], 40.0, atol=0.1)

        # Rotate 90 deg around X: Y and Z swap extents -> [20.0, 40.0, 30.0]
        rotated_x = MeshService.rotate_mesh(mesh, rx_deg=90.0)
        dims_x = rotated_x.extents
        assert np.isclose(dims_x[0], 20.0, atol=0.1)
        assert np.isclose(dims_x[1], 40.0, atol=0.1)
        assert np.isclose(dims_x[2], 30.0, atol=0.1)

        # Rotate 90 deg around Y: X and Z swap extents -> [40.0, 30.0, 20.0]
        rotated_y = MeshService.rotate_mesh(mesh, ry_deg=90.0)
        dims_y = rotated_y.extents
        assert np.isclose(dims_y[0], 40.0, atol=0.1)
        assert np.isclose(dims_y[1], 30.0, atol=0.1)
        assert np.isclose(dims_y[2], 20.0, atol=0.1)

    def test_center_mesh_on_bed(self, sample_box_stl: Path):
        mesh = MeshService.load_mesh(sample_box_stl)
        # Translate it somewhere arbitrary first
        mesh.apply_translation([100.0, -50.0, 25.0])
        assert mesh.bounds[0][2] != 0.0

        centered = MeshService.center_mesh_on_bed(mesh)
        bounds_min = centered.bounds[0]
        bounds_max = centered.bounds[1]

        # Minimum Z must be 0.0 (resting flat on print bed)
        assert np.isclose(bounds_min[2], 0.0, atol=1e-3)
        # Center of X and Y must be 0.0
        center_x = (bounds_min[0] + bounds_max[0]) / 2.0
        center_y = (bounds_min[1] + bounds_max[1]) / 2.0
        assert np.isclose(center_x, 0.0, atol=1e-3)
        assert np.isclose(center_y, 0.0, atol=1e-3)

    def test_lay_flat_mesh(self, sample_box_stl: Path):
        mesh = MeshService.load_mesh(sample_box_stl)
        # Box is 20 x 30 x 40. Largest faces are 30 x 40 (area 1200 mm^2).
        # When laying flat, the 30x40 face should be on Z=0, so the height in Z should become 20.0
        # First arbitrarily rotate the box
        rot_mesh = MeshService.rotate_mesh(mesh, rx_deg=45.0, ry_deg=30.0, rz_deg=60.0)
        flat_mesh = MeshService.lay_flat_mesh(rot_mesh)

        assert np.isclose(flat_mesh.bounds[0][2], 0.0, atol=0.1)
        # Height should be the smallest extent of the box (20.0 mm)
        assert np.isclose(flat_mesh.extents[2], 20.0, atol=0.1)

    def test_analyze_overhangs(self, sample_box_stl: Path):
        mesh = MeshService.load_mesh(sample_box_stl)
        centered = MeshService.center_mesh_on_bed(mesh)
        # A rectangular box has 6 faces: 1 bottom face pointing straight down (n_z = -1.0)
        # and 5 faces (4 vertical walls with n_z = 0, 1 top face with n_z = 1.0).
        # The bottom face area is 20 * 30 = 600 mm^2 = 6.0 cm^2
        # Total area is 2*(20*30 + 20*40 + 30*40) = 5200 mm^2 = 52.0 cm^2
        # Percentage of overhang at 45 deg critical angle: 600 / 5200 * 100 = 11.54%
        res = MeshService.analyze_overhangs(centered, critical_angle_deg=45.0)

        assert res.critical_angle_deg == 45.0
        assert res.requires_support is True
        assert res.overhang_face_count == 2  # Trimesh box has 2 triangles per quad face
        assert res.total_face_count == 12
        assert np.isclose(res.overhang_area_cm2, 6.0, atol=0.1)
        assert np.isclose(res.total_area_cm2, 52.0, atol=0.1)
        assert np.isclose(res.overhang_percentage, 11.54, atol=0.2)
        assert float(res) == res.overhang_percentage

