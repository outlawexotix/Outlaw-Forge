"use client";

import React, { useState } from "react";
import {
  WorkingModel,
  InfillPattern,
  InfillGenerateResult,
  RibReinforceResult,
} from "@shared/types/api";
import { apiClient } from "@/lib/api-client";
import {
  Box,
  Layers,
  Sparkles,
  Sliders,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Maximize2,
  Cpu,
  Shield,
  CircleDot,
  Eye,
  EyeOff,
  Droplets,
  Grid,
  Zap,
} from "lucide-react";

interface InfillStudioProps {
  projectId: string;
  mesh: WorkingModel | null;
  onModelUpdated?: (updated: WorkingModel) => void;
  onOperationRecorded?: () => void;
  onSlicePlaneChange?: (origin: [number, number, number], normal: [number, number, number]) => void;
}

const INFILL_PATTERNS: { id: InfillPattern; name: string; desc: string; icon: string }[] = [
  {
    id: "gyroid",
    name: "Gyroid (TPMS)",
    desc: "Triply periodic minimal surface with isotropic multi-axis strength.",
    icon: "🌊",
  },
  {
    id: "honeycomb",
    name: "Honeycomb",
    desc: "Hexagonal column cell lattice for vertical compressive strength.",
    icon: "⬡",
  },
  {
    id: "rectilinear",
    name: "Rectilinear",
    desc: "Orthogonal 2D grid matrix for high-speed printing.",
    icon: "▦",
  },
  {
    id: "cubic",
    name: "Cubic",
    desc: "3D intersecting cubic box lattice with balanced load distribution.",
    icon: "🧊",
  },
];

export function InfillStudio({
  projectId,
  mesh,
  onModelUpdated,
  onOperationRecorded,
  onSlicePlaneChange,
}: InfillStudioProps) {
  // Infill generator state
  const [selectedPattern, setSelectedPattern] = useState<InfillPattern>("gyroid");
  const [densityPct, setDensityPct] = useState<number>(20);
  const [unitCellSizeMm, setUnitCellSizeMm] = useState<number>(10.0);
  const [wallThicknessMm, setWallThicknessMm] = useState<number>(2.0);
  const [hollowFirst, setHollowFirst] = useState<boolean>(true);
  const [isGeneratingInfill, setIsGeneratingInfill] = useState(false);
  const [infillResult, setInfillResult] = useState<InfillGenerateResult | null>(null);
  const [infillError, setInfillError] = useState<string | null>(null);

  // Rib reinforcement state
  const [ribThicknessMm, setRibThicknessMm] = useState<number>(1.5);
  const [ribSpacingMm, setRibSpacingMm] = useState<number>(12.0);
  const [ribHeightMm, setRibHeightMm] = useState<number>(3.0);
  const [drainageRadiusMm, setDrainageRadiusMm] = useState<number>(2.0);
  const [addDrainage, setAddDrainage] = useState<boolean>(true);
  const [drainageAxis, setDrainageAxis] = useState<"x" | "y" | "z">("z");
  const [isReinforcing, setIsReinforcing] = useState(false);
  const [ribResult, setRibResult] = useState<RibReinforceResult | null>(null);
  const [ribError, setRibError] = useState<string | null>(null);

  // Cross-section cutaway viewport preview state
  const [enableCutaway, setEnableCutaway] = useState<boolean>(false);
  const [cutawayHeightPct, setCutawayHeightPct] = useState<number>(50);

  const modelHeight = mesh?.bounds.dimensions_mm[2] || 50.0;
  const modelZMin = mesh?.bounds.min[2] || 0.0;

  // Handle cutaway slider scrub
  const handleCutawayChange = (pct: number) => {
    setCutawayHeightPct(pct);
    if (onSlicePlaneChange && mesh) {
      const zCut = modelZMin + (pct / 100.0) * modelHeight;
      const xCenter = (mesh.bounds.min[0] + mesh.bounds.max[0]) / 2.0;
      const yCenter = (mesh.bounds.min[1] + mesh.bounds.max[1]) / 2.0;
      onSlicePlaneChange([xCenter, yCenter, zCut], [0, 0, 1]);
    }
  };

  const toggleCutaway = () => {
    const nextState = !enableCutaway;
    setEnableCutaway(nextState);
    if (nextState) {
      handleCutawayChange(cutawayHeightPct);
    } else if (onSlicePlaneChange && mesh) {
      // Move cut plane far above model
      onSlicePlaneChange([0, 0, modelZMin + modelHeight + 100], [0, 0, 1]);
    }
  };

  // Generate infill action
  const handleGenerateInfill = async () => {
    if (!mesh) return;
    setIsGeneratingInfill(true);
    setInfillError(null);
    setInfillResult(null);

    try {
      const result = await apiClient.generateInfill(projectId, mesh.id, {
        pattern: selectedPattern,
        density: densityPct / 100.0,
        unit_cell_size_mm: unitCellSizeMm,
        wall_thickness_mm: wallThicknessMm,
        hollow_first: hollowFirst,
      });

      setInfillResult(result);
      if (result.working_model && onModelUpdated) {
        onModelUpdated(result.working_model);
      }
      if (onOperationRecorded) {
        onOperationRecorded();
      }
    } catch (err: any) {
      setInfillError(err.message || "Failed to generate infill lattice");
    } finally {
      setIsGeneratingInfill(false);
    }
  };

  // Reinforce ribs action
  const handleReinforceRibs = async () => {
    if (!mesh) return;
    setIsReinforcing(true);
    setRibError(null);
    setRibResult(null);

    try {
      const result = await apiClient.reinforceRibs(projectId, mesh.id, {
        rib_thickness_mm: ribThicknessMm,
        rib_spacing_mm: ribSpacingMm,
        rib_height_mm: ribHeightMm,
        drainage_hole_radius_mm: drainageRadiusMm,
        add_drainage_channel: addDrainage,
        drainage_axis: drainageAxis,
        wall_thickness_mm: wallThicknessMm,
      });

      setRibResult(result);
      if (result.working_model && onModelUpdated) {
        onModelUpdated(result.working_model);
      }
      if (onOperationRecorded) {
        onOperationRecorded();
      }
    } catch (err: any) {
      setRibError(err.message || "Failed to reinforce ribs");
    } finally {
      setIsReinforcing(false);
    }
  };

  return (
    <div className="space-y-6 text-xs text-slate-300">
      {/* Studio Header */}
      <div className="rounded-md border border-cyan-800/40 bg-slate-900/80 p-3 shadow-inner">
        <div className="flex items-center gap-2 text-cyan-400 font-semibold mb-1">
          <Cpu className="h-4 w-4" />
          <span>Parametric 3D Infill & Lattice Studio</span>
        </div>
        <p className="text-[11px] text-slate-400 leading-relaxed">
          Generate procedural 3D internal lattices (Gyroid TPMS, Honeycomb, Rectilinear, Cubic),
          reinforce thin hollow walls with anti-buckling ribs, and punch continuous resin drainage channels.
        </p>
      </div>

      {/* Viewport Cross-Section Cutaway HUD */}
      <div className="rounded-md border border-slate-800 bg-slate-900/60 p-3 space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5 font-medium text-slate-200">
            <Eye className="h-3.5 w-3.5 text-amber-400" />
            <span>Interactive Viewport Cutaway</span>
          </div>
          <button
            type="button"
            onClick={toggleCutaway}
            className={`px-2.5 py-1 rounded text-[11px] font-medium transition-all ${
              enableCutaway
                ? "bg-amber-600/30 text-amber-300 border border-amber-500/50"
                : "bg-slate-800 text-slate-400 hover:text-slate-200 border border-slate-700"
            }`}
          >
            {enableCutaway ? "Cutaway Active" : "Enable Cutaway"}
          </button>
        </div>

        {enableCutaway && (
          <div className="space-y-1.5 pt-1">
            <div className="flex justify-between text-[10px] text-slate-400">
              <span>Section Z Height</span>
              <span className="font-mono text-cyan-400">
                {(modelZMin + (cutawayHeightPct / 100.0) * modelHeight).toFixed(1)} mm ({cutawayHeightPct}%)
              </span>
            </div>
            <input
              type="range"
              min="0"
              max="100"
              step="1"
              value={cutawayHeightPct}
              onChange={(e) => handleCutawayChange(Number(e.target.value))}
              className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-amber-500"
            />
          </div>
        )}
      </div>

      {/* Section 1: 3D Procedural Lattice Generator */}
      <div className="space-y-3">
        <div className="flex items-center gap-1.5 text-slate-200 font-semibold border-b border-slate-800 pb-1.5">
          <Grid className="h-3.5 w-3.5 text-cyan-400" />
          <span>Procedural Infill Pattern</span>
        </div>

        {/* Pattern Selection Grid */}
        <div className="grid grid-cols-2 gap-2">
          {INFILL_PATTERNS.map((p) => {
            const isSelected = selectedPattern === p.id;
            return (
              <button
                key={p.id}
                type="button"
                onClick={() => setSelectedPattern(p.id)}
                className={`p-2 rounded border text-left transition-all ${
                  isSelected
                    ? "border-cyan-500 bg-cyan-950/40 text-cyan-200 shadow-sm shadow-cyan-900/30"
                    : "border-slate-800 bg-slate-900/40 hover:border-slate-700 text-slate-400"
                }`}
              >
                <div className="flex items-center gap-1.5 mb-1 font-medium text-[11px] text-slate-200">
                  <span>{p.icon}</span>
                  <span>{p.name}</span>
                </div>
                <div className="text-[10px] text-slate-400 leading-tight line-clamp-2">
                  {p.desc}
                </div>
              </button>
            );
          })}
        </div>

        {/* Density Slider */}
        <div className="space-y-1.5 bg-slate-900/40 p-2.5 rounded border border-slate-800/80">
          <div className="flex justify-between items-center text-[11px]">
            <span className="text-slate-300">Infill Density</span>
            <span className="font-mono text-cyan-400 font-semibold">{densityPct}%</span>
          </div>
          <input
            type="range"
            min="5"
            max="95"
            step="1"
            value={densityPct}
            onChange={(e) => setDensityPct(Number(e.target.value))}
            className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-cyan-500"
          />
          <div className="flex justify-between gap-1 pt-1">
            {[10, 15, 20, 35, 50, 80].map((preset) => (
              <button
                key={preset}
                type="button"
                onClick={() => setDensityPct(preset)}
                className={`px-1.5 py-0.5 rounded text-[9px] font-mono transition-colors ${
                  densityPct === preset
                    ? "bg-cyan-600/30 text-cyan-300 border border-cyan-500/40"
                    : "bg-slate-800 text-slate-400 hover:text-slate-200 border border-slate-700/50"
                }`}
              >
                {preset}%
              </button>
            ))}
          </div>
        </div>

        {/* Geometric Parameters: Unit Cell Size & Wall Thickness */}
        <div className="grid grid-cols-2 gap-2">
          <div className="space-y-1 bg-slate-900/40 p-2 rounded border border-slate-800/80">
            <label className="text-[10px] text-slate-400">Unit Cell Pitch (mm)</label>
            <input
              type="number"
              min="2.0"
              max="40.0"
              step="0.5"
              value={unitCellSizeMm}
              onChange={(e) => setUnitCellSizeMm(Math.max(1.0, Number(e.target.value)))}
              className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1 text-slate-200 font-mono text-xs focus:border-cyan-500 focus:outline-none"
            />
          </div>

          <div className="space-y-1 bg-slate-900/40 p-2 rounded border border-slate-800/80">
            <label className="text-[10px] text-slate-400">Wall Shell (mm)</label>
            <input
              type="number"
              min="0.8"
              max="10.0"
              step="0.2"
              value={wallThicknessMm}
              onChange={(e) => setWallThicknessMm(Math.max(0.4, Number(e.target.value)))}
              className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1 text-slate-200 font-mono text-xs focus:border-cyan-500 focus:outline-none"
            />
          </div>
        </div>

        {/* Hollow First Toggle */}
        <label className="flex items-center gap-2 cursor-pointer text-[11px] text-slate-300 select-none bg-slate-900/40 p-2 rounded border border-slate-800/80">
          <input
            type="checkbox"
            checked={hollowFirst}
            onChange={(e) => setHollowFirst(e.target.checked)}
            className="rounded border-slate-700 bg-slate-950 text-cyan-500 focus:ring-0 focus:ring-offset-0"
          />
          <span>Retain solid outer shell and hollow internal core</span>
        </label>

        {/* Generate Infill Button */}
        <button
          type="button"
          disabled={!mesh || isGeneratingInfill}
          onClick={handleGenerateInfill}
          className="w-full flex items-center justify-center gap-2 py-2 rounded font-medium text-xs bg-cyan-600 hover:bg-cyan-500 text-white disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-md shadow-cyan-900/30"
        >
          {isGeneratingInfill ? (
            <>
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              <span>Generating Volumetric Infill...</span>
            </>
          ) : (
            <>
              <Zap className="h-3.5 w-3.5" />
              <span>Apply {selectedPattern.toUpperCase()} Infill</span>
            </>
          )}
        </button>

        {/* Infill Success Feedback */}
        {infillResult && (
          <div className="rounded border border-emerald-500/40 bg-emerald-950/30 p-2.5 space-y-1">
            <div className="flex items-center gap-1.5 text-emerald-400 font-medium">
              <CheckCircle2 className="h-3.5 w-3.5" />
              <span>Infill Generated Successfully</span>
            </div>
            <div className="text-[10px] text-slate-300 font-mono space-y-0.5">
              <div>Volume Reduction: <span className="text-emerald-300 font-semibold">{infillResult.volume_reduction_percent}%</span></div>
              <div>Triangles: {infillResult.triangle_count.toLocaleString()} | Vertices: {infillResult.vertex_count.toLocaleString()}</div>
            </div>
          </div>
        )}

        {infillError && (
          <div className="rounded border border-rose-500/40 bg-rose-950/30 p-2.5 flex items-start gap-1.5 text-rose-400">
            <AlertCircle className="h-3.5 w-3.5 shrink-0 mt-0.5" />
            <span className="text-[10px]">{infillError}</span>
          </div>
        )}
      </div>

      {/* Section 2: Structural Rib Reinforcement & Continuous Drainage */}
      <div className="space-y-3 pt-2 border-t border-slate-800">
        <div className="flex items-center gap-1.5 text-slate-200 font-semibold border-b border-slate-800 pb-1.5">
          <Shield className="h-3.5 w-3.5 text-amber-400" />
          <span>Internal Ribs & Drainage Channels</span>
        </div>

        <div className="grid grid-cols-2 gap-2">
          <div className="space-y-1 bg-slate-900/40 p-2 rounded border border-slate-800/80">
            <label className="text-[10px] text-slate-400">Rib Thickness (mm)</label>
            <input
              type="number"
              min="0.6"
              max="6.0"
              step="0.2"
              value={ribThicknessMm}
              onChange={(e) => setRibThicknessMm(Math.max(0.4, Number(e.target.value)))}
              className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1 text-slate-200 font-mono text-xs focus:border-amber-500 focus:outline-none"
            />
          </div>

          <div className="space-y-1 bg-slate-900/40 p-2 rounded border border-slate-800/80">
            <label className="text-[10px] text-slate-400">Rib Spacing (mm)</label>
            <input
              type="number"
              min="4.0"
              max="30.0"
              step="1.0"
              value={ribSpacingMm}
              onChange={(e) => setRibSpacingMm(Math.max(2.0, Number(e.target.value)))}
              className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1 text-slate-200 font-mono text-xs focus:border-amber-500 focus:outline-none"
            />
          </div>
        </div>

        <div className="space-y-2 bg-slate-900/40 p-2.5 rounded border border-slate-800/80">
          <label className="flex items-center gap-2 cursor-pointer text-[11px] text-slate-300 select-none">
            <input
              type="checkbox"
              checked={addDrainage}
              onChange={(e) => setAddDrainage(e.target.checked)}
              className="rounded border-slate-700 bg-slate-950 text-amber-500 focus:ring-0 focus:ring-offset-0"
            />
            <div className="flex items-center gap-1">
              <Droplets className="h-3 w-3 text-amber-400" />
              <span>Punch continuous resin drainage channel</span>
            </div>
          </label>

          {addDrainage && (
            <div className="grid grid-cols-2 gap-2 pt-1 border-t border-slate-800/60">
              <div className="space-y-1">
                <label className="text-[10px] text-slate-400">Hole Radius (mm)</label>
                <input
                  type="number"
                  min="0.5"
                  max="10.0"
                  step="0.5"
                  value={drainageRadiusMm}
                  onChange={(e) => setDrainageRadiusMm(Math.max(0.5, Number(e.target.value)))}
                  className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1 text-slate-200 font-mono text-xs focus:border-amber-500 focus:outline-none"
                />
              </div>

              <div className="space-y-1">
                <label className="text-[10px] text-slate-400">Drainage Axis</label>
                <select
                  value={drainageAxis}
                  onChange={(e) => setDrainageAxis(e.target.value as "x" | "y" | "z")}
                  className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1 text-slate-200 text-xs focus:border-amber-500 focus:outline-none"
                >
                  <option value="z">Z - Base Floor</option>
                  <option value="x">X - Lateral Side</option>
                  <option value="y">Y - Front/Back</option>
                </select>
              </div>
            </div>
          )}
        </div>

        {/* Reinforce Ribs Button */}
        <button
          type="button"
          disabled={!mesh || isReinforcing}
          onClick={handleReinforceRibs}
          className="w-full flex items-center justify-center gap-2 py-2 rounded font-medium text-xs bg-amber-600 hover:bg-amber-500 text-white disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-md shadow-amber-900/30"
        >
          {isReinforcing ? (
            <>
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              <span>Reinforcing Hollow Walls...</span>
            </>
          ) : (
            <>
              <Shield className="h-3.5 w-3.5" />
              <span>Apply Anti-Buckling Ribs</span>
            </>
          )}
        </button>

        {/* Rib Success Feedback */}
        {ribResult && (
          <div className="rounded border border-emerald-500/40 bg-emerald-950/30 p-2.5 space-y-1">
            <div className="flex items-center gap-1.5 text-emerald-400 font-medium">
              <CheckCircle2 className="h-3.5 w-3.5" />
              <span>Rib Reinforcement Complete</span>
            </div>
            <div className="text-[10px] text-slate-300 font-mono space-y-0.5">
              <div>Reinforced Ribs: <span className="text-amber-300 font-semibold">{ribResult.rib_count}</span></div>
              <div>Drainage Holes: <span className="text-cyan-300 font-semibold">{ribResult.drainage_holes_count}</span></div>
            </div>
          </div>
        )}

        {ribError && (
          <div className="rounded border border-rose-500/40 bg-rose-950/30 p-2.5 flex items-start gap-1.5 text-rose-400">
            <AlertCircle className="h-3.5 w-3.5 shrink-0 mt-0.5" />
            <span className="text-[10px]">{ribError}</span>
          </div>
        )}
      </div>
    </div>
  );
}
