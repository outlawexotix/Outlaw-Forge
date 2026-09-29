import pytest

from app.models.printer import PrinterProfile
from app.services.printability_service import check_printability


class TestPrintabilityAnalysis:
    """Deterministic printability and build volume validation test suite."""

    def test_model_fits_within_ender3(self, ender3_profile):
        """
        A 20x20x20 mm cube fits easily within Ender-3 build volume (220 x 220 x 250 mm).
        - fits_build_volume: True
        - exceeded_dimensions_mm: (0.0, 0.0, 0.0)
        - findings: severity is INFO
        """
        analysis = check_printability(
            dimensions_mm=[20.0, 20.0, 20.0],
            printer=ender3_profile,
            model_id="cube_20mm",
        )

        assert analysis.fits_build_volume is True
        assert analysis.exceeded_dimensions_mm.x == 0.0
        assert analysis.exceeded_dimensions_mm.y == 0.0
        assert analysis.exceeded_dimensions_mm.z == 0.0
        assert len(analysis.findings) >= 1
        assert any(f.severity == "INFO" for f in analysis.findings)
        assert analysis.printer_id == "ender-3-standard"

    def test_oversized_mesh_exceeds_ender3_all_axes(self, ender3_profile):
        """
        A 300x300x300 mm model on Ender-3 (220 x 220 x 250 mm):
        - X exceeds by: 300 - 220 = 80.0 mm
        - Y exceeds by: 300 - 220 = 80.0 mm
        - Z exceeds by: 300 - 250 = 50.0 mm
        - fits_build_volume: False
        - findings: severity is ERROR
        """
        analysis = check_printability(
            dimensions_mm=[300.0, 300.0, 300.0],
            printer=ender3_profile,
            model_id="cube_300mm",
        )

        assert analysis.fits_build_volume is False
        assert pytest.approx(analysis.exceeded_dimensions_mm.x, rel=1e-3) == 80.0
        assert pytest.approx(analysis.exceeded_dimensions_mm.y, rel=1e-3) == 80.0
        assert pytest.approx(analysis.exceeded_dimensions_mm.z, rel=1e-3) == 50.0
        assert len(analysis.findings) >= 1
        assert analysis.findings[0].severity == "ERROR"
        assert "80.0" in analysis.findings[0].message
        assert "50.0" in analysis.findings[0].message

    def test_exact_build_volume_boundary(self, ender3_profile):
        """
        A model exactly matching the 220x220x250 mm build volume boundary fits perfectly.
        """
        analysis = check_printability(
            dimensions_mm=[220.0, 220.0, 250.0],
            printer=ender3_profile,
        )

        assert analysis.fits_build_volume is True
        assert analysis.exceeded_dimensions_mm.x == 0.0
        assert analysis.exceeded_dimensions_mm.y == 0.0
        assert analysis.exceeded_dimensions_mm.z == 0.0
        assert analysis.findings[0].severity == "INFO"

    def test_width_only_exceeded(self, ender3_profile):
        """Model exceeds width (X) only: 250 x 200 x 200 mm on Ender-3 (220 x 220 x 250 mm)."""
        analysis = check_printability(
            dimensions_mm=[250.0, 200.0, 200.0],
            printer=ender3_profile,
        )

        assert analysis.fits_build_volume is False
        assert pytest.approx(analysis.exceeded_dimensions_mm.x, rel=1e-3) == 30.0
        assert analysis.exceeded_dimensions_mm.y == 0.0
        assert analysis.exceeded_dimensions_mm.z == 0.0
        assert analysis.findings[0].severity == "ERROR"
        assert "Width (X)" in analysis.findings[0].message

    def test_depth_only_exceeded(self, ender3_profile):
        """Model exceeds depth (Y) only: 200 x 235 x 200 mm on Ender-3 (220 x 220 x 250 mm)."""
        analysis = check_printability(
            dimensions_mm=[200.0, 235.0, 200.0],
            printer=ender3_profile,
        )

        assert analysis.fits_build_volume is False
        assert analysis.exceeded_dimensions_mm.x == 0.0
        assert pytest.approx(analysis.exceeded_dimensions_mm.y, rel=1e-3) == 15.0
        assert analysis.exceeded_dimensions_mm.z == 0.0
        assert analysis.findings[0].severity == "ERROR"
        assert "Depth (Y)" in analysis.findings[0].message

    def test_height_only_exceeded(self, ender3_profile):
        """Model exceeds height (Z) only: 200 x 200 x 265 mm on Ender-3 (220 x 220 x 250 mm)."""
        analysis = check_printability(
            dimensions_mm=[200.0, 200.0, 265.0],
            printer=ender3_profile,
        )

        assert analysis.fits_build_volume is False
        assert analysis.exceeded_dimensions_mm.x == 0.0
        assert analysis.exceeded_dimensions_mm.y == 0.0
        assert pytest.approx(analysis.exceeded_dimensions_mm.z, rel=1e-3) == 15.0
        assert analysis.findings[0].severity == "ERROR"
        assert "Height (Z)" in analysis.findings[0].message

    def test_profile_comparison_ender3_vs_ender3_s1(self, ender3_profile, ender3_s1_profile):
        """
        A 200 x 200 x 260 mm model:
        - Exceeds Ender-3 (250mm height) by 10mm -> fits=False
        - Fits Ender-3 S1 (270mm height) -> fits=True
        """
        dims = [200.0, 200.0, 260.0]

        res_ender3 = check_printability(dims, ender3_profile)
        assert res_ender3.fits_build_volume is False
        assert pytest.approx(res_ender3.exceeded_dimensions_mm.z, rel=1e-3) == 10.0

        res_s1 = check_printability(dims, ender3_s1_profile)
        assert res_s1.fits_build_volume is True
        assert res_s1.exceeded_dimensions_mm.z == 0.0

    def test_printer_dict_input(self):
        """Check printability works with dictionary printer representation."""
        printer_dict = {
            "id": "custom-printer",
            "manufacturer": "Prusa",
            "model": "MK4",
            "build_width_mm": 250.0,
            "build_depth_mm": 210.0,
            "build_height_mm": 220.0,
        }

        analysis = check_printability(
            dimensions_mm=[240.0, 200.0, 210.0],
            printer=printer_dict,
        )

        assert analysis.fits_build_volume is True
        assert analysis.printer_id == "custom-printer"
