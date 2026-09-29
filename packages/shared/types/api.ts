/**
 * Outlaw Forge - Shared API Contracts and Types
 * Strict source of truth across Frontend, Backend, 3D Engine, and QA.
 */

export type ProjectType =
  | 'Character'
  | 'Collectible Figure'
  | 'Mask'
  | 'Bust'
  | 'Statue'
  | 'Prop'
  | 'Plaque'
  | 'Mechanical Part'
  | 'Decorative Object'
  | 'Other';

export interface HealthStatusResponse {
  status: 'healthy' | 'degraded' | 'unhealthy';
  version: string;
  app_name: string;
  environment: string;
  services: {
    database: 'connected' | 'disconnected';
    mesh_engine: 'ready' | 'unavailable';
  };
  system: {
    platform: string;
    python_version: string;
  };
  timestamp: string;
}

export interface SourceFile {
  id: string;
  project_id: string;
  filename: string;
  file_format: 'stl' | 'obj' | 'glb' | 'gltf' | '3mf';
  file_size_bytes: number;
  storage_path: string;
  created_at: string;
}

export interface MeshTransform {
  position_mm: [number, number, number];
  rotation_deg: [number, number, number];
  scale_factors: [number, number, number];
  uniform_scale_percent: number;
}

export interface MeshBounds {
  min: [number, number, number];
  max: [number, number, number];
  dimensions_mm: [number, number, number];
}

export interface WorkingModel {
  id: string;
  project_id: string;
  source_file_id: string;
  filename: string;
  file_format: 'stl' | 'obj' | 'glb' | 'gltf';
  storage_path: string;
  units: 'mm';
  bounds: MeshBounds;
  triangle_count: number;
  vertex_count: number;
  surface_area_cm2: number;
  volume_cm3: number | null; // null if not watertight
  is_watertight: boolean;
  transform: MeshTransform;
  created_at: string;
  updated_at: string;
}

export interface PrinterProfile {
  id: string;
  manufacturer: string;
  model: string;
  build_width_mm: number;
  build_depth_mm: number;
  build_height_mm: number;
  nozzle_diameter_mm: number;
  notes?: string;
  created_at?: string;
}

export type OperationType = 'IMPORT' | 'SCALE' | 'ROTATE' | 'CENTER' | 'LAY_FLAT' | 'SLICE' | 'REPAIR' | 'EXPORT';

export interface OperationRecord {
  id: string;
  project_id: string;
  model_id?: string;
  operation_type: OperationType;
  timestamp: string;
  parameters: Record<string, any>;
  resulting_state_ref?: string;
  user_summary: string;
  success: boolean;
}

export interface Project {
  id: string;
  name: string;
  description: string;
  project_type: ProjectType;
  created_at: string;
  updated_at: string;
  thumbnail_url?: string | null;
  selected_printer_id?: string | null;
  units: 'mm';
  notes: string;
  source_files: SourceFile[];
  working_models: WorkingModel[];
  operations: OperationRecord[];
}

export interface ProjectCreatePayload {
  name: string;
  description?: string;
  project_type: ProjectType;
  selected_printer_id?: string;
  notes?: string;
}

export interface ProjectUpdatePayload {
  name?: string;
  description?: string;
  project_type?: ProjectType;
  selected_printer_id?: string | null;
  notes?: string;
}

export type FindingSeverity = 'INFO' | 'WARNING' | 'ERROR';

export interface PrintabilityFinding {
  severity: FindingSeverity;
  category: string;
  message: string;
  details?: Record<string, any>;
}

export interface PrintabilityAnalysis {
  model_id: string;
  printer_id: string;
  fits_build_volume: boolean;
  exceeded_dimensions_mm: {
    x: number;
    y: number;
    z: number;
  };
  findings: PrintabilityFinding[];
}

export interface ScaleModelPayload {
  uniform_scale_percent?: number;
  target_height_mm?: number;
  target_width_mm?: number;
  target_depth_mm?: number;
  preserve_aspect_ratio: boolean;
}

export interface RotateModelPayload {
  rotation_deg?: [number, number, number];
  rx_deg?: number;
  ry_deg?: number;
  rz_deg?: number;
  rx?: number;
  ry?: number;
  rz?: number;
  x?: number;
  y?: number;
  z?: number;
}

export interface PrinterProfileCreatePayload {
  manufacturer: string;
  model: string;
  build_width_mm: number;
  build_depth_mm: number;
  build_height_mm: number;
  nozzle_diameter_mm: number;
  notes?: string;
}

export interface OverhangAnalysis {
  model_id?: string;
  total_surface_area_cm2: number;
  overhang_surface_area_cm2: number;
  overhang_percentage: number;
  critical_threshold_deg: number;
  watertight: boolean;
}

export interface ExportModelPayload {
  format: 'stl' | 'obj' | 'glb';
  filename?: string;
}

export interface SliceModelPayload {
  plane_origin?: [number, number, number];
  plane_normal?: [number, number, number];
  cap_faces?: boolean;
  create_pegs?: boolean;
  peg_radius_mm?: number;
  peg_height_mm?: number;
  peg_clearance_mm?: number;
}

export interface SliceModelResult {
  top_model: WorkingModel;
  bottom_model: WorkingModel;
  cut_area_cm2: number;
  message: string;
}

export interface MeshRepairReport {
  holes_filled: number;
  degenerate_faces_removed: number;
  duplicate_vertices_welded: number;
  inverted_normals_fixed: boolean;
  is_watertight_before: boolean;
  is_watertight_after: boolean;
  triangle_count_before: number;
  triangle_count_after: number;
  volume_restored_cm3: number | null;
}

export interface RepairModelPayload {
  fill_holes?: boolean;
  fix_normals?: boolean;
  remove_degenerate?: boolean;
  weld_vertices?: boolean;
  weld_tolerance_mm?: number;
}

export interface RepairModelResult {
  repaired_model: WorkingModel;
  report: MeshRepairReport;
  message: string;
}
