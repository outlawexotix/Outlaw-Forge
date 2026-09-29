#!/usr/bin/env python3
"""
Outlaw Forge - Critical End-to-End Workflow Verification Suite
============================================================
Validates the complete Milestone 2 Functional Slice:

CREATE PROJECT
→ IMPORT MODEL
→ VIEW MODEL / ANALYZE DIMENSIONS
→ PRINTABILITY EVALUATION
→ DETERMINISTIC SCALING (NORMAL & OVERSIZED)
→ MESH ROTATION (90° X/Y/Z)
→ MESH CENTERING ON BED (Z_min = 0, Center X, Y = 0, 0)
→ LAY FLAT ORIENTATION
→ OVERHANG ANALYSIS DIAGNOSTICS
→ SAVE AND RELOAD
→ EXPORT MODEL & VERIFY ON DISK
"""

import sys
import os
import json
import time
import io
import urllib.request
import urllib.error

BASE_URL = os.environ.get("OUTLAW_FORGE_API_URL", "http://127.0.0.1:8000").rstrip("/")

class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    RESET = "\033[0m"

class CriticalWorkflowRunner:
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.project_id = None
        self.model_id = None
        self.printer_id = None
        self.tests_passed = 0
        self.tests_failed = 0

    def step(self, title: str):
        print(f"\n{Colors.BOLD}{Colors.CYAN}> [STEP] {title}{Colors.RESET}")

    def assert_test(self, name: str, condition: bool, details: str = ""):
        if condition:
            print(f"  {Colors.GREEN}[PASS]{Colors.RESET} {name} {f'({details})' if details else ''}")
            self.tests_passed += 1
        else:
            print(f"  {Colors.RED}[FAIL]{Colors.RESET} {name} - {details}")
            self.tests_failed += 1

    def _request(self, endpoint: str, method: str = "GET", data: dict = None, files: dict = None) -> tuple[int, dict]:
        url = f"{self.base_url}{endpoint}"
        req_headers = {"Accept": "application/json"}
        body = None

        if files:
            # Multipart upload
            boundary = f"----WebKitFormBoundary{int(time.time()*1000)}"
            req_headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
            buffer = io.BytesIO()
            for field_name, (filename, file_bytes, mime) in files.items():
                buffer.write(f"--{boundary}\r\n".encode())
                buffer.write(f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'.encode())
                buffer.write(f"Content-Type: {mime}\r\n\r\n".encode())
                buffer.write(file_bytes)
                buffer.write(b"\r\n")
            buffer.write(f"--{boundary}--\r\n".encode())
            body = buffer.getvalue()
        elif data is not None:
            req_headers["Content-Type"] = "application/json"
            body = json.dumps(data).encode("utf-8")

        req = urllib.request.Request(url, data=body, headers=req_headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=10.0) as resp:
                resp_body = resp.read().decode("utf-8")
                return resp.status, json.loads(resp_body) if resp_body else {}
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8")
            try:
                return e.code, json.loads(err_body)
            except Exception:
                return e.code, {"error": err_body}
        except Exception as e:
            return 500, {"error": str(e)}

    def run(self) -> bool:
        print(f"\n{Colors.BOLD}{Colors.YELLOW}{'='*65}")
        print(" OUTLAW FORGE: CRITICAL END-TO-END WORKFLOW TEST (MILESTONE 2)")
        print(f" Target Host: {self.base_url}")
        print(f"{'='*65}{Colors.RESET}\n")

        # 1. Health Probe
        self.step("1. Backend API Diagnostics & Readiness")
        status, data = self._request("/health")
        self.assert_test("Health endpoint 200 OK", status == 200, f"Status: {status}")
        self.assert_test("Health status is healthy", data.get("status") == "healthy")
        self.assert_test("Mesh engine service ready", data.get("services", {}).get("mesh_engine") == "ready")

        # 2. Printer Profiles Listing & Selection
        self.step("2. Query Available Printer Profiles (All 6 Seeded Profiles)")
        status, printers = self._request("/printers")
        self.assert_test("Printers endpoint 200 OK", status == 200, f"Count: {len(printers)}")
        self.assert_test("At least 6 default printer profiles present", len(printers) >= 6)

        ender3 = next((p for p in printers if p.get("id") == "printer_ender_3" or "Ender-3" in p.get("model", "")), None)
        self.assert_test("Found Creality Ender-3 profile", ender3 is not None, f"Model: {ender3.get('model') if ender3 else 'None'}")
        if ender3:
            self.printer_id = ender3["id"]
            self.assert_test(
                "Ender-3 dimensions (220x220x250mm)",
                ender3["build_width_mm"] == 220 and ender3["build_depth_mm"] == 220 and ender3["build_height_mm"] == 250,
            )

        # 3. Project Creation
        self.step("3. Create New Engineering Project")
        project_payload = {
            "name": "E2E Cyberpunk Oni Mask",
            "description": "Functional slice test project for Milestone 2",
            "project_type": "Mask",
            "selected_printer_id": self.printer_id,
            "notes": "Testing scaling, rotation, bed centering, lay flat, and overhang analysis",
        }
        status, project = self._request("/projects", method="POST", data=project_payload)
        self.assert_test("Project creation 201 Created", status == 201, f"Status: {status}")
        self.project_id = project.get("id")
        self.assert_test("Project ID assigned", bool(self.project_id), f"ID: {self.project_id}")
        self.assert_test("Project Type preserved", project.get("project_type") == "Mask")

        # 4. Import Known 20x20x20mm Test Mesh
        self.step("4. Secure Import of 20x20x20mm Calibration Cube STL")
        fixture_path = os.path.join(os.path.dirname(__file__), "..", "apps", "api", "tests", "fixtures", "cube_20mm.stl")
        if not os.path.exists(fixture_path):
            fixture_path = "D:/Outlaw-Forge/apps/api/tests/fixtures/cube_20mm.stl"

        with open(fixture_path, "rb") as f:
            stl_bytes = f.read()

        files = {"file": ("calibration_cube.stl", stl_bytes, "application/octet-stream")}
        status, model = self._request(f"/projects/{self.project_id}/models/import", method="POST", files=files)
        self.assert_test("Model import 201 Created", status == 201, f"Status: {status}")
        self.model_id = model.get("id")
        self.assert_test("Working Model ID assigned", bool(self.model_id), f"Model ID: {self.model_id}")

        # 5. Dimension & Geometry Precision Analysis
        self.step("5. Analyze Model Dimensions & Topology")
        dims = model.get("bounds", {}).get("dimensions_mm", [0, 0, 0])
        self.assert_test("X dimension = 20.0 mm", abs(dims[0] - 20.0) < 0.01, f"X={dims[0]:.2f}")
        self.assert_test("Y dimension = 20.0 mm", abs(dims[1] - 20.0) < 0.01, f"Y={dims[1]:.2f}")
        self.assert_test("Z dimension = 20.0 mm", abs(dims[2] - 20.0) < 0.01, f"Z={dims[2]:.2f}")
        self.assert_test("Watertight status is True", model.get("is_watertight") is True)
        self.assert_test("Volume = 8.0 cm3", abs((model.get("volume_cm3") or 0) - 8.0) < 0.1, f"Vol={model.get('volume_cm3')} cm3")

        # 6. Check Initial Build Volume Fit (Ender-3)
        self.step("6. Printability Evaluation (Initial 20mm Model)")
        status, printability = self._request(f"/projects/{self.project_id}/printability")
        self.assert_test("Printability check 200 OK", status == 200)
        self.assert_test("Model fits within Ender-3 build volume", printability.get("fits_build_volume") is True)
        exceeded = printability.get("exceeded_dimensions_mm", {})
        self.assert_test("Zero exceeded dimensions", exceeded.get("x") == 0 and exceeded.get("y") == 0 and exceeded.get("z") == 0)

        # 7. Deterministic Scaling: Scale Height to 100mm with Aspect Lock
        self.step("7. Scale Model Height to 100.0 mm (Aspect Ratio Locked)")
        scale_payload = {
            "target_height_mm": 100.0,
            "preserve_aspect_ratio": True,
        }
        status, scaled_model = self._request(f"/projects/{self.project_id}/models/{self.model_id}/scale", method="POST", data=scale_payload)
        self.assert_test("Model scale 200 OK", status == 200)
        s_dims = scaled_model.get("bounds", {}).get("dimensions_mm", [0, 0, 0])
        self.assert_test("Scaled X = 100.0 mm", abs(s_dims[0] - 100.0) < 0.05, f"X={s_dims[0]:.2f}")
        self.assert_test("Scaled Y = 100.0 mm", abs(s_dims[1] - 100.0) < 0.05, f"Y={s_dims[1]:.2f}")
        self.assert_test("Scaled Z = 100.0 mm", abs(s_dims[2] - 100.0) < 0.05, f"Z={s_dims[2]:.2f}")
        self.assert_test("Scaled Volume = 1000.0 cm3", abs((scaled_model.get("volume_cm3") or 0) - 1000.0) < 5.0, f"Vol={scaled_model.get('volume_cm3')} cm3")

        # 8. Scale to Oversized (300mm) to Trigger Printability Warnings
        self.step("8. Scale Model to Oversized 300mm to Verify Fit Envelope Alerts")
        oversize_payload = {
            "target_height_mm": 300.0,
            "preserve_aspect_ratio": True,
        }
        status, oversized = self._request(f"/projects/{self.project_id}/models/{self.model_id}/scale", method="POST", data=oversize_payload)
        self.assert_test("Oversize scale 200 OK", status == 200)

        status, over_printability = self._request(f"/projects/{self.project_id}/printability")
        self.assert_test("Printability check detects oversized model", over_printability.get("fits_build_volume") is False)
        over_exceeded = over_printability.get("exceeded_dimensions_mm", {})
        self.assert_test("Exceeded Width X = +80.0 mm", abs(over_exceeded.get("x", 0) - 80.0) < 0.5, f"+{over_exceeded.get('x'):.2f} mm")
        self.assert_test("Exceeded Depth Y = +80.0 mm", abs(over_exceeded.get("y", 0) - 80.0) < 0.5, f"+{over_exceeded.get('y'):.2f} mm")
        self.assert_test("Exceeded Height Z = +50.0 mm", abs(over_exceeded.get("z", 0) - 50.0) < 0.5, f"+{over_exceeded.get('z'):.2f} mm")

        # 9. Scale Back to 150mm
        self.step("9. Scale Back to Optimal 150.0 mm")
        optimal_payload = {"target_height_mm": 150.0, "preserve_aspect_ratio": True}
        status, opt_model = self._request(f"/projects/{self.project_id}/models/{self.model_id}/scale", method="POST", data=optimal_payload)
        self.assert_test("Scaled back to 150mm", abs(opt_model.get("bounds", {}).get("dimensions_mm", [0,0,0])[2] - 150.0) < 0.1)

        # 10. Mesh Rotation: Rotate 90° Around X Axis
        self.step("10. Rotate Model 90° Around X Axis")
        rot_payload = {"rx_deg": 90.0, "ry_deg": 0.0, "rz_deg": 0.0}
        status, rot_model = self._request(f"/projects/{self.project_id}/models/{self.model_id}/rotate", method="POST", data=rot_payload)
        self.assert_test("Model rotate 200 OK", status == 200)
        r_dims = rot_model.get("bounds", {}).get("dimensions_mm", [0, 0, 0])
        self.assert_test("Rotated model maintains dimensions (150x150x150mm)", abs(r_dims[0] - 150.0) < 0.1 and abs(r_dims[1] - 150.0) < 0.1 and abs(r_dims[2] - 150.0) < 0.1)
        self.assert_test("Rotation angles recorded in transform", rot_model.get("transform", {}).get("rotation_deg") is not None)

        # 11. Mesh Centering on Bed: Z_min = 0, Center X,Y = (0,0)
        self.step("11. Center Model on Build Bed (Z_min = 0, Center X, Y = 0, 0)")
        status, centered_model = self._request(f"/projects/{self.project_id}/models/{self.model_id}/center", method="POST", data={})
        self.assert_test("Model center 200 OK", status == 200)
        c_bounds = centered_model.get("bounds", {})
        c_min = c_bounds.get("min", [0, 0, 0])
        c_max = c_bounds.get("max", [0, 0, 0])
        self.assert_test("Z min positioned at Z = 0.0 mm", abs(c_min[2]) < 0.05, f"Z_min={c_min[2]:.2f}")
        center_x = (c_min[0] + c_max[0]) / 2.0
        center_y = (c_min[1] + c_max[1]) / 2.0
        self.assert_test("Center X = 0.0 mm", abs(center_x) < 0.05, f"CenterX={center_x:.2f}")
        self.assert_test("Center Y = 0.0 mm", abs(center_y) < 0.05, f"CenterY={center_y:.2f}")

        # 12. Lay Flat Orientation Verification
        self.step("12. Lay Flat Orientation on Build Bed")
        status, flat_model = self._request(f"/projects/{self.project_id}/models/{self.model_id}/lay_flat", method="POST", data={})
        self.assert_test("Model lay flat 200 OK", status == 200)
        f_bounds = flat_model.get("bounds", {})
        f_min = f_bounds.get("min", [0, 0, 0])
        self.assert_test("Lay flat Z min is at Z = 0.0 mm", abs(f_min[2]) < 0.05, f"Z_min={f_min[2]:.2f}")
        self.assert_test("Watertightness preserved after lay flat", flat_model.get("is_watertight") is True)

        # 13. Overhang Diagnostics Analysis
        self.step("13. Overhang Support Diagnostics Analysis")
        status, overhang_res = self._request(f"/projects/{self.project_id}/models/{self.model_id}/overhangs?critical_angle_deg=45.0")
        self.assert_test("Overhang diagnostics 200 OK", status == 200)
        self.assert_test("Critical angle is 45.0 degrees", overhang_res.get("critical_angle_deg") == 45.0)
        self.assert_test("Total surface area calculated > 0", overhang_res.get("total_area_cm2", 0) > 0)
        self.assert_test("Overhang metrics reported", "overhang_percentage" in overhang_res)

        # 14. Save, Close, and Reload Project State
        self.step("14. Save and Reload Project State Across Restarts")
        patch_payload = {
            "notes": "Production sliced revision with verified rotation, centering, and lay flat"
        }
        status, updated_proj = self._request(f"/projects/{self.project_id}", method="PATCH", data=patch_payload)
        self.assert_test("Project patch 200 OK", status == 200)

        status, reloaded = self._request(f"/projects/{self.project_id}")
        self.assert_test("Project reload 200 OK", status == 200)
        self.assert_test("Reloaded notes match", reloaded.get("notes") == "Production sliced revision with verified rotation, centering, and lay flat")
        self.assert_test("Reloaded working models intact", len(reloaded.get("working_models", [])) >= 1)
        self.assert_test("Reloaded operations history tracked", len(reloaded.get("operations", [])) >= 5)

        # 15. Model Export Generation
        self.step("15. Export Transformed Model to STL")
        export_payload = {
            "format": "stl",
            "filename": "oni_mask_150mm_final.stl",
        }
        status, export_res = self._request(f"/projects/{self.project_id}/models/{self.model_id}/export", method="POST", data=export_payload)
        self.assert_test("Model export 200 OK", status == 200)
        download_url = export_res.get("download_url")
        self.assert_test("Export download URL provided", bool(download_url), f"URL: {download_url}")

        # 16. Verify Export Artifact Integrity
        self.step("16. Verify Export Artifact File Integrity")
        actual_filename = download_url.split("/")[-1] if download_url else export_res.get("filename", "")
        export_file_path = os.path.join("data", "exports", actual_filename)
        self.assert_test("Exported file exists on disk", os.path.exists(export_file_path), f"Path: {export_file_path}")
        self.assert_test(
            "Exported file size > 0 bytes",
            os.path.exists(export_file_path) and os.path.getsize(export_file_path) > 0,
            f"Size: {os.path.getsize(export_file_path) if os.path.exists(export_file_path) else 0} bytes",
        )

        # Summary
        print(f"\n{Colors.BOLD}{Colors.YELLOW}{'='*65}")
        print(" CRITICAL WORKFLOW TEST SUMMARY")
        print(f"{'='*65}{Colors.RESET}")
        print(f"Total Checks Executed : {self.tests_passed + self.tests_failed}")
        print(f"Passed                : {Colors.GREEN}{self.tests_passed}{Colors.RESET}")
        print(f"Failed                : {Colors.RED if self.tests_failed > 0 else Colors.GREEN}{self.tests_failed}{Colors.RESET}")

        if self.tests_failed == 0:
            print(f"\n{Colors.GREEN}{Colors.BOLD}[OK] 100% OF CRITICAL WORKFLOW ACCEPTANCE CRITERIA SATISFIED.{Colors.RESET}\n")
            return True
        else:
            print(f"\n{Colors.RED}{Colors.BOLD}[FAIL] WORKFLOW TEST FAILED ({self.tests_failed} failures).{Colors.RESET}\n")
            return False

def main():
    runner = CriticalWorkflowRunner()
    success = runner.run()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
