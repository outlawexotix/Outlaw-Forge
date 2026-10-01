import httpx
import json
import sys

def main():
    base_url = "http://127.0.0.1:8000"
    
    with httpx.Client(base_url=base_url, timeout=10.0) as client:
        # 1. Health check
        r = client.get("/health")
        print("Health Status:", r.status_code, r.json())
        assert r.status_code == 200
        
        # 2. List filaments
        r = client.get("/filaments")
        print("Filaments count:", len(r.json()))
        assert r.status_code == 200
        assert len(r.json()) >= 7
        
        # 3. Create project
        r = client.post("/projects", json={"name": "OrcaSlicer Suite Test", "project_type": "Mechanical Part"})
        print("Create Project:", r.status_code)
        assert r.status_code == 201
        proj_id = r.json()["id"]
        
        # 4. Generate Temp Tower
        r = client.post(f"/projects/{proj_id}/calibration/generate", json={
            "calibration_type": "temp_tower",
            "start_temp_c": 220,
            "end_temp_c": 190,
            "temp_step_c": 10
        })
        print("Generate Temp Tower:", r.status_code, r.json()["message"])
        assert r.status_code == 201
        model_id = r.json()["model"]["id"]
        
        # 5. Auto-Orient
        r = client.post(f"/projects/{proj_id}/models/{model_id}/auto_orient", json={})
        print("Auto Orient:", r.status_code, r.json()["message"])
        assert r.status_code == 200
        
        # 6. Mouse Ears
        r = client.post(f"/projects/{proj_id}/models/{model_id}/mouse_ears", json={
            "radius_mm": 6.0,
            "thickness_mm": 0.2
        })
        print("Mouse Ears:", r.status_code, r.json()["message"])
        assert r.status_code == 200
        
        # 7. Adaptive Layers
        r = client.post(f"/projects/{proj_id}/models/{model_id}/adaptive_layers", json={})
        print("Adaptive Layers:", r.status_code, r.json()["message"])
        assert r.status_code == 200
        
        # 8. Estimate Cost
        r = client.post(f"/projects/{proj_id}/models/{model_id}/estimate_cost", json={
            "filament_id": "generic_pla",
            "infill_percentage": 20.0
        })
        print("Cost Estimation:", r.status_code, r.json()["message"])
        assert r.status_code == 200
        
        # 9. Auto-Arrange
        r = client.post(f"/projects/{proj_id}/auto_arrange", json={"spacing_mm": 10.0})
        print("Auto-Arrange:", r.status_code, r.json()["message"])
        assert r.status_code == 200

        print("\nALL ORCASLICER SUITE FEATURES VERIFIED SUCCESSFULLY!")

if __name__ == "__main__":
    main()
