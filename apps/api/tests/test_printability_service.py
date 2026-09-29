from app.models.printer import PrinterProfile
from app.models.project import MeshBounds, MeshTransform, WorkingModel
from app.services.printability_service import PrintabilityService


class TestPrintabilityService:
    @classmethod
    def setup_class(cls):
        cls.printer = PrinterProfile(
            id="printer_test_200",
            manufacturer="Creality",
            model="Ender-3",
            build_width_mm=220.0,
            build_depth_mm=220.0,
            build_height_mm=250.0,
            nozzle_diameter_mm=0.4,
        )

    def test_fitting_model(self):
        model = WorkingModel(
            id="wm_fit",
            project_id="proj_1",
            source_file_id="src_1",
            filename="fitting_cube.stl",
            file_format="stl",
            storage_path="working/cube.stl",
            units="mm",
            bounds=MeshBounds(
                min=[0.0, 0.0, 0.0],
                max=[100.0, 100.0, 150.0],
                dimensions_mm=[100.0, 100.0, 150.0],
            ),
            triangle_count=5000,
            vertex_count=2502,
            surface_area_cm2=600.0,
            volume_cm3=1500.0,
            is_watertight=True,
            transform=MeshTransform(),
            created_at="2026-09-28T00:00:00Z",
            updated_at="2026-09-28T00:00:00Z",
        )

        analysis = PrintabilityService.evaluate(model, self.printer)
        assert analysis.fits_build_volume is True
        assert analysis.exceeded_dimensions_mm.x == 0.0
        assert analysis.exceeded_dimensions_mm.y == 0.0
        assert analysis.exceeded_dimensions_mm.z == 0.0
        assert any(f.severity == "INFO" and f.category.lower() in ("build volume", "build_volume") for f in analysis.findings)

    def test_exceeded_dimensions(self):
        model = WorkingModel(
            id="wm_huge",
            project_id="proj_1",
            source_file_id="src_1",
            filename="oversized.stl",
            file_format="stl",
            storage_path="working/oversized.stl",
            units="mm",
            bounds=MeshBounds(
                min=[0.0, 0.0, 0.0],
                max=[250.0, 200.0, 300.0],
                dimensions_mm=[250.0, 200.0, 300.0],
            ),
            triangle_count=5000,
            vertex_count=2502,
            surface_area_cm2=1000.0,
            volume_cm3=2000.0,
            is_watertight=True,
            transform=MeshTransform(),
            created_at="2026-09-28T00:00:00Z",
            updated_at="2026-09-28T00:00:00Z",
        )

        analysis = PrintabilityService.evaluate(model, self.printer)
        assert analysis.fits_build_volume is False
        assert analysis.exceeded_dimensions_mm.x == 30.0  # 250 - 220
        assert analysis.exceeded_dimensions_mm.y == 0.0  # 200 < 220
        assert analysis.exceeded_dimensions_mm.z == 50.0  # 300 - 250
        assert any(f.severity == "ERROR" and f.category.lower() in ("build volume", "build_volume") for f in analysis.findings)


    def test_non_watertight_model(self):
        model = WorkingModel(
            id="wm_broken",
            project_id="proj_1",
            source_file_id="src_1",
            filename="broken_mesh.stl",
            file_format="stl",
            storage_path="working/broken.stl",
            units="mm",
            bounds=MeshBounds(
                min=[0.0, 0.0, 0.0],
                max=[50.0, 50.0, 50.0],
                dimensions_mm=[50.0, 50.0, 50.0],
            ),
            triangle_count=500,
            vertex_count=300,
            surface_area_cm2=150.0,
            volume_cm3=None,
            is_watertight=False,
            transform=MeshTransform(),
            created_at="2026-09-28T00:00:00Z",
            updated_at="2026-09-28T00:00:00Z",
        )

        analysis = PrintabilityService.evaluate(model, self.printer)
        assert any(f.severity == "WARNING" and f.category == "Mesh Integrity" for f in analysis.findings)
