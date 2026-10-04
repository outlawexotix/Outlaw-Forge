"use client";

import React, { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  Box,
  CheckCircle2,
  ChevronRight,
  CircleDollarSign,
  Download,
  Loader2,
  Printer,
  Ruler,
  ScanLine,
  Settings2,
  ShieldCheck,
  Wrench,
} from "lucide-react";
import {
  CostEstimationResult,
  OverhangAnalysis,
  PrinterProfile,
  ThinWallAnalysisResult,
  WorkingModel,
} from "@shared/types/api";
import { apiClient } from "@/lib/api-client";
import { formatNumber } from "@/lib/utils";

interface ReadinessPanelProps {
  projectId: string;
  mesh: WorkingModel | null;
  printer: PrinterProfile;
  onModelUpdated?: (model: WorkingModel) => void;
  onOperationRecorded?: () => void;
  onOpenAdvanced?: () => void;
}

type ActionState = "idle" | "repairing" | "preparing" | "exporting" | "ready" | "error";

interface ReadinessRowProps {
  icon: React.ReactNode;
  title: string;
  status: string;
  detail: string;
  tone: "good" | "warn" | "bad" | "neutral";
  metric?: string;
}

function ReadinessRow({ icon, title, status, detail, tone, metric }: ReadinessRowProps) {
  const toneClasses = {
    good: "text-emerald-400",
    warn: "text-amber-400",
    bad: "text-red-400",
    neutral: "text-neutral-400",
  }[tone];

  return (
    <div className="border border-neutral-800 bg-neutral-900/55 px-3 py-3 rounded-sm">
      <div className="flex items-start gap-3">
        <div className={`mt-0.5 shrink-0 ${toneClasses}`}>{icon}</div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-3">
            <span className="text-[13px] font-semibold text-neutral-100">{title}</span>
            <span className={`text-[11px] font-mono font-semibold ${toneClasses}`}>{status}</span>
          </div>
          <p className="mt-1 text-[11px] leading-4 text-neutral-500">{detail}</p>
          {metric && <p className="mt-1.5 text-[11px] font-mono text-neutral-300">{metric}</p>}
        </div>
        <ChevronRight className="mt-0.5 h-3.5 w-3.5 shrink-0 text-neutral-600" />
      </div>
    </div>
  );
}

export function ReadinessPanel({
  projectId,
  mesh,
  printer,
  onModelUpdated,
  onOperationRecorded,
  onOpenAdvanced,
}: ReadinessPanelProps) {
  const [overhangs, setOverhangs] = useState<OverhangAnalysis | null>(null);
  const [thinWalls, setThinWalls] = useState<ThinWallAnalysisResult | null>(null);
  const [costEstimate, setCostEstimate] = useState<CostEstimationResult | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [actionState, setActionState] = useState<ActionState>("idle");
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setActionState("idle");
    setActionMessage(null);

    if (!projectId || !mesh) {
      setOverhangs(null);
      setThinWalls(null);
      setCostEstimate(null);
      return () => {
        cancelled = true;
      };
    }

    const modelId = mesh.id;

    async function analyze() {
      setIsAnalyzing(true);
      const [overhangResult, wallResult, costResult] = await Promise.allSettled([
        apiClient.getOverhangs(projectId, modelId, 45),
        apiClient.analyzeThinWalls(projectId, modelId, { min_wall_thickness_mm: 0.8 }),
        apiClient.estimateCost(projectId, modelId, { material_type: "PLA", infill_density_percent: 20 }),
      ]);
      if (cancelled) return;
      setOverhangs(overhangResult.status === "fulfilled" ? overhangResult.value : null);
      setThinWalls(wallResult.status === "fulfilled" ? wallResult.value : null);
      setCostEstimate(costResult.status === "fulfilled" ? costResult.value : null);
      setIsAnalyzing(false);
    }

    analyze();
    return () => {
      cancelled = true;
    };
  }, [projectId, mesh]);

  const dimensions = mesh?.bounds.dimensions_mm ?? [0, 0, 0];
  const fitsBuildVolume = Boolean(
    mesh &&
      dimensions[0] <= printer.build_width_mm &&
      dimensions[1] <= printer.build_depth_mm &&
      dimensions[2] <= printer.build_height_mm
  );
  const overhangIssueCount = overhangs?.requires_support ? 1 : 0;
  const thinWallCount = thinWalls?.thin_wall_count ?? 0;
  const thinWallIssueCount = thinWallCount > 0 ? 1 : 0;
  const totalIssues =
    overhangIssueCount + thinWallIssueCount + (mesh && !mesh.is_watertight ? 1 : 0) + (mesh && !fitsBuildVolume ? 1 : 0);

  const runRepair = async () => {
    if (!mesh || !projectId) return;
    try {
      setActionState("repairing");
      setActionMessage("Healing mesh geometry...");
      const result = await apiClient.repairModel(projectId, mesh.id, {
        fill_holes: true,
        fix_normals: true,
        remove_degenerate: true,
        weld_vertices: true,
      });
      onModelUpdated?.(result.repaired_model);
      onOperationRecorded?.();
      setActionState("ready");
      setActionMessage(result.message);
    } catch (error) {
      setActionState("error");
      setActionMessage(error instanceof Error ? error.message : "Repair failed");
    }
  };

  const prepareForPrint = useCallback(async () => {
    if (!mesh || !projectId) return;
    try {
      setActionState("preparing");
      setActionMessage("Optimizing model orientation...");
      let current = mesh;
      if (!current.is_watertight) {
        const repair = await apiClient.repairModel(projectId, current.id, {
          fill_holes: true,
          fix_normals: true,
          remove_degenerate: true,
          weld_vertices: true,
        });
        current = repair.repaired_model;
      }
      const oriented = await apiClient.autoOrient(projectId, current.id);
      onModelUpdated?.(oriented.oriented_model);
      onOperationRecorded?.();
      setActionState("ready");
      setActionMessage(`Print-ready orientation saved. Overhang reduced ${formatNumber(oriented.reduction_percentage, 1)}%.`);
    } catch (error) {
      setActionState("error");
      setActionMessage(error instanceof Error ? error.message : "Preparation failed");
    }
  }, [mesh, projectId, onModelUpdated, onOperationRecorded]);

  const busy = actionState === "repairing" || actionState === "preparing" || actionState === "exporting";

  useEffect(() => {
    const handleShortcut = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "p" && mesh && !busy) {
        event.preventDefault();
        void prepareForPrint();
      }
    };
    window.addEventListener("keydown", handleShortcut);
    return () => window.removeEventListener("keydown", handleShortcut);
  }, [busy, mesh, prepareForPrint]);

  const exportModel = async () => {
    if (!mesh || !projectId) return;
    try {
      setActionState("exporting");
      setActionMessage("Generating production STL...");
      const filename = `${mesh.filename.replace(/\.[^/.]+$/, "")}_print_ready.stl`;
      const result = await apiClient.exportModel(projectId, mesh.id, { format: "stl", filename });
      const download = document.createElement("a");
      download.href = apiClient.getDownloadUrl(result.download_url);
      download.download = result.filename;
      download.rel = "noopener noreferrer";
      download.click();
      onOperationRecorded?.();
      setActionState("ready");
      setActionMessage(`${result.filename} is ready.`);
    } catch (error) {
      setActionState("error");
      setActionMessage(error instanceof Error ? error.message : "Export failed");
    }
  };

  return (
    <aside className="w-[360px] shrink-0 border-l border-neutral-800 bg-[#0b0d10] flex flex-col overflow-hidden">
      <div className="h-14 border-b border-neutral-800 px-4 flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-[17px] font-semibold tracking-tight text-neutral-100">Print Readiness</h2>
            {isAnalyzing && <Loader2 className="h-3.5 w-3.5 animate-spin text-amber-400" />}
          </div>
          <p className="mt-0.5 text-[10px] font-mono text-neutral-500">
            {mesh ? `${mesh.triangle_count.toLocaleString()} TRIANGLES` : "NO MODEL LOADED"}
          </p>
        </div>
        <div className={`flex items-center gap-1.5 text-xs font-semibold ${totalIssues ? "text-amber-400" : "text-emerald-400"}`}>
          {totalIssues ? <AlertTriangle className="h-4 w-4" /> : <CheckCircle2 className="h-4 w-4" />}
          <span>{totalIssues ? `${totalIssues} issues` : "Ready"}</span>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {!mesh ? (
          <div className="h-full min-h-[360px] flex flex-col items-center justify-center text-center px-8">
            <Box className="h-9 w-9 text-neutral-600" />
            <h3 className="mt-4 text-sm font-semibold text-neutral-200">Import a model to begin</h3>
            <p className="mt-2 text-xs leading-5 text-neutral-500">Drop an STL, OBJ, GLB, or 3MF file into the viewport.</p>
          </div>
        ) : (
          <>
            <ReadinessRow
              icon={<ScanLine className="h-5 w-5" />}
              title="Overhangs"
              status={overhangs?.requires_support ? `${overhangs.overhang_face_count} faces` : "No issues"}
              detail="Surfaces above the support threshold are highlighted in the viewport."
              tone={overhangIssueCount ? "bad" : "good"}
              metric={overhangs ? `${formatNumber(overhangs.overhang_area_cm2, 2)} cm² at ${formatNumber(overhangs.critical_angle_deg, 0)}°` : "Analyzing surface angles"}
            />
            <ReadinessRow
              icon={<Ruler className="h-5 w-5" />}
              title="Thin Walls"
              status={thinWallCount ? `${thinWallCount} regions` : "No issues"}
              detail="Walls below 0.8 mm may print weak or fail."
              tone={thinWallCount ? "warn" : "good"}
              metric={thinWalls ? `Minimum ${formatNumber(thinWalls.min_detected_thickness_mm, 2)} mm` : "Analyzing wall thickness"}
            />
            <ReadinessRow
              icon={<ShieldCheck className="h-5 w-5" />}
              title="Watertightness"
              status={mesh.is_watertight ? "No issues" : "Repair needed"}
              detail={mesh.is_watertight ? "The model is a closed printable volume." : "Open edges or holes were detected in the mesh."}
              tone={mesh.is_watertight ? "good" : "bad"}
            />
            <ReadinessRow
              icon={<Printer className="h-5 w-5" />}
              title="Build Volume"
              status={fitsBuildVolume ? "Within limits" : "Exceeds bed"}
              detail={`${printer.manufacturer} ${printer.model}`}
              tone={fitsBuildVolume ? "good" : "bad"}
              metric={`${formatNumber(dimensions[0], 1)} × ${formatNumber(dimensions[1], 1)} × ${formatNumber(dimensions[2], 1)} mm`}
            />

            <div className="border border-neutral-800 bg-neutral-900/55 px-3 py-3 rounded-sm">
              <div className="flex items-center gap-2 text-[13px] font-semibold text-neutral-100">
                <CircleDollarSign className="h-4 w-4 text-emerald-400" />
                Material Estimate
              </div>
              <div className="mt-3 grid grid-cols-3 gap-3 text-center">
                <div>
                  <div className="text-sm font-semibold text-neutral-200">{costEstimate ? `${formatNumber(costEstimate.mass_grams, 1)} g` : "--"}</div>
                  <div className="text-[9px] uppercase tracking-wider text-neutral-600">Mass</div>
                </div>
                <div className="border-x border-neutral-800">
                  <div className="text-sm font-semibold text-neutral-200">{costEstimate ? `${formatNumber(costEstimate.filament_length_m, 2)} m` : "--"}</div>
                  <div className="text-[9px] uppercase tracking-wider text-neutral-600">Filament</div>
                </div>
                <div>
                  <div className="text-sm font-semibold text-neutral-200">{costEstimate ? `$${formatNumber(costEstimate.material_cost_usd, 2)}` : "--"}</div>
                  <div className="text-[9px] uppercase tracking-wider text-neutral-600">PLA</div>
                </div>
              </div>
            </div>
          </>
        )}
      </div>

      <div className="border-t border-neutral-800 p-3 space-y-2 bg-neutral-950/80">
        {actionMessage && (
          <div className={`px-3 py-2 text-[11px] leading-4 border rounded-sm ${actionState === "error" ? "border-red-500/40 bg-red-500/10 text-red-300" : "border-amber-500/30 bg-amber-500/10 text-amber-200"}`}>
            {actionMessage}
          </div>
        )}
        <button
          onClick={prepareForPrint}
          disabled={!mesh || busy}
          className="h-12 w-full bg-amber-500 hover:bg-amber-400 disabled:bg-neutral-800 disabled:text-neutral-600 text-neutral-950 text-sm font-bold flex items-center justify-center gap-2 rounded-sm transition-colors"
        >
          {actionState === "preparing" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Printer className="h-4 w-4" />}
          Prepare for Print
          <span className="ml-auto mr-3 text-[10px] font-mono opacity-70">Ctrl + P</span>
        </button>
        <div className="grid grid-cols-2 gap-2">
          <button
            onClick={runRepair}
            disabled={!mesh || busy}
            className="h-10 border border-neutral-700 bg-neutral-900 hover:bg-neutral-800 disabled:opacity-40 text-xs font-semibold text-neutral-200 flex items-center justify-center gap-2 rounded-sm transition-colors"
          >
            {actionState === "repairing" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Wrench className="h-4 w-4" />}
            Repair
          </button>
          <button
            onClick={exportModel}
            disabled={!mesh || busy}
            className="h-10 border border-neutral-700 bg-neutral-900 hover:bg-neutral-800 disabled:opacity-40 text-xs font-semibold text-neutral-200 flex items-center justify-center gap-2 rounded-sm transition-colors"
          >
            {actionState === "exporting" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
            Export STL
          </button>
        </div>
        <button
          onClick={onOpenAdvanced}
          className="h-8 w-full text-[10px] font-mono text-neutral-500 hover:text-neutral-200 flex items-center justify-center gap-2 transition-colors"
        >
          <Settings2 className="h-3.5 w-3.5" />
          Advanced geometry tools
        </button>
      </div>
    </aside>
  );
}
