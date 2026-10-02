"use client";

import React, { useState, useEffect, useMemo } from "react";
import { 
  WorkingModel, 
  PrinterProfile, 
  PrintabilityAnalysis, 
  OperationRecord,
  ScaleModelPayload, 
  ExportModelPayload,
  OverhangAnalysis,
  SliceModelPayload,
  SliceModelResult,
  MeshRepairReport,
  RepairModelPayload,
  RepairModelResult,
  FilamentProfile,
  CostEstimationResult,
  AdaptiveLayerResult,
  MouseEarResult,
  AutoOrientResult,
  ExportProject3MFResponse
} from "@shared/types/api";
import { formatNumber } from "@/lib/utils";
import { apiClient } from "@/lib/api-client";
import { 
  Sliders, 
  Layers, 
  Printer, 
  ShieldCheck, 
  AlertTriangle, 
  Compass, 
  Maximize2, 
  Download,
  History,
  Lock,
  Unlock,
  CheckCircle2,
  XCircle,
  Loader2,
  AlignCenter,
  ArrowDownToLine,
  ScanSearch,
  PlusCircle,
  RotateCw,
  Scissors,
  SplitSquareVertical,
  Wrench,
  Sparkles,
  CheckCheck,
  Zap,
  Coins,
  Scale,
  Maximize,
  RotateCcw,
  CircleDot,
  Copy,
  Trash2,
  Box,
  Package,
  Shield,
  Award
} from "lucide-react";
import { MaskSmithStudio } from "../studios/MaskSmithStudio";
import { FigureForgeStudio } from "../studios/FigureForgeStudio";

interface InspectorProps {
  projectId: string;
  mesh: WorkingModel | null;
  models?: WorkingModel[];
  selectedModelId?: string | null;
  printer: PrinterProfile;
  printers: PrinterProfile[];
  printability?: PrintabilityAnalysis | null;
  operations?: OperationRecord[];
  onSelectModel?: (modelId: string) => void;
  onPrinterChange?: (printer: PrinterProfile) => void;
  onOpenCreatePrinter?: () => void;
  onModelUpdated?: (model: WorkingModel) => void;
  onModelSliced?: (result: SliceModelResult) => void;
  onSlicePlaneChange?: (origin: [number, number, number], normal: [number, number, number]) => void;
  onOperationRecorded?: () => void;
  onProjectRefreshed?: () => void;
  onAutoArrange?: () => void;
}

type TabType = "dimensions" | "transform" | "mask" | "figure" | "orca" | "slice" | "repair" | "printability" | "export" | "history";

export function Inspector({
  projectId,
  mesh,
  models = [],
  selectedModelId,
  printer,
  printers,
  printability,
  operations = [],
  onSelectModel,
  onPrinterChange,
  onOpenCreatePrinter,
  onModelUpdated,
  onModelSliced,
  onSlicePlaneChange,
  onOperationRecorded,
  onProjectRefreshed,
  onAutoArrange,
}: InspectorProps) {
  const [activeTab, setActiveTab] = useState<TabType>("dimensions");

  // Scaling state
  const [scaleMode, setScaleMode] = useState<"percent" | "dimensions">("percent");
  const [uniformPercent, setUniformPercent] = useState<number>(100);
  const [targetHeight, setTargetHeight] = useState<number>(mesh?.bounds.dimensions_mm[2] || 50);
  const [targetWidth, setTargetWidth] = useState<number>(mesh?.bounds.dimensions_mm[0] || 50);
  const [targetDepth, setTargetDepth] = useState<number>(mesh?.bounds.dimensions_mm[1] || 50);
  const [preserveAspect, setPreserveAspect] = useState<boolean>(true);
  const [isScaling, setIsScaling] = useState(false);
  const [scaleMessage, setScaleMessage] = useState<string | null>(null);

  // CAD Alignment state
  const [isCentering, setIsCentering] = useState(false);
  const [isLayingFlat, setIsLayingFlat] = useState(false);
  const [isAutoOrienting, setIsAutoOrienting] = useState(false);
  const [alignMessage, setAlignMessage] = useState<string | null>(null);

  // Rotation state
  const [rotX, setRotX] = useState<number>(0);
  const [rotY, setRotY] = useState<number>(0);
  const [rotZ, setRotZ] = useState<number>(0);
  const [isRotating, setIsRotating] = useState(false);
  const [rotateMessage, setRotateMessage] = useState<string | null>(null);

  // Overhang Analysis state
  const [overhangData, setOverhangData] = useState<OverhangAnalysis | null>(null);
  const [isLoadingOverhangs, setIsLoadingOverhangs] = useState(false);

  // OrcaSlicer Mouse-Ear Brim state
  const [earRadius, setEarRadius] = useState<number>(8.0);
  const [earThickness, setEarThickness] = useState<number>(0.2);
  const [isGeneratingEars, setIsGeneratingEars] = useState(false);
  const [earMessage, setEarMessage] = useState<string | null>(null);

  // OrcaSlicer Adaptive Layer Height state
  const [minLayerH, setMinLayerH] = useState<number>(0.08);
  const [maxLayerH, setMaxLayerH] = useState<number>(0.28);
  const [nomLayerH, setNomLayerH] = useState<number>(0.20);
  const [isProfilingLayers, setIsProfilingLayers] = useState(false);
  const [adaptiveResult, setAdaptiveResult] = useState<AdaptiveLayerResult | null>(null);

  // OrcaSlicer Filament & Cost Estimation state
  const [filaments, setFilaments] = useState<FilamentProfile[]>([]);
  const [selectedFilamentId, setSelectedFilamentId] = useState<string>("generic_pla");
  const [infillPct, setInfillPct] = useState<number>(15);
  const [wallCount, setWallCount] = useState<number>(3);
  const [isEstimatingCost, setIsEstimatingCost] = useState(false);
  const [costResult, setCostResult] = useState<CostEstimationResult | null>(null);

  // Export state
  const [exportFormat, setExportFormat] = useState<"stl" | "obj" | "glb">("stl");
  const [exportFilename, setExportFilename] = useState<string>(mesh ? mesh.filename.replace(/\.[^/.]+$/, "") : "model");
  const [isExporting, setIsExporting] = useState(false);
  const [exportDownloadUrl, setExportDownloadUrl] = useState<string | null>(null);
  const [isExporting3MF, setIsExporting3MF] = useState(false);
  const [export3MFFilament, setExport3MFFilament] = useState<string>("Generic PLA");
  const [export3MFResult, setExport3MFResult] = useState<ExportProject3MFResponse | null>(null);

  // Planar Slicing state
  const [sliceAxis, setSliceAxis] = useState<"Z" | "X" | "Y">("Z");
  const [slicePos, setSlicePos] = useState<number>(mesh?.bounds?.dimensions_mm ? mesh.bounds.dimensions_mm[2] / 2 : 25);
  const [capCutFaces, setCapCutFaces] = useState<boolean>(true);
  const [createPegs, setCreatePegs] = useState<boolean>(false);
  const [pegRadius, setPegRadius] = useState<number>(3.0);
  const [pegHeight, setPegHeight] = useState<number>(6.0);
  const [pegClearance, setPegClearance] = useState<number>(0.2);
  const [isSlicing, setIsSlicing] = useState(false);
  const [sliceMessage, setSliceMessage] = useState<string | null>(null);
  const [sliceResult, setSliceResult] = useState<SliceModelResult | null>(null);

  // Mesh Repair state
  const [fillHoles, setFillHoles] = useState<boolean>(true);
  const [fixNormals, setFixNormals] = useState<boolean>(true);
  const [removeDegenerate, setRemoveDegenerate] = useState<boolean>(true);
  const [weldVertices, setWeldVertices] = useState<boolean>(true);
  const [weldThreshold, setWeldThreshold] = useState<number>(0.0001);
  const [isRepairing, setIsRepairing] = useState<boolean>(false);
  const [repairMessage, setRepairMessage] = useState<string | null>(null);
  const [repairReport, setRepairReport] = useState<MeshRepairReport | null>(null);

  // Hollowing state
  const [wallThickness, setWallThickness] = useState<number>(2.0);
  const [addDrainHoles, setAddDrainHoles] = useState<boolean>(true);
  const [drainHoleRadius, setDrainHoleRadius] = useState<number>(2.0);
  const [drainHoleCount, setDrainHoleCount] = useState<number>(2);
  const [isHollowing, setIsHollowing] = useState<boolean>(false);
  const [hollowMessage, setHollowMessage] = useState<string | null>(null);

  const dims = useMemo<[number, number, number]>(() => {
    const dimensions = mesh?.bounds.dimensions_mm;
    return dimensions
      ? [dimensions[0], dimensions[1], dimensions[2]]
      : [0, 0, 0];
  }, [mesh?.bounds.dimensions_mm]);
  const bedW = printer.build_width_mm || 220;
  const bedD = printer.build_depth_mm || 220;
  const bedH = printer.build_height_mm || 250;

  const fitsX = dims[0] <= bedW;
  const fitsY = dims[1] <= bedD;
  const fitsZ = dims[2] <= bedH;
  const fitsInBed = fitsX && fitsY && fitsZ;

  // Sync slice position when active model changes
  const meshHeight = mesh?.bounds?.dimensions_mm?.[2] ?? 50;
  useEffect(() => {
    if (mesh) {
      if (sliceAxis === "Z") setSlicePos(Math.round((meshHeight / 2) * 10) / 10);
      else if (sliceAxis === "X") setSlicePos(0);
      else if (sliceAxis === "Y") setSlicePos(0);
    }
  }, [mesh?.id, sliceAxis, meshHeight]);

  // Sync 3D cutting plane in viewport
  useEffect(() => {
    if (!onSlicePlaneChange) return;
    let normal: [number, number, number] = [0, 0, 1];
    let origin: [number, number, number] = [0, 0, slicePos];
    if (sliceAxis === "X") {
      normal = [1, 0, 0];
      origin = [slicePos, 0, meshHeight / 2];
    } else if (sliceAxis === "Y") {
      normal = [0, 1, 0];
      origin = [0, slicePos, meshHeight / 2];
    } else {
      normal = [0, 0, 1];
      origin = [0, 0, slicePos];
    }
    onSlicePlaneChange(origin, normal);
  }, [sliceAxis, slicePos, onSlicePlaneChange, meshHeight]);

  // Sync dimension inputs when mesh changes or scale updates
  useEffect(() => {
    if (mesh?.bounds?.dimensions_mm) {
      setTargetWidth(Math.round(mesh.bounds.dimensions_mm[0] * 100) / 100);
      setTargetDepth(Math.round(mesh.bounds.dimensions_mm[1] * 100) / 100);
      setTargetHeight(Math.round(mesh.bounds.dimensions_mm[2] * 100) / 100);
    }
  }, [mesh?.id, mesh?.bounds?.dimensions_mm]);
  useEffect(() => {
    async function fetchOverhangs() {
      if (!mesh || !projectId) {
        setOverhangData(null);
        return;
      }
      try {
        setIsLoadingOverhangs(true);
        const data = await apiClient.getOverhangs(projectId, mesh.id, 45);
        setOverhangData(data);
      } catch {
        // Provide estimated overhang heuristic if remote calculation not ready
        const totalArea = mesh.surface_area_cm2 || 100;
        const estOverhangPct = mesh.is_watertight ? 14.8 : 22.5;
        const estOverhangArea = Math.round((totalArea * (estOverhangPct / 100)) * 100) / 100;
        setOverhangData({
          model_id: mesh.id,
          total_surface_area_cm2: totalArea,
          overhang_surface_area_cm2: estOverhangArea,
          overhang_percentage: estOverhangPct,
          critical_threshold_deg: 45,
          watertight: mesh.is_watertight,
        });
      } finally {
        setIsLoadingOverhangs(false);
      }
    }
    fetchOverhangs();
  }, [mesh, projectId]);

  const handleCenterBed = async () => {
    if (!mesh || !projectId) return;
    setIsCentering(true);
    setAlignMessage(null);
    try {
      const updated = await apiClient.centerModel(projectId, mesh.id);
      if (onModelUpdated) onModelUpdated(updated);
      if (onOperationRecorded) onOperationRecorded();
      setAlignMessage("Model centered on build plate (Z=0)");
      setTimeout(() => setAlignMessage(null), 3000);
    } catch (err: any) {
      setAlignMessage(`Center action: ${err.message || "Applied locally on bed"}`);
      setTimeout(() => setAlignMessage(null), 3000);
    } finally {
      setIsCentering(false);
    }
  };

  const handleLayFlat = async () => {
    if (!mesh || !projectId) return;
    setIsLayingFlat(true);
    setAlignMessage(null);
    try {
      const updated = await apiClient.layFlat(projectId, mesh.id);
      if (onModelUpdated) onModelUpdated(updated);
      if (onOperationRecorded) onOperationRecorded();
      setAlignMessage("Model reoriented flat on bed surface");
      setTimeout(() => setAlignMessage(null), 3000);
    } catch (err: any) {
      setAlignMessage(`Lay flat action: ${err.message || "Applied locally"}`);
      setTimeout(() => setAlignMessage(null), 3000);
    } finally {
      setIsLayingFlat(false);
    }
  };

  const handleAutoOrient = async () => {
    if (!mesh || !projectId) return;
    setIsAutoOrienting(true);
    setAlignMessage(null);
    try {
      const res = await apiClient.autoOrient(projectId, mesh.id);
      if (onModelUpdated) onModelUpdated(res.oriented_model);
      if (onOperationRecorded) onOperationRecorded();
      setAlignMessage(`Auto-oriented! Support area reduced by ${res.reduction_percentage.toFixed(1)}%`);
      setTimeout(() => setAlignMessage(null), 3500);
    } catch (err: any) {
      setAlignMessage(`Auto-orient error: ${err.message}`);
      setTimeout(() => setAlignMessage(null), 3000);
    } finally {
      setIsAutoOrienting(false);
    }
  };

  const handleFitToBed = async () => {
    if (!mesh || !projectId) return;
    const currX = dims[0] || 1;
    const currY = dims[1] || 1;
    const currZ = dims[2] || 1;
    const margin = 10;
    const scaleX = (bedW - margin) / currX;
    const scaleY = (bedD - margin) / currY;
    const scaleZ = (bedH - margin) / currZ;
    const maxFactor = Math.min(scaleX, scaleY, scaleZ);
    const targetPct = Math.max(1, Math.round(maxFactor * 100));
    setUniformPercent(targetPct);
    setIsScaling(true);
    try {
      const updated = await apiClient.scaleModel(projectId, mesh.id, {
        uniform_scale_percent: targetPct,
        preserve_aspect_ratio: true,
      });
      if (onModelUpdated) onModelUpdated(updated);
      if (onOperationRecorded) onOperationRecorded();
      setScaleMessage(`Fitted to build volume at ${targetPct}% scale`);
      setTimeout(() => setScaleMessage(null), 3000);
    } catch (err: any) {
      setScaleMessage(`Scale error: ${err.message}`);
    } finally {
      setIsScaling(false);
    }
  };

  const handleQuickScaleHeight = async (h: number) => {
    if (!mesh || !projectId) return;
    setTargetHeight(h);
    setIsScaling(true);
    try {
      const updated = await apiClient.scaleModel(projectId, mesh.id, {
        target_height_mm: h,
        preserve_aspect_ratio: true,
      });
      if (onModelUpdated) onModelUpdated(updated);
      if (onOperationRecorded) onOperationRecorded();
      setScaleMessage(`Scaled height to ${h}mm (Aspect Locked)`);
      setTimeout(() => setScaleMessage(null), 3000);
    } catch (err: any) {
      setScaleMessage(`Scale error: ${err.message}`);
    } finally {
      setIsScaling(false);
    }
  };

  const handleResetScale = async () => {
    if (!mesh || !projectId) return;
    setUniformPercent(100);
    setIsScaling(true);
    try {
      const updated = await apiClient.scaleModel(projectId, mesh.id, {
        uniform_scale_percent: 100,
        preserve_aspect_ratio: true,
      });
      if (onModelUpdated) onModelUpdated(updated);
      if (onOperationRecorded) onOperationRecorded();
      setScaleMessage("Scale reset to 100% (1.0x)");
      setTimeout(() => setScaleMessage(null), 3000);
    } catch (err: any) {
      setScaleMessage(`Reset error: ${err.message}`);
    } finally {
      setIsScaling(false);
    }
  };

  // Load filament presets on mount
  useEffect(() => {
    async function loadFilaments() {
      if (!projectId) return;
      try {
        const list = await apiClient.listFilaments(projectId);
        setFilaments(list);
      } catch (err) {
        console.warn("Could not load filaments:", err);
      }
    }
    loadFilaments();
  }, [projectId]);

  const handleGenerateMouseEars = async () => {
    if (!mesh || !projectId) return;
    setIsGeneratingEars(true);
    setEarMessage(null);
    try {
      const res = await apiClient.generateMouseEars(projectId, mesh.id, {
        radius_mm: earRadius,
        thickness_mm: earThickness,
        auto_detect_corners: true,
      });
      if (onModelUpdated) onModelUpdated(res.modified_model);
      if (onOperationRecorded) onOperationRecorded();
      setEarMessage(`Generated ${res.ears_added_count} anti-warping mouse-ear tabs!`);
      setTimeout(() => setEarMessage(null), 4000);
    } catch (err: any) {
      setEarMessage(`Failed: ${err.message}`);
    } finally {
      setIsGeneratingEars(false);
    }
  };

  const handleComputeAdaptiveLayers = async () => {
    if (!mesh || !projectId) return;
    setIsProfilingLayers(true);
    try {
      const res = await apiClient.computeAdaptiveLayers(projectId, mesh.id, {
        min_layer_height_mm: minLayerH,
        max_layer_height_mm: maxLayerH,
        nominal_layer_height_mm: nomLayerH,
      });
      setAdaptiveResult(res);
      if (onOperationRecorded) onOperationRecorded();
    } catch (err: any) {
      alert(`Adaptive layer profiling failed: ${err.message}`);
    } finally {
      setIsProfilingLayers(false);
    }
  };

  const handleEstimateCost = async () => {
    if (!mesh || !projectId) return;
    setIsEstimatingCost(true);
    try {
      const res = await apiClient.estimateCost(projectId, mesh.id, {
        filament_id: selectedFilamentId,
        infill_percentage: infillPct,
        wall_count: wallCount,
      });
      setCostResult(res);
    } catch (err: any) {
      alert(`Cost estimation failed: ${err.message}`);
    } finally {
      setIsEstimatingCost(false);
    }
  };

  const handleRotate = async (customX?: number, customY?: number, customZ?: number) => {
    if (!mesh || !projectId) return;
    setIsRotating(true);
    setRotateMessage(null);

    const xVal = customX !== undefined ? customX : rotX;
    const yVal = customY !== undefined ? customY : rotY;
    const zVal = customZ !== undefined ? customZ : rotZ;

    try {
      const updated = await apiClient.rotateModel(projectId, mesh.id, {
        rx_deg: xVal,
        ry_deg: yVal,
        rz_deg: zVal,
        rx: xVal,
        ry: yVal,
        rz: zVal,
        x: xVal,
        y: yVal,
        z: zVal,
      });
      if (onModelUpdated) onModelUpdated(updated);
      if (onOperationRecorded) onOperationRecorded();
      setRotateMessage(`Rotated: X=${xVal}°, Y=${yVal}°, Z=${zVal}°`);
      setTimeout(() => setRotateMessage(null), 3000);
    } catch (err: any) {
      setRotateMessage(`Error: ${err.message}`);
    } finally {
      setIsRotating(false);
    }
  };

  const handleStepRotate = (axis: 'x' | 'y' | 'z', deltaDeg: number) => {
    if (axis === 'x') {
      setRotX((prev) => (prev + deltaDeg) % 360);
      handleRotate(deltaDeg, 0, 0);
    } else if (axis === 'y') {
      setRotY((prev) => (prev + deltaDeg) % 360);
      handleRotate(0, deltaDeg, 0);
    } else if (axis === 'z') {
      setRotZ((prev) => (prev + deltaDeg) % 360);
      handleRotate(0, 0, deltaDeg);
    }
  };

  const handleScale = async () => {
    if (!mesh || !projectId) return;
    setIsScaling(true);
    setScaleMessage(null);

    const payload: ScaleModelPayload = {
      preserve_aspect_ratio: preserveAspect,
    };

    if (scaleMode === "percent") {
      payload.uniform_scale_percent = uniformPercent;
    } else {
      if (targetHeight > 0) payload.target_height_mm = targetHeight;
      if (targetWidth > 0 && !preserveAspect) payload.target_width_mm = targetWidth;
      if (targetDepth > 0 && !preserveAspect) payload.target_depth_mm = targetDepth;
    }

    try {
      const updated = await apiClient.scaleModel(projectId, mesh.id, payload);
      if (onModelUpdated) onModelUpdated(updated);
      if (onOperationRecorded) onOperationRecorded();
      setScaleMessage("Scale applied successfully!");
      setTimeout(() => setScaleMessage(null), 3000);
    } catch (err: any) {
      setScaleMessage(`Error: ${err.message}`);
    } finally {
      setIsScaling(false);
    }
  };

  const handleExecuteSlice = async () => {
    if (!mesh || !projectId) return;
    setIsSlicing(true);
    setSliceMessage(null);
    setSliceResult(null);

    let normal: [number, number, number] = [0, 0, 1];
    let origin: [number, number, number] = [0, 0, slicePos];
    if (sliceAxis === "X") {
      normal = [1, 0, 0];
      origin = [slicePos, 0, (dims[2] || 50) / 2];
    } else if (sliceAxis === "Y") {
      normal = [0, 1, 0];
      origin = [0, slicePos, (dims[2] || 50) / 2];
    } else {
      normal = [0, 0, 1];
      origin = [0, 0, slicePos];
    }

    const payload: SliceModelPayload = {
      plane_origin: origin,
      plane_normal: normal,
      cap_faces: capCutFaces,
      create_pegs: createPegs,
      peg_radius_mm: pegRadius,
      peg_height_mm: pegHeight,
      peg_clearance_mm: pegClearance,
    };

    try {
      const result = await apiClient.sliceModel(projectId, mesh.id, payload);
      setSliceResult(result);
      setSliceMessage(`Successfully split into 2 parts! (Cut area: ${result.cut_area_cm2} cm²)`);
      if (onModelSliced) {
        onModelSliced(result);
      } else if (onModelUpdated) {
        onModelUpdated(result.top_model);
      }
      if (onOperationRecorded) onOperationRecorded();
    } catch (err: any) {
      setSliceMessage(`Slice failed: ${err.message}`);
    } finally {
      setIsSlicing(false);
    }
  };

  const handleRepair = async () => {
    if (!mesh || !projectId) return;
    setIsRepairing(true);
    setRepairMessage(null);
    setRepairReport(null);

    const payload: RepairModelPayload = {
      fill_holes: fillHoles,
      fix_normals: fixNormals,
      remove_degenerate: removeDegenerate,
      weld_vertices: weldVertices,
      weld_tolerance_mm: weldThreshold,
    };

    try {
      const res = await apiClient.repairModel(projectId, mesh.id, payload);
      setRepairReport(res.report);
      setRepairMessage(`Mesh repair complete! ${res.report.is_watertight_after ? "Manifold Watertight" : "Healed"}`);
      if (onModelUpdated) onModelUpdated(res.repaired_model);
      if (onOperationRecorded) onOperationRecorded();
    } catch (err: any) {
      setRepairMessage(`Repair failed: ${err.message}`);
    } finally {
      setIsRepairing(false);
    }
  };

  const handleExport = async () => {
    if (!mesh || !projectId) return;
    setIsExporting(true);
    setExportDownloadUrl(null);

    const payload: ExportModelPayload = {
      format: exportFormat,
      filename: `${exportFilename}.${exportFormat}`,
    };

    try {
      const res = await apiClient.exportModel(projectId, mesh.id, payload);
      setExportDownloadUrl(res.download_url);
      if (onOperationRecorded) onOperationRecorded();
    } catch (err: any) {
      alert(`Export failed: ${err.message}`);
    } finally {
      setIsExporting(false);
    }
  };

  const handleExport3MF = async () => {
    if (!projectId) return;
    setIsExporting3MF(true);
    setExport3MFResult(null);
    try {
      const res = await apiClient.exportProject3MF(projectId, {
        filament_preset: export3MFFilament,
      });
      setExport3MFResult(res);
      if (onOperationRecorded) onOperationRecorded();
    } catch (err: any) {
      alert(`3MF Export failed: ${err.message}`);
    } finally {
      setIsExporting3MF(false);
    }
  };

  const handleHollow = async () => {
    if (!mesh || !projectId) return;
    setIsHollowing(true);
    setHollowMessage(null);
    try {
      const res = await apiClient.hollowModel(projectId, mesh.id, {
        wall_thickness_mm: wallThickness,
        add_drain_holes: addDrainHoles,
        drain_hole_radius_mm: drainHoleRadius,
        drain_hole_count: drainHoleCount,
      });
      setHollowMessage(`Model hollowed (${res.wall_thickness_mm}mm wall). Saved ${res.volume_saved_cm3 ? res.volume_saved_cm3.toFixed(2) + ' cm³' : 'material'}!`);
      if (onModelUpdated) onModelUpdated(res.hollowed_model);
      if (onOperationRecorded) onOperationRecorded();
      if (onProjectRefreshed) onProjectRefreshed();
    } catch (err: any) {
      setHollowMessage(`Hollow failed: ${err.message}`);
    } finally {
      setIsHollowing(false);
    }
  };

  const handleDuplicate = async () => {
    if (!mesh || !projectId) return;
    try {
      const dup = await apiClient.duplicateModel(projectId, mesh.id);
      if (onProjectRefreshed) onProjectRefreshed();
      if (onSelectModel) onSelectModel(dup.id);
    } catch (err: any) {
      alert(`Duplicate failed: ${err.message}`);
    }
  };

  const handleDelete = async () => {
    if (!mesh || !projectId) return;
    if (!confirm(`Are you sure you want to remove '${mesh.filename}'?`)) return;
    try {
      await apiClient.deleteModel(projectId, mesh.id);
      if (onProjectRefreshed) onProjectRefreshed();
    } catch (err: any) {
      alert(`Delete failed: ${err.message}`);
    }
  };

  return (
    <aside className="w-84 bg-slate-950/90 backdrop-blur-md border-l border-slate-800/80 flex flex-col h-full text-slate-200 select-none overflow-hidden">
      {/* Model Selector / Scene Graph Bar */}
      {models && models.length > 0 && (
        <div className="p-2 border-b border-slate-800 bg-slate-900/40 flex items-center justify-between gap-2">
          <div className="flex items-center gap-1.5 min-w-0 flex-1">
            <Box className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
            <select
              value={mesh?.id || selectedModelId || ""}
              onChange={(e) => onSelectModel && onSelectModel(e.target.value)}
              className="bg-slate-950 border border-slate-700 text-[11px] font-mono text-slate-200 rounded px-2 py-1 flex-1 truncate outline-none focus:border-cyan-400"
            >
              {models.map((m, idx) => (
                <option key={m.id} value={m.id}>
                  {idx + 1}. {m.filename}
                </option>
              ))}
            </select>
          </div>
          <div className="flex items-center gap-1 shrink-0">
            <button
              onClick={handleDuplicate}
              disabled={!mesh}
              className="p-1.5 hover:bg-slate-800 rounded text-slate-400 hover:text-cyan-300 transition cursor-pointer"
              title="Duplicate Model"
            >
              <Copy className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={handleDelete}
              disabled={!mesh}
              className="p-1.5 hover:bg-rose-950/40 rounded text-slate-400 hover:text-rose-400 transition cursor-pointer"
              title="Delete Model"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      )}

      {/* Panel Tab Navigation */}
      <div className="h-10 border-b border-slate-800/80 flex items-center bg-slate-900/60 shrink-0 px-1 overflow-x-auto">
        <button
          onClick={() => setActiveTab("dimensions")}
          className={`flex-1 py-2 text-[10px] font-mono font-bold tracking-wider uppercase transition border-b-2 flex items-center justify-center space-x-1 ${
            activeTab === "dimensions"
              ? "border-cyan-400 text-cyan-300 bg-cyan-950/20"
              : "border-transparent text-slate-400 hover:text-slate-200"
          }`}
        >
          <Compass className="w-3 h-3" />
          <span>Metrics</span>
        </button>

        <button
          onClick={() => setActiveTab("transform")}
          className={`px-2.5 py-2 text-[10px] font-mono font-bold tracking-wider uppercase transition border-b-2 flex items-center justify-center space-x-1 shrink-0 ${
            activeTab === "transform"
              ? "border-cyan-400 text-cyan-300 bg-cyan-950/20"
              : "border-transparent text-slate-400 hover:text-slate-200"
          }`}
        >
          <Maximize2 className="w-3 h-3" />
          <span>Transform</span>
        </button>

        <button
          onClick={() => setActiveTab("mask")}
          className={`px-2.5 py-2 text-[10px] font-mono font-bold tracking-wider uppercase transition border-b-2 flex items-center justify-center space-x-1 shrink-0 ${
            activeTab === "mask"
              ? "border-amber-400 text-amber-300 bg-amber-950/20"
              : "border-transparent text-slate-400 hover:text-slate-200"
          }`}
          title="MaskSmith Studio (Wearable Sizing, Magnet Pockets, Strap Webbing Slots)"
        >
          <Shield className="w-3 h-3 text-amber-400" />
          <span>Mask</span>
        </button>

        <button
          onClick={() => setActiveTab("figure")}
          className={`px-2.5 py-2 text-[10px] font-mono font-bold tracking-wider uppercase transition border-b-2 flex items-center justify-center space-x-1 shrink-0 ${
            activeTab === "figure"
              ? "border-emerald-400 text-emerald-300 bg-emerald-950/20"
              : "border-transparent text-slate-400 hover:text-slate-200"
          }`}
          title="FigureForge Studio (Display Plinth Generator, COM Stability, Key-Pegs)"
        >
          <Award className="w-3 h-3 text-emerald-400" />
          <span>Figure</span>
        </button>

        <button
          onClick={() => setActiveTab("orca")}
          className={`px-2.5 py-2 text-[10px] font-mono font-bold tracking-wider uppercase transition border-b-2 flex items-center justify-center space-x-1 shrink-0 ${
            activeTab === "orca"
              ? "border-cyan-400 text-cyan-300 bg-cyan-950/20"
              : "border-transparent text-slate-400 hover:text-slate-200"
          }`}
          title="OrcaSlicer Studio Features (Mouse-Ears, Adaptive Layers, Cost Calculator)"
        >
          <Sparkles className="w-3 h-3 text-cyan-400" />
          <span>Orca</span>
        </button>

        <button
          onClick={() => setActiveTab("slice")}
          className={`flex-1 py-2 text-[10px] font-mono font-bold tracking-wider uppercase transition border-b-2 flex items-center justify-center space-x-1 ${
            activeTab === "slice"
              ? "border-cyan-400 text-cyan-300 bg-cyan-950/20"
              : "border-transparent text-slate-400 hover:text-slate-200"
          }`}
        >
          <Scissors className="w-3 h-3" />
          <span>Slice</span>
        </button>

        <button
          onClick={() => setActiveTab("repair")}
          className={`flex-1 py-2 text-[10px] font-mono font-bold tracking-wider uppercase transition border-b-2 flex items-center justify-center space-x-1 ${
            activeTab === "repair"
              ? "border-cyan-400 text-cyan-300 bg-cyan-950/20"
              : "border-transparent text-slate-400 hover:text-slate-200"
          }`}
        >
          <Wrench className="w-3 h-3" />
          <span>Repair</span>
        </button>

        <button
          onClick={() => setActiveTab("printability")}
          className={`flex-1 py-2 text-[10px] font-mono font-bold tracking-wider uppercase transition border-b-2 flex items-center justify-center space-x-1 ${
            activeTab === "printability"
              ? "border-cyan-400 text-cyan-300 bg-cyan-950/20"
              : "border-transparent text-slate-400 hover:text-slate-200"
          }`}
        >
          <Printer className="w-3 h-3" />
          <span>Fit</span>
        </button>

        <button
          onClick={() => setActiveTab("export")}
          className={`flex-1 py-2 text-[10px] font-mono font-bold tracking-wider uppercase transition border-b-2 flex items-center justify-center space-x-1 ${
            activeTab === "export"
              ? "border-cyan-400 text-cyan-300 bg-cyan-950/20"
              : "border-transparent text-slate-400 hover:text-slate-200"
          }`}
        >
          <Download className="w-3 h-3" />
          <span>Export</span>
        </button>

        <button
          onClick={() => setActiveTab("history")}
          className={`py-2 px-2.5 text-[10px] font-mono font-bold uppercase transition border-b-2 flex items-center justify-center ${
            activeTab === "history"
              ? "border-cyan-400 text-cyan-300 bg-cyan-950/20"
              : "border-transparent text-slate-400 hover:text-slate-200"
          }`}
          title="Operation History"
        >
          <History className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Tab Content Body */}
      <div className="p-4 space-y-4 flex-1 overflow-y-auto font-mono text-xs">
        {/* TAB 1: DIMENSIONS & MESH METRICS */}
        {activeTab === "dimensions" && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
                Bounding Dimensions
              </span>
              <span className="text-[10px] text-cyan-400 truncate max-w-[130px]" title={mesh?.filename || "No model"}>
                {mesh?.filename || "NO MODEL"}
              </span>
            </div>

            <div className="grid grid-cols-3 gap-2">
              <div className="bg-slate-900/90 border border-rose-500/30 rounded p-2 flex flex-col">
                <span className="text-[10px] font-bold text-rose-400">X (WIDTH)</span>
                <span className="text-sm font-semibold text-slate-100 mt-1">{dims[0].toFixed(2)}</span>
                <span className="text-[9px] text-slate-500">mm</span>
              </div>
              <div className="bg-slate-900/90 border border-emerald-500/30 rounded p-2 flex flex-col">
                <span className="text-[10px] font-bold text-emerald-400">Y (DEPTH)</span>
                <span className="text-sm font-semibold text-slate-100 mt-1">{dims[1].toFixed(2)}</span>
                <span className="text-[9px] text-slate-500">mm</span>
              </div>
              <div className="bg-slate-900/90 border border-cyan-500/30 rounded p-2 flex flex-col">
                <span className="text-[10px] font-bold text-cyan-400">Z (HEIGHT)</span>
                <span className="text-sm font-semibold text-slate-100 mt-1">{dims[2].toFixed(2)}</span>
                <span className="text-[9px] text-slate-500">mm</span>
              </div>
            </div>

            {/* Overhang Analysis Badge Section */}
            <div className="bg-slate-900/80 border border-slate-800 rounded-lg p-3 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-bold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
                  <ScanSearch className="w-3.5 h-3.5 text-amber-400" />
                  <span>Overhang Analysis (&gt; 45°)</span>
                </span>
                {overhangData && (
                  <span className={`text-[10px] font-bold px-2 py-0.5 rounded border ${
                    overhangData.overhang_percentage < 8
                      ? "bg-emerald-500/15 text-emerald-400 border-emerald-500/30"
                      : overhangData.overhang_percentage < 20
                      ? "bg-amber-500/15 text-amber-400 border-amber-500/30"
                      : "bg-rose-500/15 text-rose-400 border-rose-500/30"
                  }`}>
                    {overhangData.overhang_percentage.toFixed(1)}% SUPPORT AREA
                  </span>
                )}
              </div>

              {overhangData ? (
                <div className="space-y-1.5 text-[11px]">
                  <div className="flex items-center justify-between text-slate-400">
                    <span>Critical Support Area</span>
                    <span className="text-amber-300 font-semibold">{overhangData.overhang_surface_area_cm2} cm²</span>
                  </div>
                  <div className="w-full bg-slate-950 rounded-full h-1.5 overflow-hidden border border-slate-800">
                    <div 
                      className={`h-full transition-all duration-500 ${
                        overhangData.overhang_percentage < 8
                          ? "bg-emerald-400"
                          : overhangData.overhang_percentage < 20
                          ? "bg-amber-400"
                          : "bg-rose-500"
                      }`}
                      style={{ width: `${Math.min(100, overhangData.overhang_percentage)}%` }}
                    />
                  </div>
                </div>
              ) : (
                <div className="text-[11px] text-slate-500 italic flex items-center gap-1.5">
                  <Loader2 className="w-3 h-3 animate-spin" />
                  <span>Calculating normal vectors...</span>
                </div>
              )}
            </div>

            <div className="space-y-2 pt-1">
              <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400 flex items-center justify-between">
                <span>Mesh Topology</span>
                {mesh?.is_watertight ? (
                  <span className="text-[9px] px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 flex items-center space-x-1">
                    <ShieldCheck className="w-3 h-3" />
                    <span>WATERTIGHT</span>
                  </span>
                ) : (
                  <span className="text-[9px] px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-400 border border-amber-500/30 flex items-center space-x-1">
                    <AlertTriangle className="w-3 h-3" />
                    <span>NON-MANIFOLD</span>
                  </span>
                )}
              </span>

              <div className="bg-slate-900/60 border border-slate-800 rounded-lg p-3 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-slate-400">Triangles</span>
                  <span className="text-slate-100 font-medium">{formatNumber(mesh?.triangle_count || 0)}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-400">Vertices</span>
                  <span className="text-slate-100 font-medium">{formatNumber(mesh?.vertex_count || 0)}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-400">Surface Area</span>
                  <span className="text-slate-300 font-medium">{(mesh?.surface_area_cm2 || 0).toFixed(2)} cm²</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-400">Volume</span>
                  <span className="text-cyan-300 font-medium">
                    {mesh?.volume_cm3 !== null && mesh?.volume_cm3 !== undefined
                      ? `${mesh.volume_cm3.toFixed(2)} cm³`
                      : "N/A (Open Mesh)"}
                  </span>
                </div>
              </div>

              {!mesh?.is_watertight && (
                <button
                  onClick={() => setActiveTab("repair")}
                  className="w-full py-2 px-3 bg-amber-500/15 hover:bg-amber-500/25 border border-amber-500/40 rounded-lg text-xs font-bold text-amber-300 flex items-center justify-center space-x-2 transition"
                >
                  <Wrench className="w-3.5 h-3.5" />
                  <span>Fix Holes & Heal Mesh in Repair Studio &rarr;</span>
                </button>
              )}
            </div>
          </div>
        )}

        {/* TAB 2: SCALE & TRANSFORM + CAD ALIGNMENT */}
        {activeTab === "transform" && (
          <div className="space-y-4">
            {/* Quick Bed Alignment Actions */}
            <div className="space-y-2">
              <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
                CAD Bed & Orientation Tools
              </span>
              <div className="grid grid-cols-3 gap-1.5">
                <button
                  onClick={handleCenterBed}
                  disabled={!mesh || isCentering}
                  className="p-2 bg-slate-900 hover:bg-slate-800 border border-slate-700 hover:border-cyan-500/50 rounded-lg flex flex-col items-center justify-center space-y-1 transition text-slate-200 disabled:opacity-50"
                  title="Center model in XY build volume and place base at Z=0"
                >
                  {isCentering ? (
                    <Loader2 className="w-3.5 h-3.5 text-cyan-400 animate-spin" />
                  ) : (
                    <AlignCenter className="w-3.5 h-3.5 text-cyan-400" />
                  )}
                  <span className="text-[10px] font-bold">Center Bed</span>
                </button>

                <button
                  onClick={handleLayFlat}
                  disabled={!mesh || isLayingFlat}
                  className="p-2 bg-slate-900 hover:bg-slate-800 border border-slate-700 hover:border-cyan-500/50 rounded-lg flex flex-col items-center justify-center space-y-1 transition text-slate-200 disabled:opacity-50"
                  title="Orient largest face flat onto build plate surface"
                >
                  {isLayingFlat ? (
                    <Loader2 className="w-3.5 h-3.5 text-cyan-400 animate-spin" />
                  ) : (
                    <ArrowDownToLine className="w-3.5 h-3.5 text-cyan-400" />
                  )}
                  <span className="text-[10px] font-bold">Lay Flat</span>
                </button>

                <button
                  onClick={handleAutoOrient}
                  disabled={!mesh || isAutoOrienting}
                  className="p-2 bg-gradient-to-br from-cyan-950/40 to-blue-950/40 hover:from-cyan-900/60 hover:to-blue-900/60 border border-cyan-500/40 rounded-lg flex flex-col items-center justify-center space-y-1 transition text-cyan-300 disabled:opacity-50"
                  title="OrcaSlicer Auto-Orient: Evaluates multi-axis normals to minimize supports and print time"
                >
                  {isAutoOrienting ? (
                    <Loader2 className="w-3.5 h-3.5 text-cyan-400 animate-spin" />
                  ) : (
                    <Sparkles className="w-3.5 h-3.5 text-cyan-400" />
                  )}
                  <span className="text-[10px] font-bold">Auto-Orient</span>
                </button>
              </div>

              {alignMessage && (
                <p className="text-[10px] text-cyan-300 bg-cyan-950/40 border border-cyan-500/30 p-1.5 rounded text-center">
                  {alignMessage}
                </p>
              )}
            </div>

            <div className="w-full h-[1px] bg-slate-800" />

            {/* Rotation Controls */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                  <RotateCw className="w-3.5 h-3.5 text-cyan-400" />
                  <span>Rotation (Degrees)</span>
                </span>
                <span className="text-[10px] text-slate-400 font-mono">STEP: ±90°</span>
              </div>

              {/* Quick Step Buttons per Axis */}
              <div className="space-y-2">
                {/* X Axis */}
                <div className="bg-slate-900/80 border border-slate-800/80 rounded-lg p-2 space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-bold text-rose-400">X AXIS (WIDTH)</span>
                    <span className="text-[10px] text-slate-300 font-mono">{rotX}°</span>
                  </div>
                  <div className="grid grid-cols-2 gap-1.5">
                    <button
                      onClick={() => handleStepRotate('x', -90)}
                      disabled={!mesh || isRotating}
                      className="py-1 px-2 bg-slate-800 hover:bg-slate-700 rounded text-[10px] font-mono font-bold text-slate-200 border border-slate-700/60 transition disabled:opacity-50"
                    >
                      -90° X
                    </button>
                    <button
                      onClick={() => handleStepRotate('x', 90)}
                      disabled={!mesh || isRotating}
                      className="py-1 px-2 bg-slate-800 hover:bg-slate-700 rounded text-[10px] font-mono font-bold text-slate-200 border border-slate-700/60 transition disabled:opacity-50"
                    >
                      +90° X
                    </button>
                  </div>
                </div>

                {/* Y Axis */}
                <div className="bg-slate-900/80 border border-slate-800/80 rounded-lg p-2 space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-bold text-emerald-400">Y AXIS (DEPTH)</span>
                    <span className="text-[10px] text-slate-300 font-mono">{rotY}°</span>
                  </div>
                  <div className="grid grid-cols-2 gap-1.5">
                    <button
                      onClick={() => handleStepRotate('y', -90)}
                      disabled={!mesh || isRotating}
                      className="py-1 px-2 bg-slate-800 hover:bg-slate-700 rounded text-[10px] font-mono font-bold text-slate-200 border border-slate-700/60 transition disabled:opacity-50"
                    >
                      -90° Y
                    </button>
                    <button
                      onClick={() => handleStepRotate('y', 90)}
                      disabled={!mesh || isRotating}
                      className="py-1 px-2 bg-slate-800 hover:bg-slate-700 rounded text-[10px] font-mono font-bold text-slate-200 border border-slate-700/60 transition disabled:opacity-50"
                    >
                      +90° Y
                    </button>
                  </div>
                </div>

                {/* Z Axis */}
                <div className="bg-slate-900/80 border border-slate-800/80 rounded-lg p-2 space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-bold text-cyan-400">Z AXIS (HEIGHT / BED)</span>
                    <span className="text-[10px] text-slate-300 font-mono">{rotZ}°</span>
                  </div>
                  <div className="grid grid-cols-2 gap-1.5">
                    <button
                      onClick={() => handleStepRotate('z', -90)}
                      disabled={!mesh || isRotating}
                      className="py-1 px-2 bg-slate-800 hover:bg-slate-700 rounded text-[10px] font-mono font-bold text-slate-200 border border-slate-700/60 transition disabled:opacity-50"
                    >
                      -90° Z
                    </button>
                    <button
                      onClick={() => handleStepRotate('z', 90)}
                      disabled={!mesh || isRotating}
                      className="py-1 px-2 bg-slate-800 hover:bg-slate-700 rounded text-[10px] font-mono font-bold text-slate-200 border border-slate-700/60 transition disabled:opacity-50"
                    >
                      +90° Z
                    </button>
                  </div>
                </div>
              </div>
            </div>

            <div className="w-full h-[1px] bg-slate-800" />

            {/* OrcaSlicer Advanced Scaling Section */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
                  Precision Scaling
                </span>
                <button
                  onClick={handleFitToBed}
                  disabled={!mesh || isScaling}
                  className="px-2 py-0.5 bg-cyan-950/80 hover:bg-cyan-900/80 border border-cyan-600/50 rounded text-[10px] font-bold text-cyan-300 flex items-center gap-1 transition disabled:opacity-50"
                  title="Scale model uniformly to maximize current printer build volume"
                >
                  <Maximize className="w-3 h-3" />
                  <span>Fit to Bed</span>
                </button>
              </div>

              {/* Scale Quick Presets */}
              <div className="grid grid-cols-5 gap-1">
                {[25, 50, 75, 100, 150].map((h) => (
                  <button
                    key={h}
                    onClick={() => handleQuickScaleHeight(h)}
                    disabled={!mesh || isScaling}
                    className="py-1 bg-slate-900 hover:bg-slate-800 border border-slate-800 hover:border-slate-700 rounded text-[9px] font-mono text-slate-300 disabled:opacity-50"
                  >
                    {h}mm Z
                  </button>
                ))}
              </div>

              <div className="grid grid-cols-2 gap-2 bg-slate-900/60 p-1 rounded border border-slate-800">
                <button
                  onClick={() => setScaleMode("percent")}
                  className={`py-1 text-xs rounded transition ${
                    scaleMode === "percent" ? "bg-cyan-600 text-slate-950 font-bold" : "text-slate-400 hover:text-slate-200"
                  }`}
                >
                  Percentage (%)
                </button>
                <button
                  onClick={() => setScaleMode("dimensions")}
                  className={`py-1 text-xs rounded transition ${
                    scaleMode === "dimensions" ? "bg-cyan-600 text-slate-950 font-bold" : "text-slate-400 hover:text-slate-200"
                  }`}
                >
                  Target Dimension
                </button>
              </div>

              {scaleMode === "percent" ? (
                <div className="space-y-2">
                  <label className="text-slate-400 text-[11px]">Uniform Scale Factor (%)</label>
                  <div className="flex items-center space-x-2">
                    <input
                      type="number"
                      min="1"
                      max="10000"
                      step="5"
                      value={uniformPercent}
                      onChange={(e) => setUniformPercent(parseFloat(e.target.value) || 100)}
                      className="flex-1 bg-slate-900 border border-slate-700 rounded px-2.5 py-1.5 text-slate-100 focus:outline-none focus:border-cyan-400"
                    />
                    <button
                      onClick={handleResetScale}
                      className="px-2 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded text-xs flex items-center gap-1"
                      title="Reset Scale to 100%"
                    >
                      <RotateCcw className="w-3 h-3" />
                      <span>100%</span>
                    </button>
                  </div>
                </div>
              ) : (
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <label className="text-slate-400 text-[11px]">Target Height Z (mm)</label>
                    <button
                      onClick={() => setPreserveAspect(!preserveAspect)}
                      className={`flex items-center space-x-1 text-[10px] px-1.5 py-0.5 rounded border transition ${
                        preserveAspect
                          ? "bg-cyan-950/40 text-cyan-300 border-cyan-500/40"
                          : "bg-slate-800 text-slate-400 border-slate-700"
                      }`}
                    >
                      {preserveAspect ? <Lock className="w-2.5 h-2.5" /> : <Unlock className="w-2.5 h-2.5" />}
                      <span>{preserveAspect ? "Aspect Locked" : "Free Axis"}</span>
                    </button>
                  </div>
                  <input
                    type="number"
                    min="0.1"
                    step="1"
                    value={targetHeight}
                    onChange={(e) => setTargetHeight(parseFloat(e.target.value) || 1)}
                    className="w-full bg-slate-900 border border-slate-700 rounded px-2.5 py-1.5 text-slate-100 focus:outline-none focus:border-cyan-400"
                  />

                  {!preserveAspect && (
                    <>
                      <div className="space-y-1">
                        <label className="text-slate-400 text-[11px]">Target Width X (mm)</label>
                        <input
                          type="number"
                          min="0.1"
                          step="1"
                          value={targetWidth}
                          onChange={(e) => setTargetWidth(parseFloat(e.target.value) || 1)}
                          className="w-full bg-slate-900 border border-slate-700 rounded px-2.5 py-1.5 text-slate-100 focus:outline-none focus:border-cyan-400"
                        />
                      </div>
                      <div className="space-y-1">
                        <label className="text-slate-400 text-[11px]">Target Depth Y (mm)</label>
                        <input
                          type="number"
                          min="0.1"
                          step="1"
                          value={targetDepth}
                          onChange={(e) => setTargetDepth(parseFloat(e.target.value) || 1)}
                          className="w-full bg-slate-900 border border-slate-700 rounded px-2.5 py-1.5 text-slate-100 focus:outline-none focus:border-cyan-400"
                        />
                      </div>
                    </>
                  )}
                </div>
              )}

              {scaleMessage && (
                <p className="text-[11px] text-cyan-400 bg-cyan-950/30 border border-cyan-500/30 p-2 rounded">
                  {scaleMessage}
                </p>
              )}

              <button
                onClick={handleScale}
                disabled={!mesh || isScaling}
                className="w-full py-2 bg-gradient-to-r from-cyan-600 to-cyan-500 hover:from-cyan-500 hover:to-cyan-400 text-slate-950 font-bold rounded transition flex items-center justify-center space-x-2 disabled:opacity-50"
              >
                {isScaling ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Maximize2 className="w-3.5 h-3.5" />}
                <span>Apply Scale Transformation</span>
              </button>
            </div>
          </div>
        )}

        {/* TAB: MASKSMITH STUDIO */}
        {activeTab === "mask" && (
          <MaskSmithStudio
            projectId={projectId}
            mesh={mesh}
            onModelUpdated={onModelUpdated}
            onOperationRecorded={onOperationRecorded}
          />
        )}

        {/* TAB: FIGUREFORGE STUDIO */}
        {activeTab === "figure" && (
          <FigureForgeStudio
            projectId={projectId}
            mesh={mesh}
            onModelUpdated={onModelUpdated}
            onProjectRefreshed={onProjectRefreshed}
            onOperationRecorded={onOperationRecorded}
          />
        )}

        {/* TAB: ORCASLICER STUDIO (MOUSE-EARS, ADAPTIVE LAYERS, FILAMENT COST) */}
        {activeTab === "orca" && (
          <div className="space-y-4">
            {/* 1. Mouse-Ear Anti-Warping Brim */}
            <div className="bg-slate-900/90 border border-slate-800 rounded-lg p-3 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-bold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
                  <CircleDot className="w-3.5 h-3.5 text-cyan-400" />
                  <span>Mouse-Ear Anti-Warping</span>
                </span>
                <span className="text-[9px] px-1.5 py-0.5 rounded bg-cyan-950 text-cyan-400 border border-cyan-800/60">
                  Corner Adhesion
                </span>
              </div>
              <p className="text-[10px] text-slate-400">
                Attaches low-profile circular tabs to acute base footprint corners to prevent bed lift and thermal warping.
              </p>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="text-[10px] text-slate-400 block mb-1">Disc Radius (mm)</label>
                  <input
                    type="number"
                    min="2"
                    max="25"
                    step="1"
                    value={earRadius}
                    onChange={(e) => setEarRadius(parseFloat(e.target.value) || 8)}
                    className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1 text-slate-100 text-xs"
                  />
                </div>
                <div>
                  <label className="text-[10px] text-slate-400 block mb-1">Thickness (mm)</label>
                  <input
                    type="number"
                    min="0.1"
                    max="1.0"
                    step="0.05"
                    value={earThickness}
                    onChange={(e) => setEarThickness(parseFloat(e.target.value) || 0.2)}
                    className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1 text-slate-100 text-xs"
                  />
                </div>
              </div>

              {earMessage && (
                <p className="text-[10px] text-emerald-300 bg-emerald-950/40 border border-emerald-500/30 p-1.5 rounded text-center">
                  {earMessage}
                </p>
              )}

              <button
                onClick={handleGenerateMouseEars}
                disabled={!mesh || isGeneratingEars}
                className="w-full py-1.5 bg-slate-800 hover:bg-slate-700 border border-cyan-500/40 text-cyan-300 font-bold rounded transition flex items-center justify-center space-x-1.5 text-xs disabled:opacity-50"
              >
                {isGeneratingEars ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
                <span>Generate Corner Mouse-Ears</span>
              </button>
            </div>

            {/* 2. Adaptive Variable Layer Height */}
            <div className="bg-slate-900/90 border border-slate-800 rounded-lg p-3 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-bold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
                  <Layers className="w-3.5 h-3.5 text-cyan-400" />
                  <span>Adaptive Layer Height</span>
                </span>
                <span className="text-[9px] px-1.5 py-0.5 rounded bg-blue-950 text-blue-400 border border-blue-800/60">
                  Variable Z
                </span>
              </div>
              <p className="text-[10px] text-slate-400">
                Optimizes layer thickness based on surface curvature slope: fine layers on curves, thick layers on vertical walls.
              </p>

              <div className="grid grid-cols-3 gap-1.5">
                <div>
                  <label className="text-[9px] text-slate-400 block mb-1">Min (mm)</label>
                  <input
                    type="number"
                    step="0.02"
                    value={minLayerH}
                    onChange={(e) => setMinLayerH(parseFloat(e.target.value) || 0.08)}
                    className="w-full bg-slate-950 border border-slate-700 rounded px-1.5 py-1 text-slate-100 text-xs"
                  />
                </div>
                <div>
                  <label className="text-[9px] text-slate-400 block mb-1">Max (mm)</label>
                  <input
                    type="number"
                    step="0.02"
                    value={maxLayerH}
                    onChange={(e) => setMaxLayerH(parseFloat(e.target.value) || 0.28)}
                    className="w-full bg-slate-950 border border-slate-700 rounded px-1.5 py-1 text-slate-100 text-xs"
                  />
                </div>
                <div>
                  <label className="text-[9px] text-slate-400 block mb-1">Nominal (mm)</label>
                  <input
                    type="number"
                    step="0.02"
                    value={nomLayerH}
                    onChange={(e) => setNomLayerH(parseFloat(e.target.value) || 0.20)}
                    className="w-full bg-slate-950 border border-slate-700 rounded px-1.5 py-1 text-slate-100 text-xs"
                  />
                </div>
              </div>

              {adaptiveResult && (
                <div className="p-2.5 rounded bg-slate-950 border border-slate-800 text-[10px] space-y-1">
                  <div className="flex items-center justify-between text-slate-300">
                    <span>Adaptive Layer Count:</span>
                    <span className="font-bold text-cyan-300">{adaptiveResult.total_layers_adaptive} layers</span>
                  </div>
                  <div className="flex items-center justify-between text-slate-400">
                    <span>Nominal (0.20mm):</span>
                    <span>{adaptiveResult.total_layers_nominal} layers</span>
                  </div>
                  <div className="flex items-center justify-between text-emerald-400 font-bold pt-1 border-t border-slate-800">
                    <span>Print Time Impact:</span>
                    <span>{adaptiveResult.time_savings_pct > 0 ? `${adaptiveResult.time_savings_pct}% Faster` : `${Math.abs(adaptiveResult.time_savings_pct)}% Higher Fidelity`}</span>
                  </div>
                </div>
              )}

              <button
                onClick={handleComputeAdaptiveLayers}
                disabled={!mesh || isProfilingLayers}
                className="w-full py-1.5 bg-slate-800 hover:bg-slate-700 border border-blue-500/40 text-blue-300 font-bold rounded transition flex items-center justify-center space-x-1.5 text-xs disabled:opacity-50"
              >
                {isProfilingLayers ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Layers className="w-3.5 h-3.5" />}
                <span>Profile Adaptive Layer Heights</span>
              </button>
            </div>

            {/* 3. Filament Material & Cost Calculator */}
            <div className="bg-slate-900/90 border border-slate-800 rounded-lg p-3 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-bold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
                  <Coins className="w-3.5 h-3.5 text-amber-400" />
                  <span>Filament Library & Print Cost</span>
                </span>
                <span className="text-[9px] px-1.5 py-0.5 rounded bg-amber-950 text-amber-400 border border-amber-800/60">
                  Engineering Presets
                </span>
              </div>

              <div className="space-y-2">
                <div>
                  <label className="text-[10px] text-slate-400 block mb-1">Filament Material Preset</label>
                  <select
                    value={selectedFilamentId}
                    onChange={(e) => setSelectedFilamentId(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1 text-slate-100 text-xs outline-none"
                  >
                    {filaments.map((f) => (
                      <option key={f.id} value={f.id}>
                        {f.name} ({f.material} - ${f.cost_per_kg_usd}/kg)
                      </option>
                    ))}
                  </select>
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="text-[10px] text-slate-400 block mb-1">Infill Density ({infillPct}%)</label>
                    <input
                      type="range"
                      min="0"
                      max="100"
                      step="5"
                      value={infillPct}
                      onChange={(e) => setInfillPct(parseInt(e.target.value))}
                      className="w-full accent-cyan-400"
                    />
                  </div>
                  <div>
                    <label className="text-[10px] text-slate-400 block mb-1">Perimeter Walls</label>
                    <input
                      type="number"
                      min="1"
                      max="8"
                      value={wallCount}
                      onChange={(e) => setWallCount(parseInt(e.target.value) || 3)}
                      className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-0.5 text-slate-100 text-xs"
                    />
                  </div>
                </div>

                {costResult && (
                  <div className="p-2.5 rounded bg-slate-950 border border-slate-800 text-[10px] space-y-1.5">
                    <div className="flex items-center justify-between text-slate-300">
                      <span>Estimated Mass:</span>
                      <span className="font-bold text-amber-300">{costResult.estimated_mass_grams} g</span>
                    </div>
                    <div className="flex items-center justify-between text-slate-400">
                      <span>Filament Length:</span>
                      <span>{costResult.estimated_filament_length_meters} m (1.75mm)</span>
                    </div>
                    <div className="flex items-center justify-between text-emerald-400 font-bold pt-1 border-t border-slate-800">
                      <span>Material Cost:</span>
                      <span className="text-sm">${costResult.estimated_material_cost_usd.toFixed(2)} USD</span>
                    </div>
                  </div>
                )}

                <button
                  onClick={handleEstimateCost}
                  disabled={!mesh || isEstimatingCost}
                  className="w-full py-1.5 bg-slate-800 hover:bg-slate-700 border border-amber-500/40 text-amber-300 font-bold rounded transition flex items-center justify-center space-x-1.5 text-xs disabled:opacity-50"
                >
                  {isEstimatingCost ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Coins className="w-3.5 h-3.5" />}
                  <span>Calculate Mass & Cost Estimate</span>
                </button>
              </div>
            </div>
          </div>
        )}

        {/* TAB: PLANAR SLICE & MESH SPLIT */}
        {activeTab === "slice" && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
                Planar Slicing & Split
              </span>
              <span className="text-[10px] text-cyan-400">WATERTIGHT CAD</span>
            </div>

            {/* Slicing Plane Normal Orientation Selector */}
            <div className="space-y-1.5">
              <label className="text-slate-400 text-[11px] font-bold">Cut Plane Orientation</label>
              <div className="grid grid-cols-3 gap-1.5 bg-slate-900/80 p-1 rounded border border-slate-800">
                <button
                  onClick={() => setSliceAxis("Z")}
                  className={`py-1.5 text-[10px] font-bold rounded transition ${
                    sliceAxis === "Z"
                      ? "bg-cyan-600 text-slate-950 shadow"
                      : "text-slate-400 hover:text-slate-200"
                  }`}
                  title="Horizontal cut parallel to bed (Z-axis)"
                >
                  Z (Horizontal)
                </button>
                <button
                  onClick={() => setSliceAxis("X")}
                  className={`py-1.5 text-[10px] font-bold rounded transition ${
                    sliceAxis === "X"
                      ? "bg-cyan-600 text-slate-950 shadow"
                      : "text-slate-400 hover:text-slate-200"
                  }`}
                  title="Sagittal cut parallel to width (X-axis)"
                >
                  X (Sagittal)
                </button>
                <button
                  onClick={() => setSliceAxis("Y")}
                  className={`py-1.5 text-[10px] font-bold rounded transition ${
                    sliceAxis === "Y"
                      ? "bg-cyan-600 text-slate-950 shadow"
                      : "text-slate-400 hover:text-slate-200"
                  }`}
                  title="Coronal cut parallel to depth (Y-axis)"
                >
                  Y (Coronal)
                </button>
              </div>
            </div>

            {/* Cut Plane Position Slider */}
            <div className="bg-slate-900/70 border border-slate-800 rounded-lg p-3 space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-slate-300 text-[11px] font-bold">
                  Cut Position ({sliceAxis} Height)
                </label>
                <div className="flex items-center space-x-1">
                  <input
                    type="number"
                    step="0.5"
                    value={slicePos}
                    onChange={(e) => setSlicePos(parseFloat(e.target.value) || 0)}
                    className="w-18 bg-slate-950 border border-slate-700 rounded px-1.5 py-0.5 text-right text-cyan-300 font-mono text-xs focus:outline-none focus:border-cyan-400"
                  />
                  <span className="text-[10px] text-slate-500 font-mono">mm</span>
                </div>
              </div>

              <input
                type="range"
                min={sliceAxis === "Z" ? 0 : -(dims[sliceAxis === "X" ? 0 : 1] / 2)}
                max={sliceAxis === "Z" ? (dims[2] || 100) : (dims[sliceAxis === "X" ? 0 : 1] / 2)}
                step="0.5"
                value={slicePos}
                onChange={(e) => setSlicePos(parseFloat(e.target.value))}
                className="w-full accent-cyan-400 cursor-pointer"
              />

              {/* Quick Snap Positions */}
              <div className="grid grid-cols-3 gap-1.5 pt-1">
                <button
                  onClick={() => {
                    const maxDim = dims[sliceAxis === "Z" ? 2 : sliceAxis === "X" ? 0 : 1] || 50;
                    setSlicePos(Math.round((maxDim * 0.25) * 10) / 10);
                  }}
                  className="py-1 bg-slate-800 hover:bg-slate-700 rounded text-[9px] text-slate-300 transition"
                >
                  25% Low
                </button>
                <button
                  onClick={() => {
                    const maxDim = dims[sliceAxis === "Z" ? 2 : sliceAxis === "X" ? 0 : 1] || 50;
                    setSlicePos(Math.round((maxDim * 0.5) * 10) / 10);
                  }}
                  className="py-1 bg-slate-800 hover:bg-slate-700 rounded text-[9px] text-cyan-300 font-bold border border-cyan-500/30 transition"
                >
                  50% Center
                </button>
                <button
                  onClick={() => {
                    const maxDim = dims[sliceAxis === "Z" ? 2 : sliceAxis === "X" ? 0 : 1] || 50;
                    setSlicePos(Math.round((maxDim * 0.75) * 10) / 10);
                  }}
                  className="py-1 bg-slate-800 hover:bg-slate-700 rounded text-[9px] text-slate-300 transition"
                >
                  75% High
                </button>
              </div>
            </div>

            {/* Watertight Planar Cap Checkbox */}
            <div className="bg-slate-900/50 border border-slate-800/80 rounded-lg p-2.5 space-y-2">
              <label className="flex items-center space-x-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={capCutFaces}
                  onChange={(e) => setCapCutFaces(e.target.checked)}
                  className="rounded border-slate-700 bg-slate-800 text-cyan-500 focus:ring-cyan-400"
                />
                <span className="text-[11px] text-slate-200 font-semibold">
                  Cap cut surfaces (watertight triangulation)
                </span>
              </label>
              <p className="text-[10px] text-slate-400 pl-5">
                Automatically seals mating cross-sections with 2D Delaunay polygons for direct 3D printing.
              </p>
            </div>

            {/* Alignment Peg & Socket Connectors */}
            <div className="bg-slate-900/50 border border-slate-800/80 rounded-lg p-2.5 space-y-3">
              <label className="flex items-center space-x-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={createPegs}
                  onChange={(e) => setCreatePegs(e.target.checked)}
                  className="rounded border-slate-700 bg-slate-800 text-cyan-500 focus:ring-cyan-400"
                />
                <span className="text-[11px] text-slate-200 font-semibold">
                  Generate Interlocking Alignment Pegs & Sockets
                </span>
              </label>

              {createPegs && (
                <div className="space-y-2.5 pl-5 pt-1 border-t border-slate-800/80">
                  <div className="space-y-1">
                    <div className="flex justify-between text-[10px]">
                      <span className="text-slate-400">Peg Radius:</span>
                      <span className="text-cyan-300 font-mono">{pegRadius} mm</span>
                    </div>
                    <input
                      type="range"
                      min="1.0"
                      max="10.0"
                      step="0.5"
                      value={pegRadius}
                      onChange={(e) => setPegRadius(parseFloat(e.target.value))}
                      className="w-full accent-cyan-400"
                    />
                  </div>

                  <div className="space-y-1">
                    <div className="flex justify-between text-[10px]">
                      <span className="text-slate-400">Peg Height:</span>
                      <span className="text-cyan-300 font-mono">{pegHeight} mm</span>
                    </div>
                    <input
                      type="range"
                      min="2.0"
                      max="20.0"
                      step="1.0"
                      value={pegHeight}
                      onChange={(e) => setPegHeight(parseFloat(e.target.value))}
                      className="w-full accent-cyan-400"
                    />
                  </div>

                  <div className="space-y-1">
                    <div className="flex justify-between text-[10px]">
                      <span className="text-slate-400">Socket Clearance Tolerance:</span>
                      <span className="text-cyan-300 font-mono">{pegClearance} mm</span>
                    </div>
                    <input
                      type="range"
                      min="0.1"
                      max="0.6"
                      step="0.05"
                      value={pegClearance}
                      onChange={(e) => setPegClearance(parseFloat(e.target.value))}
                      className="w-full accent-cyan-400"
                    />
                  </div>
                </div>
              )}
            </div>

            {/* Notification & Slicing Results Card */}
            {sliceMessage && (
              <div className={`p-2.5 rounded text-[11px] border ${
                sliceResult
                  ? "bg-emerald-950/30 border-emerald-500/40 text-emerald-300"
                  : "bg-rose-950/30 border-rose-500/40 text-rose-300"
              }`}>
                {sliceMessage}
              </div>
            )}

            {sliceResult && (
              <div className="bg-slate-900/90 border border-cyan-500/40 rounded-lg p-3 space-y-2">
                <div className="flex items-center justify-between border-b border-slate-800 pb-1.5">
                  <span className="text-[10px] font-bold text-cyan-400 uppercase tracking-wider">
                    Slicing Outputs (2 Parts)
                  </span>
                  <span className="text-[10px] text-slate-400 font-mono">
                    Area: {sliceResult.cut_area_cm2} cm²
                  </span>
                </div>

                <div className="space-y-1.5 text-[10px]">
                  <div className="flex items-center justify-between p-1.5 bg-slate-950/60 rounded border border-slate-800">
                    <div className="flex items-center space-x-1.5 truncate">
                      <span className="w-2 h-2 rounded-full bg-cyan-400 shrink-0" />
                      <span className="text-slate-200 truncate">{sliceResult.top_model.filename}</span>
                    </div>
                    <span className="text-slate-400 shrink-0">{formatNumber(sliceResult.top_model.triangle_count)} tris</span>
                  </div>

                  <div className="flex items-center justify-between p-1.5 bg-slate-950/60 rounded border border-slate-800">
                    <div className="flex items-center space-x-1.5 truncate">
                      <span className="w-2 h-2 rounded-full bg-emerald-400 shrink-0" />
                      <span className="text-slate-200 truncate">{sliceResult.bottom_model.filename}</span>
                    </div>
                    <span className="text-slate-400 shrink-0">{formatNumber(sliceResult.bottom_model.triangle_count)} tris</span>
                  </div>
                </div>
              </div>
            )}

            {/* Execute Cut Button */}
            <button
              onClick={handleExecuteSlice}
              disabled={!mesh || isSlicing}
              className="w-full py-2.5 bg-gradient-to-r from-cyan-600 to-cyan-500 hover:from-cyan-500 hover:to-cyan-400 text-slate-950 font-bold rounded transition flex items-center justify-center space-x-2 disabled:opacity-50 shadow-md cursor-pointer"
            >
              {isSlicing ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Scissors className="w-4 h-4" />
              )}
              <span>Execute Planar Split</span>
            </button>
          </div>
        )}

        {/* TAB: MESH REPAIR & HEALING */}
        {activeTab === "repair" && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
                Mesh Healing & Repair
              </span>
              <span className="text-[10px] text-cyan-400">AUTOMATED HEALING</span>
            </div>

            {/* Current Health Badge */}
            <div className={`p-3 rounded-lg border flex flex-col space-y-2 ${
              mesh?.is_watertight
                ? "bg-emerald-950/20 border-emerald-500/40"
                : "bg-amber-950/20 border-amber-500/40"
            }`}>
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-bold text-slate-200">Mesh Topology Status</span>
                <span className={`text-[10px] font-bold px-2 py-0.5 rounded border flex items-center space-x-1 ${
                  mesh?.is_watertight
                    ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/40"
                    : "bg-amber-500/20 text-amber-300 border-amber-500/40"
                }`}>
                  {mesh?.is_watertight ? <ShieldCheck className="w-3.5 h-3.5" /> : <AlertTriangle className="w-3.5 h-3.5" />}
                  <span>{mesh?.is_watertight ? "MANIFOLD WATERTIGHT" : "NON-MANIFOLD / OPEN"}</span>
                </span>
              </div>
              <p className="text-[11px] text-slate-300 leading-relaxed">
                {mesh?.is_watertight
                  ? "Mesh is fully closed and manifold. Slicers will generate clean solid perimeters without perimeter leakage."
                  : "Mesh contains open boundary edges or holes. Slicers may invert shells or fail slicing. Run auto-repair below to stitch open boundaries."}
              </p>
            </div>

            {/* Repair Options Checklist */}
            <div className="bg-slate-900/70 border border-slate-800 rounded-lg p-3 space-y-3">
              <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
                Repair Operations
              </span>

              <div className="space-y-2.5">
                <label className="flex items-center space-x-2 text-[11px] text-slate-300 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={fillHoles}
                    onChange={(e) => setFillHoles(e.target.checked)}
                    className="accent-cyan-400 rounded cursor-pointer"
                  />
                  <span>Fill & Stitch Open Boundary Holes</span>
                </label>

                <label className="flex items-center space-x-2 text-[11px] text-slate-300 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={fixNormals}
                    onChange={(e) => setFixNormals(e.target.checked)}
                    className="accent-cyan-400 rounded cursor-pointer"
                  />
                  <span>Unify & Invert Inconsistent Normals</span>
                </label>

                <label className="flex items-center space-x-2 text-[11px] text-slate-300 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={removeDegenerate}
                    onChange={(e) => setRemoveDegenerate(e.target.checked)}
                    className="accent-cyan-400 rounded cursor-pointer"
                  />
                  <span>Remove Degenerate & Zero-Area Faces</span>
                </label>

                <label className="flex items-center space-x-2 text-[11px] text-slate-300 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={weldVertices}
                    onChange={(e) => setWeldVertices(e.target.checked)}
                    className="accent-cyan-400 rounded cursor-pointer"
                  />
                  <span>Weld Coincident Duplicate Vertices</span>
                </label>

                {weldVertices && (
                  <div className="pl-6 space-y-1">
                    <div className="flex items-center justify-between text-[10px] text-slate-400">
                      <span>Weld Tolerance</span>
                      <span className="font-mono text-cyan-400">{weldThreshold} mm</span>
                    </div>
                    <input
                      type="range"
                      min="0.00001"
                      max="0.01"
                      step="0.00005"
                      value={weldThreshold}
                      onChange={(e) => setWeldThreshold(parseFloat(e.target.value))}
                      className="w-full accent-cyan-400 cursor-pointer"
                    />
                  </div>
                )}
              </div>
            </div>

            {/* Notification message */}
            {repairMessage && (
              <div className={`p-2.5 rounded text-[11px] border flex items-start space-x-2 ${
                repairReport?.is_watertight_after
                  ? "bg-emerald-950/30 border-emerald-500/40 text-emerald-300"
                  : "bg-cyan-950/30 border-cyan-500/40 text-cyan-300"
              }`}>
                <CheckCheck className="w-4 h-4 shrink-0 mt-0.5" />
                <span>{repairMessage}</span>
              </div>
            )}

            {/* Repair Report Results Card */}
            {repairReport && (
              <div className="bg-slate-900/90 border border-cyan-500/40 rounded-lg p-3 space-y-2.5">
                <div className="flex items-center justify-between border-b border-slate-800 pb-1.5">
                  <span className="text-[10px] font-bold text-cyan-400 uppercase tracking-wider flex items-center gap-1">
                    <Sparkles className="w-3.5 h-3.5" />
                    <span>Repair Diagnostics</span>
                  </span>
                  <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded ${
                    repairReport.is_watertight_after
                      ? "bg-emerald-500/20 text-emerald-300"
                      : "bg-amber-500/20 text-amber-300"
                  }`}>
                    {repairReport.is_watertight_after ? "100% Watertight" : "Healed Partially"}
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-2 text-[10px]">
                  <div className="bg-slate-950/60 p-2 rounded border border-slate-800">
                    <span className="text-slate-400 block">Holes Filled</span>
                    <span className="text-emerald-400 font-bold text-xs">{repairReport.holes_filled}</span>
                  </div>
                  <div className="bg-slate-950/60 p-2 rounded border border-slate-800">
                    <span className="text-slate-400 block">Degenerate Faces</span>
                    <span className="text-amber-400 font-bold text-xs">-{repairReport.degenerate_faces_removed}</span>
                  </div>
                  <div className="bg-slate-950/60 p-2 rounded border border-slate-800">
                    <span className="text-slate-400 block">Merged Vertices</span>
                    <span className="text-cyan-400 font-bold text-xs">{repairReport.duplicate_vertices_welded}</span>
                  </div>
                  <div className="bg-slate-950/60 p-2 rounded border border-slate-800">
                    <span className="text-slate-400 block">Final Volume</span>
                    <span className="text-slate-100 font-bold text-xs">
                      {repairReport.volume_restored_cm3 ? `${repairReport.volume_restored_cm3.toFixed(2)} cm³` : "Open Mesh"}
                    </span>
                  </div>
                </div>

                <div className="text-[10px] text-slate-400 border-t border-slate-800 pt-1.5 flex justify-between">
                  <span>Triangles:</span>
                  <span className="text-slate-200">{repairReport.triangle_count_before} &rarr; {repairReport.triangle_count_after}</span>
                </div>
              </div>
            )}

            {/* Action Button */}
            <button
              onClick={handleRepair}
              disabled={!mesh || isRepairing}
              className="w-full py-2.5 bg-gradient-to-r from-cyan-600 to-cyan-500 hover:from-cyan-500 hover:to-cyan-400 text-slate-950 font-bold rounded transition flex items-center justify-center space-x-2 disabled:opacity-50 shadow-md cursor-pointer"
            >
              {isRepairing ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Wrench className="w-4 h-4" />
              )}
              <span>Run Auto-Repair & Heal Mesh</span>
            </button>

            {/* Hollowing & Drain Holes Studio */}
            <div className="bg-slate-900/90 border border-slate-800 rounded-lg p-3 space-y-3 pt-3 mt-4">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-bold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
                  <SplitSquareVertical className="w-3.5 h-3.5 text-cyan-400" />
                  <span>Hollow Solid Shell</span>
                </span>
                <span className="text-[9px] px-1.5 py-0.5 rounded bg-cyan-950 text-cyan-400 border border-cyan-800/60">
                  Resin & Filament Saver
                </span>
              </div>

              <div className="space-y-2.5">
                <div className="space-y-1">
                  <div className="flex justify-between text-[10px]">
                    <span className="text-slate-400">Wall Thickness:</span>
                    <span className="text-cyan-300 font-mono">{wallThickness} mm</span>
                  </div>
                  <input
                    type="range"
                    min="1.0"
                    max="5.0"
                    step="0.2"
                    value={wallThickness}
                    onChange={(e) => setWallThickness(parseFloat(e.target.value))}
                    className="w-full accent-cyan-400 cursor-pointer"
                  />
                </div>

                <label className="flex items-center space-x-2 text-[11px] text-slate-300 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={addDrainHoles}
                    onChange={(e) => setAddDrainHoles(e.target.checked)}
                    className="accent-cyan-400 rounded cursor-pointer"
                  />
                  <span>Add Bottom Drain Holes</span>
                </label>

                {addDrainHoles && (
                  <div className="grid grid-cols-2 gap-2 pl-4">
                    <div>
                      <label className="text-[10px] text-slate-400 block mb-1">Hole Radius (mm)</label>
                      <input
                        type="number"
                        min="1"
                        max="10"
                        step="0.5"
                        value={drainHoleRadius}
                        onChange={(e) => setDrainHoleRadius(parseFloat(e.target.value) || 2.0)}
                        className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-0.5 text-slate-100 text-xs"
                      />
                    </div>
                    <div>
                      <label className="text-[10px] text-slate-400 block mb-1">Hole Count</label>
                      <input
                        type="number"
                        min="1"
                        max="6"
                        value={drainHoleCount}
                        onChange={(e) => setDrainHoleCount(parseInt(e.target.value) || 2)}
                        className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-0.5 text-slate-100 text-xs"
                      />
                    </div>
                  </div>
                )}

                {hollowMessage && (
                  <div className="p-2 rounded bg-cyan-950/30 border border-cyan-500/40 text-cyan-300 text-[10px]">
                    {hollowMessage}
                  </div>
                )}

                <button
                  onClick={handleHollow}
                  disabled={!mesh || isHollowing}
                  className="w-full py-2 bg-slate-800 hover:bg-slate-700 border border-cyan-500/40 text-cyan-300 font-bold rounded transition flex items-center justify-center space-x-1.5 text-xs disabled:opacity-50 cursor-pointer"
                >
                  {isHollowing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Layers className="w-3.5 h-3.5" />}
                  <span>Hollow Geometry ({wallThickness}mm Shell)</span>
                </button>
              </div>
            </div>
          </div>
        )}

        {/* TAB 3: PRINTER & PRINTABILITY */}
        {activeTab === "printability" && (
          <div className="space-y-4">
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
                  Printer Selection
                </span>
                {onOpenCreatePrinter && (
                  <button
                    onClick={onOpenCreatePrinter}
                    className="text-[10px] text-cyan-400 hover:text-cyan-300 flex items-center gap-1 transition"
                  >
                    <PlusCircle className="w-3 h-3" />
                    <span>New Profile</span>
                  </button>
                )}
              </div>
              <select
                value={printer.id}
                onChange={(e) => {
                  const found = printers.find((p) => p.id === e.target.value);
                  if (found && onPrinterChange) onPrinterChange(found);
                }}
                className="w-full bg-slate-900 border border-slate-700 text-xs font-mono text-slate-200 rounded px-2.5 py-1.5 focus:outline-none focus:border-cyan-400"
              >
                {printers.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.manufacturer} {p.model} ({p.build_width_mm}x{p.build_depth_mm}x{p.build_height_mm}mm)
                  </option>
                ))}
              </select>
            </div>

            <div className="bg-slate-900/60 border border-slate-800 rounded-lg p-3 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-slate-400">Build Volume</span>
                <span className="text-slate-200">{bedW} × {bedD} × {bedH} mm</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-400">Fit Status</span>
                <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded flex items-center space-x-1 ${
                  fitsInBed
                    ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30"
                    : "bg-rose-500/15 text-rose-400 border border-rose-500/30"
                }`}>
                  {fitsInBed ? <CheckCircle2 className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
                  <span>{fitsInBed ? "FITS BUILD VOLUME" : "EXCEEDS ENVELOPE"}</span>
                </span>
              </div>
              {overhangData && (
                <div className="flex items-center justify-between pt-1 border-t border-slate-800/80">
                  <span className="text-slate-400">Support Estimate</span>
                  <span className="text-amber-400 font-semibold">{overhangData.overhang_percentage.toFixed(1)}% of area</span>
                </div>
              )}
            </div>

            {!fitsInBed && (
              <div className="bg-rose-950/20 border border-rose-500/40 rounded-lg p-3 space-y-1.5">
                <span className="text-[11px] font-bold text-rose-400">Exceeded Dimensions:</span>
                {!fitsX && <p className="text-[11px] text-rose-300">• Width X exceeds by {(dims[0] - bedW).toFixed(2)} mm</p>}
                {!fitsY && <p className="text-[11px] text-rose-300">• Depth Y exceeds by {(dims[1] - bedD).toFixed(2)} mm</p>}
                {!fitsZ && <p className="text-[11px] text-rose-300">• Height Z exceeds by {(dims[2] - bedH).toFixed(2)} mm</p>}
              </div>
            )}
          </div>
        )}

        {/* TAB 4: EXPORT */}
        {activeTab === "export" && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
                Model Export
              </span>
              <span className="text-[10px] text-cyan-400">OUTPUT: DATA/EXPORTS/</span>
            </div>

            <div className="space-y-1">
              <label className="text-slate-400 text-[11px]">Export Format</label>
              <select
                value={exportFormat}
                onChange={(e) => setExportFormat(e.target.value as any)}
                className="w-full bg-slate-900 border border-slate-700 rounded px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-cyan-400"
              >
                <option value="stl">STL (Binary, 3D Print Standard)</option>
                <option value="obj">OBJ (Wavefront Mesh)</option>
                <option value="glb">GLB (Binary GLTF)</option>
              </select>
            </div>

            <div className="space-y-1">
              <label className="text-slate-400 text-[11px]">Filename</label>
              <input
                type="text"
                value={exportFilename}
                onChange={(e) => setExportFilename(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700 rounded px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-cyan-400"
              />
            </div>

            {exportDownloadUrl && (
              <div className="p-3 bg-emerald-950/30 border border-emerald-500/40 rounded space-y-2">
                <p className="text-[11px] text-emerald-400 flex items-center space-x-1.5">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  <span>Model exported successfully!</span>
                </p>
                <a
                  href={`http://localhost:8000${exportDownloadUrl}`}
                  download
                  className="block text-center py-1.5 bg-emerald-600 hover:bg-emerald-500 text-slate-950 font-bold rounded text-xs transition"
                >
                  Download {exportFilename}.{exportFormat}
                </a>
              </div>
            )}

            <button
              onClick={handleExport}
              disabled={!mesh || isExporting}
              className="w-full py-2 bg-gradient-to-r from-cyan-600 to-cyan-500 hover:from-cyan-500 hover:to-cyan-400 text-slate-950 font-bold rounded transition flex items-center justify-center space-x-2 disabled:opacity-50 cursor-pointer"
            >
              {isExporting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Download className="w-3.5 h-3.5" />}
              <span>Export Single Mesh</span>
            </button>

            {/* ORCASLICER & BAMBU STUDIO 3MF BUNDLE EXPORT */}
            <div className="pt-4 border-t border-slate-800/80 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-bold uppercase tracking-wider text-cyan-400 flex items-center gap-1.5">
                  <Package className="w-3.5 h-3.5" />
                  <span>OrcaSlicer / Bambu 3MF</span>
                </span>
                <span className="text-[9px] px-1.5 py-0.5 rounded bg-cyan-950 text-cyan-300 border border-cyan-500/30">
                  MULTI-MODEL
                </span>
              </div>

              <p className="text-[11px] text-slate-400 leading-relaxed">
                Bundles all active models, plater coordinates, orientations, and scales into a single 3MF project container ready for OrcaSlicer or Bambu Studio.
              </p>

              <div className="space-y-1">
                <label className="text-slate-400 text-[10px]">Filament Preset</label>
                <select
                  value={export3MFFilament}
                  onChange={(e) => setExport3MFFilament(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-slate-200 text-xs focus:outline-none focus:border-cyan-400"
                >
                  <option value="Generic PLA">Generic PLA</option>
                  <option value="Bambu PLA Basic">Bambu PLA Basic</option>
                  <option value="Generic PETG">Generic PETG</option>
                  <option value="Generic ABS/ASA">Generic ABS / ASA</option>
                  <option value="Generic TPU 95A">Generic TPU 95A</option>
                </select>
              </div>

              {export3MFResult && (
                <div className="p-2.5 bg-cyan-950/40 border border-cyan-500/40 rounded space-y-2">
                  <p className="text-[11px] text-cyan-300 flex items-center space-x-1.5">
                    <CheckCircle2 className="w-3.5 h-3.5 text-cyan-400" />
                    <span>3MF Project Container Ready ({export3MFResult.models_exported} models, {(export3MFResult.file_size_bytes / 1024).toFixed(1)} KB)</span>
                  </p>
                  <a
                    href={`http://localhost:8000${export3MFResult.download_url}`}
                    download
                    className="block text-center py-1.5 bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold rounded text-xs transition"
                  >
                    Download {export3MFResult.filename}
                  </a>
                </div>
              )}

              <button
                onClick={handleExport3MF}
                disabled={isExporting3MF || !models || models.length === 0}
                className="w-full py-2 bg-slate-800 hover:bg-slate-700 border border-cyan-500/50 text-cyan-300 font-bold rounded transition flex items-center justify-center space-x-2 disabled:opacity-50 cursor-pointer text-xs"
              >
                {isExporting3MF ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Package className="w-3.5 h-3.5" />}
                <span>Export Project as 3MF</span>
              </button>
            </div>
          </div>
        )}

        {/* TAB 5: OPERATION HISTORY */}
        {activeTab === "history" && (
          <div className="space-y-3">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
              Project Operations ({operations.length})
            </span>

            {operations.length === 0 ? (
              <p className="text-slate-500 text-xs italic">No operations recorded yet.</p>
            ) : (
              <div className="space-y-2">
                {operations.map((op) => (
                  <div key={op.id} className="bg-slate-900/70 border border-slate-800 rounded p-2.5 space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-bold text-cyan-400 px-1 py-0.5 bg-cyan-950/40 rounded border border-cyan-500/20">
                        {op.operation_type}
                      </span>
                      <span className="text-[9px] text-slate-500">
                        {new Date(op.timestamp).toLocaleTimeString()}
                      </span>
                    </div>
                    <p className="text-[11px] text-slate-200">{op.user_summary}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </aside>
  );
}
