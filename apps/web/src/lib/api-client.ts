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
  OverhangAnalysis,
  SliceModelPayload,
  SliceModelResult,
  RepairModelPayload,
  RepairModelResult,
  HollowModelPayload,
  HollowModelResult,
  ArrangeProjectPayload,
  ArrangeProjectResult,
  ExportProject3MFPayload,
  ExportProject3MFResponse,
  MaskFitAnalysis,
  MaskFitScalePayload,
  MagnetSocketPunchPayload,
  MagnetSocketPunchResult,
  StrapSlotPunchPayload,
  StrapSlotPunchResult,
  CenterOfMassAnalysis,
  PlinthGeneratePayload,
  PlinthGenerateResult,
  KeyPegPayload,
  KeyPegResult,
  ThinWallAnalysisPayload,
  ThinWallAnalysisResult,
  IslandAnalysisPayload,
  IslandAnalysisResult,
  CostEstimationPayload,
  CostEstimationResult,
  InfillGeneratePayload,
  InfillGenerateResult,
  RibReinforcePayload,
  RibReinforceResult,
} from "@shared/types/api";

declare global {
  interface Window {
    __OUTLAW_FORGE_API_URL__?: string;
  }
}

export class ApiClient {
  private customBaseUrl: string | null = null;

  constructor(baseUrl?: string) {
    if (baseUrl) {
      this.customBaseUrl = baseUrl.replace(/\/$/, "");
    }
  }

  public setBaseUrl(url: string): void {
    this.customBaseUrl = url.replace(/\/$/, "");
  }

  public getBaseUrl(): string {
    if (this.customBaseUrl) {
      return this.customBaseUrl;
    }
    if (typeof window !== "undefined") {
      if (window.__OUTLAW_FORGE_API_URL__) {
        return window.__OUTLAW_FORGE_API_URL__.replace(/\/$/, "");
      }
      try {
        const stored = localStorage.getItem("outlaw_forge_api_url");
        if (stored) {
          return stored.replace(/\/$/, "");
        }
      } catch {
        // Ignore localStorage access restrictions
      }
    }
    return (process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
  }

  public getDownloadUrl(relativePath: string): string {
    const base = this.getBaseUrl();
    const clean = relativePath.startsWith("/") ? relativePath : `/${relativePath}`;
    return `${base}${clean}`;
  }

  /**
   * Check backend health status
   */
  async getHealth(signal?: AbortSignal): Promise<HealthStatusResponse> {
    const res = await fetch(`${this.getBaseUrl()}/health`, {
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
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 15000);
    try {
      const res = await fetch(`${this.getBaseUrl()}/projects`, {
        method: "GET",
        headers: { "Accept": "application/json" },
        cache: "no-store",
        signal: controller.signal,
      });
      if (!res.ok) throw new Error(`Failed to list projects: ${res.statusText}`);
      return res.json();
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") {
        throw new Error("Loading projects timed out. Check that the API server is running.");
      }
      throw err;
    } finally {
      clearTimeout(timeoutId);
    }
  }

  /**
   * Create a new project
   */
  async createProject(payload: ProjectCreatePayload): Promise<Project> {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 15000);
    try {
      const res = await fetch(`${this.getBaseUrl()}/projects`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "Accept": "application/json" },
        body: JSON.stringify(payload),
        signal: controller.signal,
      });
      if (!res.ok) {
        const errorBody = await res.json().catch(() => null);
        throw new Error(errorBody?.detail || `Failed to create project: ${res.statusText}`);
      }
      return res.json();
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") {
        throw new Error("Project creation timed out. Check that the API server is running.");
      }
      throw err;
    } finally {
      clearTimeout(timeoutId);
    }
  }

  /**
   * Get project by ID
   */
  async getProject(id: string): Promise<Project> {
    const res = await fetch(`${this.getBaseUrl()}/projects/${id}`, {
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
    const res = await fetch(`${this.getBaseUrl()}/projects/${id}`, {
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
    const res = await fetch(`${this.getBaseUrl()}/projects/${id}`, {
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

    const res = await fetch(`${this.getBaseUrl()}/projects/${projectId}/models/import`, {
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
    const res = await fetch(`${this.getBaseUrl()}/printers`, {
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
    const res = await fetch(`${this.getBaseUrl()}/printers`, {
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
    const res = await fetch(`${this.getBaseUrl()}/projects/${projectId}/models/${modelId}/scale`, {
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
    const res = await fetch(`${this.getBaseUrl()}/projects/${projectId}/models/${modelId}/rotate`, {
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
    const res = await fetch(`${this.getBaseUrl()}/projects/${projectId}/models/${modelId}/center`, {
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
    const res = await fetch(`${this.getBaseUrl()}/projects/${projectId}/models/${modelId}/lay_flat`, {
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
    const res = await fetch(`${this.getBaseUrl()}/projects/${projectId}/models/${modelId}/overhangs?critical_angle_deg=${thresholdDeg}`, {
      method: "GET",
      headers: { "Accept": "application/json" },
      cache: "no-store",
    });
    if (!res.ok) throw new Error(`Failed to get overhang analysis: ${res.statusText}`);
    return res.json();
  }

  /**
   * Slice working model along planar cut
   */
  async sliceModel(projectId: string, modelId: string, payload: SliceModelPayload): Promise<SliceModelResult> {
    const res = await fetch(`${this.getBaseUrl()}/projects/${projectId}/models/${modelId}/slice`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "Accept": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || "Failed to slice model");
    }
    return res.json();
  }

  /**
   * Run automated mesh repair and healing
   */
  async repairModel(projectId: string, modelId: string, payload?: RepairModelPayload): Promise<RepairModelResult> {
    const res = await fetch(`${this.getBaseUrl()}/projects/${projectId}/models/${modelId}/repair`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "Accept": "application/json" },
      body: JSON.stringify(payload || {}),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || "Failed to repair mesh");
    }
    return res.json();
  }

  /**
   * Hollow out a solid 3D model with wall thickness and bottom drain holes
   */
  async hollowModel(projectId: string, modelId: string, payload?: HollowModelPayload): Promise<HollowModelResult> {
    const res = await fetch(`${this.getBaseUrl()}/projects/${projectId}/models/${modelId}/hollow`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "Accept": "application/json" },
      body: JSON.stringify(payload || {}),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || "Failed to hollow model");
    }
    return res.json();
  }

  /**
   * Duplicate a working model in the project
   */
  async duplicateModel(projectId: string, modelId: string): Promise<WorkingModel> {
    const res = await fetch(`${this.getBaseUrl()}/projects/${projectId}/models/${modelId}/duplicate`, {
      method: "POST",
      headers: { "Accept": "application/json" },
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || "Failed to duplicate model");
    }
    return res.json();
  }

  /**
   * Delete a working model from the project
   */
  async deleteModel(projectId: string, modelId: string): Promise<{ message: string; model_id: string }> {
    const res = await fetch(`${this.getBaseUrl()}/projects/${projectId}/models/${modelId}`, {
      method: "DELETE",
      headers: { "Accept": "application/json" },
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || "Failed to delete model");
    }
    return res.json();
  }

  /**
   * Auto-arrange all models collision-free on the build plate
   */
  async arrangeProject(projectId: string, payload?: ArrangeProjectPayload): Promise<ArrangeProjectResult> {
    const res = await fetch(`${this.getBaseUrl()}/projects/${projectId}/arrange`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "Accept": "application/json" },
      body: JSON.stringify(payload || {}),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || "Failed to arrange project models");
    }
    return res.json();
  }

  /**
   * Export transformed model
   */
  async exportModel(projectId: string, modelId: string, payload: ExportModelPayload): Promise<{ download_url: string; filename: string }> {
    const res = await fetch(`${this.getBaseUrl()}/projects/${projectId}/models/${modelId}/export`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "Accept": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error(`Failed to export model: ${res.statusText}`);
    return res.json();
  }

  /**
   * Export all project models into a 3MF archive for OrcaSlicer/Bambu Studio
   */
  async exportProject3MF(projectId: string, payload?: ExportProject3MFPayload): Promise<ExportProject3MFResponse> {
    const res = await fetch(`${this.getBaseUrl()}/projects/${projectId}/export_3mf`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "Accept": "application/json" },
      body: JSON.stringify(payload || {}),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || "Failed to export 3MF package");
    }
    return res.json();
  }

  /**
   * Generate procedural 3D calibration artifact
   */
  async generateCalibrationArtifact(
    projectId: string,
    payload: import("@shared/types/api").CalibrationGeneratePayload
  ): Promise<import("@shared/types/api").CalibrationGenerateResult> {
    const res = await fetch(`${this.getBaseUrl()}/projects/${projectId}/calibration/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "Accept": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || "Failed to generate calibration artifact");
    }
    return res.json();
  }

  /**
   * Auto-orient model for FDM support & height minimization
   */
  async autoOrient(
    projectId: string,
    modelId: string,
    payload?: import("@shared/types/api").AutoOrientPayload
  ): Promise<import("@shared/types/api").AutoOrientResult> {
    const res = await fetch(`${this.getBaseUrl()}/projects/${projectId}/models/${modelId}/auto_orient`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "Accept": "application/json" },
      body: JSON.stringify(payload || {}),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || "Failed to auto-orient model");
    }
    return res.json();
  }

  /**
   * Auto-arrange multi-model build plate nesting
   */
  async autoArrange(
    projectId: string,
    payload?: import("@shared/types/api").AutoArrangePayload
  ): Promise<import("@shared/types/api").AutoArrangeResult> {
    const res = await fetch(`${this.getBaseUrl()}/projects/${projectId}/auto_arrange`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "Accept": "application/json" },
      body: JSON.stringify(payload || {}),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || "Failed to auto-arrange models");
    }
    return res.json();
  }

  /**
   * Generate mouse-ear anti-warping corner discs
   */
  async generateMouseEars(
    projectId: string,
    modelId: string,
    payload?: import("@shared/types/api").MouseEarPayload
  ): Promise<import("@shared/types/api").MouseEarResult> {
    const res = await fetch(`${this.getBaseUrl()}/projects/${projectId}/models/${modelId}/mouse_ears`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "Accept": "application/json" },
      body: JSON.stringify(payload || {}),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || "Failed to generate mouse-ears");
    }
    return res.json();
  }

  /**
   * Compute adaptive variable layer height profile
   */
  async computeAdaptiveLayers(
    projectId: string,
    modelId: string,
    payload?: import("@shared/types/api").AdaptiveLayerPayload
  ): Promise<import("@shared/types/api").AdaptiveLayerResult> {
    const res = await fetch(`${this.getBaseUrl()}/projects/${projectId}/models/${modelId}/adaptive_layers`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "Accept": "application/json" },
      body: JSON.stringify(payload || {}),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || "Failed to compute adaptive layers");
    }
    return res.json();
  }

  /**
   * List filament material profiles
   */
  async listFilaments(projectId?: string): Promise<import("@shared/types/api").FilamentProfile[]> {
    const url = projectId ? `${this.getBaseUrl()}/projects/${projectId}/filaments` : `${this.getBaseUrl()}/filaments`;
    const res = await fetch(url, {
      method: "GET",
      headers: { "Accept": "application/json" },
      cache: "no-store",
    });
    if (!res.ok) throw new Error(`Failed to list filaments: ${res.statusText}`);
    return res.json();
  }

  /**
   * Calculate filament mass and print cost estimation
   */
  async estimateCost(
    projectId: string,
    modelId: string,
    payload?: CostEstimationPayload
  ): Promise<CostEstimationResult> {
    const res = await fetch(`${this.getBaseUrl()}/projects/${projectId}/models/${modelId}/estimate_cost`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "Accept": "application/json" },
      body: JSON.stringify(payload || {}),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || "Failed to estimate material cost");
    }
    return res.json();
  }
  /**
   * MaskSmith: Analyze wearable mask fit and anthropometric clearance
   */
  async analyzeMaskFit(projectId: string, modelId: string): Promise<MaskFitAnalysis> {
    const res = await fetch(`${this.getBaseUrl()}/projects/${projectId}/models/${modelId}/masksmith/fit-analyze`, {
      method: "POST",
      headers: { "Accept": "application/json" },
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || "Failed to analyze mask fit");
    }
    return res.json();
  }

  /**
   * MaskSmith: Auto-scale mask to match targeted human head preset
   */
  async autoScaleMask(projectId: string, modelId: string, payload: MaskFitScalePayload): Promise<WorkingModel> {
    const res = await fetch(`${this.getBaseUrl()}/projects/${projectId}/models/${modelId}/masksmith/auto-scale`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "Accept": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || "Failed to scale mask fit");
    }
    return res.json();
  }

  /**
   * MaskSmith: Punch neodymium magnet sockets into mask perimeter
   */
  async punchMagnetSockets(projectId: string, modelId: string, payload: MagnetSocketPunchPayload): Promise<MagnetSocketPunchResult> {
    const res = await fetch(`${this.getBaseUrl()}/projects/${projectId}/models/${modelId}/masksmith/punch-magnets`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "Accept": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || "Failed to punch magnet sockets");
    }
    return res.json();
  }

  /**
   * MaskSmith: Punch strap webbing slots and harness loops
   */
  async punchStrapSlots(projectId: string, modelId: string, payload: StrapSlotPunchPayload): Promise<StrapSlotPunchResult> {
    const res = await fetch(`${this.getBaseUrl()}/projects/${projectId}/models/${modelId}/masksmith/punch-strap-slots`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "Accept": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || "Failed to punch strap slots");
    }
    return res.json();
  }

  /**
   * FigureForge: Calculate center of mass and tipping angle stability
   */
  async analyzeFigureCOM(projectId: string, modelId: string): Promise<CenterOfMassAnalysis> {
    const res = await fetch(`${this.getBaseUrl()}/projects/${projectId}/models/${modelId}/figureforge/com-analyze`, {
      method: "POST",
      headers: { "Accept": "application/json" },
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || "Failed to analyze figure center of mass");
    }
    return res.json();
  }

  /**
   * FigureForge: Generate custom collectible display plinth
   */
  async generatePlinth(projectId: string, modelId: string, payload: PlinthGeneratePayload): Promise<PlinthGenerateResult> {
    const res = await fetch(`${this.getBaseUrl()}/projects/${projectId}/models/${modelId}/figureforge/generate-plinth`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "Accept": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || "Failed to generate plinth");
    }
    return res.json();
  }

  /**
   * FigureForge: Create mounting key-pegs on figure feet
   */
  async createKeyPegs(projectId: string, modelId: string, payload: KeyPegPayload): Promise<KeyPegResult> {
    const res = await fetch(`${this.getBaseUrl()}/projects/${projectId}/models/${modelId}/figureforge/create-key-pegs`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "Accept": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || "Failed to create key pegs");
    }
    return res.json();
  }

  /**
   * Phase 8: Analyze thin walls and fragile geometries
   */
  async analyzeThinWalls(projectId: string, modelId: string, payload?: ThinWallAnalysisPayload): Promise<ThinWallAnalysisResult> {
    const res = await fetch(`${this.getBaseUrl()}/projects/${projectId}/models/${modelId}/thin_walls`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "Accept": "application/json" },
      body: JSON.stringify(payload || {}),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || "Failed to analyze thin walls");
    }
    return res.json();
  }

  /**
   * Phase 8: Detect unsupported floating overhang islands
   */
  async analyzeIslands(projectId: string, modelId: string, payload?: IslandAnalysisPayload): Promise<IslandAnalysisResult> {
    const res = await fetch(`${this.getBaseUrl()}/projects/${projectId}/models/${modelId}/islands`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "Accept": "application/json" },
      body: JSON.stringify(payload || {}),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || "Failed to analyze floating islands");
    }
    return res.json();
  }

  /**
   * Phase 10: Generate procedural 3D infill lattice (Gyroid, Honeycomb, Rectilinear, Cubic)
   */
  async generateInfill(projectId: string, modelId: string, payload: InfillGeneratePayload): Promise<InfillGenerateResult> {
    const res = await fetch(`${this.getBaseUrl()}/projects/${projectId}/models/${modelId}/infill`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "Accept": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || "Failed to generate infill");
    }
    return res.json();
  }

  /**
   * Phase 10: Reinforce hollow walls with structural ribs and continuous drainage channels
   */
  async reinforceRibs(projectId: string, modelId: string, payload: RibReinforcePayload): Promise<RibReinforceResult> {
    const res = await fetch(`${this.getBaseUrl()}/projects/${projectId}/models/${modelId}/reinforce_ribs`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "Accept": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || "Failed to reinforce ribs");
    }
    return res.json();
  }
}

export const apiClient = new ApiClient();

