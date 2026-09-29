import { 
  HealthStatusResponse, 
  Project, 
  ProjectCreatePayload, 
  ProjectUpdatePayload, 
  PrinterProfile, 
  PrinterProfileCreatePayload,
  WorkingModel, 
  PrintabilityAnalysis, 
  ScaleModelPayload, 
  RotateModelPayload,
  ExportModelPayload,
  OverhangAnalysis
} from "@shared/types/api";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl.replace(/\/$/, "");
  }

  /**
   * Check backend health status
   */
  async getHealth(signal?: AbortSignal): Promise<HealthStatusResponse> {
    const res = await fetch(`${this.baseUrl}/health`, {
      method: "GET",
      headers: {
        "Accept": "application/json",
      },
      signal,
      cache: "no-store",
    });

    if (!res.ok) {
      throw new Error(`Health check failed with status: ${res.status}`);
    }

    return (await res.json()) as HealthStatusResponse;
  }

  /**
   * List all projects
   */
  async listProjects(): Promise<Project[]> {
    const res = await fetch(`${this.baseUrl}/projects`, {
      method: "GET",
      headers: { "Accept": "application/json" },
      cache: "no-store",
    });
    if (!res.ok) throw new Error(`Failed to list projects: ${res.statusText}`);
    return res.json();
  }

  /**
   * Create a new project
   */
  async createProject(payload: ProjectCreatePayload): Promise<Project> {
    const res = await fetch(`${this.baseUrl}/projects`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "Accept": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error(`Failed to create project: ${res.statusText}`);
    return res.json();
  }

  /**
   * Get project by ID
   */
  async getProject(id: string): Promise<Project> {
    const res = await fetch(`${this.baseUrl}/projects/${id}`, {
      method: "GET",
      headers: { "Accept": "application/json" },
      cache: "no-store",
    });
    if (!res.ok) throw new Error(`Failed to get project: ${res.statusText}`);
    return res.json();
  }

  /**
   * Update project metadata
   */
  async updateProject(id: string, payload: ProjectUpdatePayload): Promise<Project> {
    const res = await fetch(`${this.baseUrl}/projects/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", "Accept": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error(`Failed to update project: ${res.statusText}`);
    return res.json();
  }

  /**
   * Delete project by ID
   */
  async deleteProject(id: string): Promise<{ success: boolean; id: string }> {
    const res = await fetch(`${this.baseUrl}/projects/${id}`, {
      method: "DELETE",
      headers: { "Accept": "application/json" },
    });
    if (!res.ok) throw new Error(`Failed to delete project: ${res.statusText}`);
    return res.json();
  }

  /**
   * Upload and import a 3D model
   */
  async importModel(projectId: string, file: File): Promise<WorkingModel> {
    const formData = new FormData();
    formData.append("file", file);

    const res = await fetch(`${this.baseUrl}/projects/${projectId}/models/import`, {
      method: "POST",
      headers: { "Accept": "application/json" },
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || "Failed to import model");
    }
    return res.json();
  }

  /**
   * List available printer profiles
   */
  async listPrinters(): Promise<PrinterProfile[]> {
    const res = await fetch(`${this.baseUrl}/printers`, {
      method: "GET",
      headers: { "Accept": "application/json" },
      cache: "no-store",
    });
    if (!res.ok) throw new Error(`Failed to list printers: ${res.statusText}`);
    return res.json();
  }

  /**
   * Create a new custom printer profile
   */
  async createPrinter(payload: PrinterProfileCreatePayload): Promise<PrinterProfile> {
    const res = await fetch(`${this.baseUrl}/printers`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "Accept": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || "Failed to create printer profile");
    }
    return res.json();
  }

  /**
   * Scale working model
   */
  async scaleModel(projectId: string, modelId: string, payload: ScaleModelPayload): Promise<WorkingModel> {
    const res = await fetch(`${this.baseUrl}/projects/${projectId}/models/${modelId}/scale`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "Accept": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error(`Failed to scale model: ${res.statusText}`);
    return res.json();
  }

  /**
   * Rotate working model
   */
  async rotateModel(projectId: string, modelId: string, payload: RotateModelPayload): Promise<WorkingModel> {
    const res = await fetch(`${this.baseUrl}/projects/${projectId}/models/${modelId}/rotate`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "Accept": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error(`Failed to rotate model: ${res.statusText}`);
    return res.json();
  }

  /**
   * Center working model on the build plate
   */
  async centerModel(projectId: string, modelId: string): Promise<WorkingModel> {
    const res = await fetch(`${this.baseUrl}/projects/${projectId}/models/${modelId}/center`, {
      method: "POST",
      headers: { "Accept": "application/json" },
    });
    if (!res.ok) throw new Error(`Failed to center model: ${res.statusText}`);
    return res.json();
  }

  /**
   * Lay working model flat on build surface (minimizing overhangs / height)
   */
  async layFlat(projectId: string, modelId: string): Promise<WorkingModel> {
    const res = await fetch(`${this.baseUrl}/projects/${projectId}/models/${modelId}/lay_flat`, {
      method: "POST",
      headers: { "Accept": "application/json" },
    });
    if (!res.ok) throw new Error(`Failed to lay model flat: ${res.statusText}`);
    return res.json();
  }

  /**
   * Get overhang inspection analysis
   */
  async getOverhangs(projectId: string, modelId: string, thresholdDeg: number = 45): Promise<OverhangAnalysis> {
    const res = await fetch(`${this.baseUrl}/projects/${projectId}/models/${modelId}/overhangs?critical_angle_deg=${thresholdDeg}`, {
      method: "GET",
      headers: { "Accept": "application/json" },
      cache: "no-store",
    });
    if (!res.ok) throw new Error(`Failed to get overhang analysis: ${res.statusText}`);
    return res.json();
  }

  /**
   * Export transformed model
   */
  async exportModel(projectId: string, modelId: string, payload: ExportModelPayload): Promise<{ download_url: string; filename: string }> {
    const res = await fetch(`${this.baseUrl}/projects/${projectId}/models/${modelId}/export`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "Accept": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error(`Failed to export model: ${res.statusText}`);
    return res.json();
  }
}

export const apiClient = new ApiClient();
