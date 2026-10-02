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

export type OperationType =
  | 'IMPORT'
  | 'SCALE'
  | 'ROTATE'
  | 'CENTER'
  | 'LAY_FLAT'
  | 'SLICE'
  | 'REPAIR'
  | 'EXPORT'
  | 'CALIBRATION_GENERATE'
  | 'AUTO_ORIENT'
  | 'AUTO_ARRANGE'
  | 'MOUSE_EAR_BRIM'
  | 'ADAPTIVE_LAYERS'
  | 'HOLLOW'
  | 'DUPLICATE'
  | 'DELETE'
  | 'ARRANGE'
  | 'EXPORT_3MF'
  | 'MASK_FIT_SCALE'
  | 'MASK_MAGNET_PUNCH'
  | 'MASK_STRAP_SLOT'
  | 'FIGURE_PLINTH_GENERATE'
  | 'FIGURE_KEY_PEG';

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

// --- OrcaSlicer Calibration Studio Types ---

export type CalibrationType =
  | 'temp_tower'
  | 'flow_rate'
  | 'retraction_tower'
  | 'tolerance_gauge'
  | 'overhang_benchmark'
  | 'calibration_cube_v2'
  | 'max_volumetric_speed';

export interface CalibrationGeneratePayload {
  calibration_type: CalibrationType;
  start_temp_c?: number;
  end_temp_c?: number;
  temp_step_c?: number;
  flow_rate_start_pct?: number;
  flow_rate_end_pct?: number;
  flow_rate_step_pct?: number;
  retraction_start_mm?: number;
  retraction_end_mm?: number;
  retraction_step_mm?: number;
  tolerance_min_mm?: number;
  tolerance_max_mm?: number;
  tolerance_step_mm?: number;
  cube_size_mm?: number;
  custom_name?: string;
}

export interface CalibrationGenerateResult {
  model: WorkingModel;
  calibration_type: CalibrationType;
  suggested_slicer_notes: string[];
  message: string;
}

// --- OrcaSlicer Auto-Orient Types ---

export interface AutoOrientPayload {
  overhang_weight?: number;
  height_weight?: number;
  bed_contact_weight?: number;
  critical_angle_deg?: number;
}

export interface AutoOrientResult {
  oriented_model: WorkingModel;
  optimal_rotation_deg: [number, number, number];
  original_overhang_area_cm2: number;
  optimized_overhang_area_cm2: number;
  reduction_percentage: number;
  message: string;
}

// --- OrcaSlicer Auto-Arrange / Multi-Model Bed Nesting Types ---

export interface AutoArrangePayload {
  spacing_mm?: number;
  bed_width_mm?: number;
  bed_depth_mm?: number;
  model_ids?: string[];
}

export interface ModelPlacement {
  model_id: string;
  x_offset_mm: number;
  y_offset_mm: number;
  rotation_deg: number;
  bounds: MeshBounds;
}

export interface AutoArrangeResult {
  arranged_models: WorkingModel[];
  placements: ModelPlacement[];
  fits_bed: boolean;
  message: string;
}

// --- OrcaSlicer Mouse-Ear Anti-Warping Brim Types ---

export interface MouseEarPayload {
  radius_mm?: number;
  thickness_mm?: number;
  corner_angle_threshold_deg?: number;
  auto_detect_corners?: boolean;
  custom_centers_mm?: [number, number][];
}

export interface MouseEarResult {
  modified_model: WorkingModel;
  ears_added_count: number;
  ear_positions_mm: [number, number][];
  message: string;
}

// --- OrcaSlicer Adaptive Layer Height Profiler Types ---

export interface AdaptiveLayerPayload {
  min_layer_height_mm?: number;
  max_layer_height_mm?: number;
  nominal_layer_height_mm?: number;
  step_size_mm?: number;
  smoothness_factor?: number;
}

export interface AdaptiveLayerCurvePoint {
  z_height_mm: number;
  layer_height_mm: number;
  slope_deg: number;
  layer_index: number;
}

export interface AdaptiveLayerResult {
  model_id: string;
  total_layers_nominal: number;
  total_layers_adaptive: number;
  estimated_time_nominal_min: number;
  estimated_time_adaptive_min: number;
  time_savings_pct: number;
  layer_curve: AdaptiveLayerCurvePoint[];
  message: string;
}

// --- OrcaSlicer Filament Library & Print Cost Types ---

export type FilamentMaterial =
  | 'PLA'
  | 'PETG'
  | 'ABS'
  | 'ASA'
  | 'TPU'
  | 'PC'
  | 'PA-CF'
  | 'PETG-CF'
  | 'Silk PLA'
  | 'Resin'
  | 'Custom';

export interface FilamentProfile {
  id: string;
  name: string;
  material: FilamentMaterial;
  density_g_cm3: number;
  nozzle_temp_c: number;
  bed_temp_c: number;
  cost_per_kg_usd: number;
  shrinkage_factor_pct: number;
  recommended_speed_mm_s: number;
  color_hex?: string;
  notes?: string;
}

export interface CostEstimationPayload {
  filament_id?: string;
  custom_density_g_cm3?: number;
  custom_cost_per_kg_usd?: number;
  infill_percentage?: number;
  wall_count?: number;
  top_bottom_layers?: number;
}

export interface CostEstimationResult {
  model_id: string;
  material_name: string;
  estimated_mass_grams: number;
  estimated_filament_length_meters: number;
  estimated_material_cost_usd: number;
  model_volume_cm3: number;
  effective_infill_volume_cm3: number;
  message: string;
}

// --- CAD Hollow and Auto-Arrange Types ---

export interface HollowModelPayload {
  wall_thickness_mm?: number;
  add_drain_holes?: boolean;
  drain_hole_radius_mm?: number;
  drain_hole_count?: number;
}

export interface HollowModelResult {
  hollowed_model: WorkingModel;
  wall_thickness_mm: number;
  drain_holes_added: number;
  volume_saved_cm3?: number | null;
  message: string;
}

export interface ArrangeItemPlacement {
  model_id: string;
  filename: string;
  position_mm: [number, number, number];
  rotation_deg?: [number, number, number];
}

export interface ArrangeProjectPayload {
  spacing_mm?: number;
  bed_margin_mm?: number;
  printer_id?: string;
}

export interface ArrangeProjectResult {
  project_id: string;
  models_arranged: number;
  placements: ArrangeItemPlacement[];
  all_fit: boolean;
  message: string;
}

export interface ExportProject3MFPayload {
  filename?: string;
  plate_name?: string;
  filament_id?: string;
  filament_preset?: string;
}

export interface ExportProject3MFResponse {
  project_id?: string;
  download_url: string;
  filename: string;
  storage_path?: string;
  models_exported?: number;
  models_included?: number;
  file_size_bytes: number;
  printer_model?: string;
  message: string;
}

// --- MaskSmith Studio Types ---

export type HeadSizePreset =
  | 'Adult Male (L/XL - 155mm)'
  | 'Adult Male (M - 150mm)'
  | 'Adult Female (M - 145mm)'
  | 'Adult Female (S - 140mm)'
  | 'Youth (130mm)'
  | 'Child (120mm)'
  | 'Custom';

export type MagnetPreset =
  | '6x3mm (D:6mm, H:3mm)'
  | '8x3mm (D:8mm, H:3mm)'
  | '10x3mm (D:10mm, H:3mm)'
  | '12x3mm (D:12mm, H:3mm)'
  | '6x2mm (D:6mm, H:2mm)'
  | '8x2mm (D:8mm, H:2mm)'
  | '10x2mm (D:10mm, H:2mm)'
  | 'Custom';

export type MagnetPlacementMode =
  | 'perimeter_4_corner'
  | 'perimeter_6_point'
  | 'split_seam_flange'
  | 'custom_points';

export type StrapPreset =
  | '15mm Elastic Band'
  | '20mm (3/4in) Webbing'
  | '25mm (1in) Tactical Webbing'
  | '38mm (1.5in) Heavy Duty Webbing'
  | 'Custom';

export interface MaskFitAnalysis {
  model_id: string;
  inner_width_mm: number;
  inner_height_mm: number;
  inner_depth_mm: number;
  recommended_preset: HeadSizePreset;
  recommended_scale_male_pct: number;
  recommended_scale_female_pct: number;
  recommended_scale_youth_pct: number;
  head_clearance_padding_mm: number;
  is_wearable_scale: boolean;
  notes: string;
}

export interface MaskFitScalePayload {
  target_preset?: HeadSizePreset;
  target_inner_width_mm?: number;
  padding_clearance_mm?: number;
  uniform_scale?: boolean;
}

export interface MagnetSocketPunchPayload {
  magnet_preset?: MagnetPreset;
  custom_diameter_mm?: number;
  custom_depth_mm?: number;
  clearance_tolerance_mm?: number;
  placement_mode?: MagnetPlacementMode;
  margin_inset_mm?: number;
  custom_points?: [number, number, number][];
}

export interface MagnetSocketPunchResult {
  model: WorkingModel;
  sockets_punched: number;
  magnet_diameter_mm: number;
  magnet_depth_mm: number;
  socket_positions: [number, number, number][];
  message: string;
}

export interface StrapSlotPunchPayload {
  strap_preset?: StrapPreset;
  slot_width_mm?: number;
  slot_thickness_mm?: number;
  placement?: 'temple_bilateral' | 'crown_and_temple_3point' | 'custom';
  inset_from_edge_mm?: number;
  custom_positions?: [number, number, number][];
}

export interface StrapSlotPunchResult {
  model: WorkingModel;
  slots_punched: number;
  slot_width_mm: number;
  slot_thickness_mm: number;
  slot_positions: [number, number, number][];
  message: string;
}

// --- FigureForge Studio Types ---

export type PlinthShape =
  | 'cylinder'
  | 'hexagon'
  | 'octagon'
  | 'stepped_round'
  | 'square_chamfered';

export interface CenterOfMassAnalysis {
  model_id: string;
  center_of_mass: [number, number, number];
  ground_projection: [number, number, number];
  base_centroid: [number, number, number];
  com_offset_from_center_mm: number;
  base_contact_radius_mm: number;
  tipping_angle_deg: number;
  stability_status: 'STABLE' | 'MARGINAL' | 'TOPPLE_RISK';
  is_freestanding: boolean;
  recommended_plinth_diameter_mm: number;
  notes: string;
}

export interface PlinthGeneratePayload {
  shape?: PlinthShape;
  diameter_mm?: number;
  height_mm?: number;
  chamfer_height_mm?: number;
  add_nameplate_recess?: boolean;
  add_figure_sockets?: boolean;
  socket_diameter_mm?: number;
  socket_depth_mm?: number;
  socket_spacing_mm?: number;
}

export interface PlinthGenerateResult {
  plinth_model: WorkingModel;
  shape: PlinthShape;
  diameter_mm: number;
  height_mm: number;
  has_sockets: boolean;
  message: string;
}

export interface KeyPegPayload {
  peg_shape?: 'cylinder' | 'square' | 'keyed_dowel';
  peg_diameter_mm?: number;
  peg_length_mm?: number;
  foot_offset_mm?: number;
  dual_feet_pegs?: boolean;
}

export interface KeyPegResult {
  model_with_pegs: WorkingModel;
  pegs_added_count: number;
  peg_diameter_mm: number;
  peg_length_mm: number;
  peg_positions: [number, number, number][];
  message: string;
}

// --- Phase 8: Advanced Printability, Diagnostics & Cost Estimator ---

export interface ThinRegion {
  center_mm: [number, number, number];
  thickness_mm: number;
  severity: 'warning' | 'critical';
  feature_id: number;
}

export interface ThinWallAnalysisPayload {
  min_wall_thickness_mm?: number;
  sample_points?: number;
}

export interface ThinWallAnalysisResult {
  model_id: string;
  thin_wall_count: number;
  min_detected_thickness_mm: number;
  thin_regions: ThinRegion[];
  total_thin_area_cm2: number;
  summary: string;
}

export interface FloatingIsland {
  point_mm: [number, number, number];
  layer_z_mm: number;
  area_mm2: number;
  severity: 'warning' | 'critical';
}

export interface IslandAnalysisPayload {
  min_island_area_mm2?: number;
  overhang_threshold_deg?: number;
}

export interface IslandAnalysisResult {
  model_id: string;
  island_count: number;
  islands: FloatingIsland[];
  summary: string;
}

export interface CostEstimationPayload {
  material_type?: FilamentMaterial;
  density_g_cm3?: number;
  spool_price_usd?: number;
  spool_weight_g?: number;
  infill_density_percent?: number;
  wall_thickness_mm?: number;
  top_bottom_thickness_mm?: number;
  print_speed_mm_s?: number;
  layer_height_mm?: number;
}

export interface CostEstimationResult {
  model_id: string;
  model_volume_cm3: number;
  shell_volume_cm3: number;
  infill_volume_cm3: number;
  total_printed_volume_cm3: number;
  mass_grams: number;
  filament_length_m: number;
  material_cost_usd: number;
  estimated_time_minutes: number;
  estimated_time_formatted: string;
  material_type: string;
}






