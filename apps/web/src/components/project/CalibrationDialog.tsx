"use client";

import React, { useState } from "react";
import { 
  CalibrationType, 
  CalibrationGeneratePayload, 
  CalibrationGenerateResult,
  WorkingModel 
} from "@shared/types/api";
import { apiClient } from "@/lib/api-client";
import { 
  Thermometer, 
  Layers, 
  MoveHorizontal, 
  Sliders, 
  Box, 
  Zap, 
  Compass, 
  Check, 
  Loader2, 
  X, 
  Sparkles,
  Info
} from "lucide-react";

interface CalibrationDialogProps {
  projectId: string;
  isOpen: boolean;
  onClose: () => void;
  onModelGenerated: (model: WorkingModel) => void;
}

interface ArtifactOption {
  type: CalibrationType;
  title: string;
  category: string;
  description: string;
  icon: React.ElementType;
  badge: string;
}

const ARTIFACT_OPTIONS: ArtifactOption[] = [
  {
    type: "temp_tower",
    title: "Temperature Tower",
    category: "Thermal",
    description: "Multi-tiered tower testing bridging, overhangs, and stringing at graduated nozzle temperatures.",
    icon: Thermometer,
    badge: "Essential",
  },
  {
    type: "flow_rate",
    title: "Flow Rate Swatches",
    category: "Extrusion",
    description: "Graduated top-surface swatch tiles to calibrate flow multiplier and achieve mirror-smooth finishes.",
    icon: Layers,
    badge: "Accuracy",
  },
  {
    type: "retraction_tower",
    title: "Retraction Test Tower",
    category: "Extrusion",
    description: "Dual-pole stringing test to find the minimum clean retraction distance without oozing.",
    icon: MoveHorizontal,
    badge: "Quality",
  },
  {
    type: "tolerance_gauge",
    title: "Tolerance / Clearance Gauge",
    category: "Mechanical",
    description: "Interlocking cylindrical test pins (0.1mm to 0.5mm clearance) to calibrate print-in-place tolerances.",
    icon: Sliders,
    badge: "Engineering",
  },
  {
    type: "overhang_benchmark",
    title: "Overhang & Bridging Benchmark",
    category: "Geometry",
    description: "Stepped cantilever fins testing steep overhangs (15° to 75°) and horizontal bridging spans.",
    icon: Compass,
    badge: "Benchmark",
  },
  {
    type: "calibration_cube_v2",
    title: "XYZ Calibration Cube V2",
    category: "Dimensional",
    description: "Precision 20x20x20mm cube with dimensional notches to measure lead-screw and belt step calibration.",
    icon: Box,
    badge: "Precision",
  },
  {
    type: "max_volumetric_speed",
    title: "Max Volumetric Speed Tower",
    category: "Speed",
    description: "Continuous flow tower to identify the maximum melting rate (mm³/s) of your hotend.",
    icon: Zap,
    badge: "High Speed",
  },
];

export function CalibrationDialog({
  projectId,
  isOpen,
  onClose,
  onModelGenerated,
}: CalibrationDialogProps) {
  const [selectedType, setSelectedType] = useState<CalibrationType>("temp_tower");
  const [isGenerating, setIsGenerating] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [resultNotes, setResultNotes] = useState<string[] | null>(null);

  // Form parameters
  const [startTemp, setStartTemp] = useState<number>(220);
  const [endTemp, setEndTemp] = useState<number>(185);
  const [tempStep, setTempStep] = useState<number>(5);

  const [flowStart, setFlowStart] = useState<number>(-15);
  const [flowEnd, setFlowEnd] = useState<number>(15);
  const [flowStep, setFlowStep] = useState<number>(5);

  const [retractStart, setRetractStart] = useState<number>(1.0);
  const [retractEnd, setRetractEnd] = useState<number>(6.0);
  const [retractStep, setRetractStep] = useState<number>(1.0);

  const [toleranceMin, setToleranceMin] = useState<number>(0.1);
  const [toleranceMax, setToleranceMax] = useState<number>(0.5);
  const [toleranceStep, setToleranceStep] = useState<number>(0.1);

  const [cubeSize, setCubeSize] = useState<number>(20.0);

  if (!isOpen) return null;

  const handleGenerate = async () => {
    setIsGenerating(true);
    setErrorMsg(null);
    setResultNotes(null);

    try {
      const payload: CalibrationGeneratePayload = {
        calibration_type: selectedType,
        start_temp_c: startTemp,
        end_temp_c: endTemp,
        temp_step_c: tempStep,
        flow_rate_start_pct: flowStart,
        flow_rate_end_pct: flowEnd,
        flow_rate_step_pct: flowStep,
        retraction_start_mm: retractStart,
        retraction_end_mm: retractEnd,
        retraction_step_mm: retractStep,
        tolerance_min_mm: toleranceMin,
        tolerance_max_mm: toleranceMax,
        tolerance_step_mm: toleranceStep,
        cube_size_mm: cubeSize,
      };

      const result = await apiClient.generateCalibrationArtifact(projectId, payload);
      onModelGenerated(result.model);
      setResultNotes(result.suggested_slicer_notes);
      setTimeout(() => {
        onClose();
      }, 1200);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to generate artifact";
      setErrorMsg(msg);
    } finally {
      setIsGenerating(false);
    }
  };

  const activeOption = ARTIFACT_OPTIONS.find((o) => o.type === selectedType) || ARTIFACT_OPTIONS[0];
  const IconComponent = activeOption.icon;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4">
      <div className="relative w-full max-w-4xl max-h-[90vh] overflow-y-auto rounded-xl bg-slate-900 border border-slate-800 shadow-2xl flex flex-col text-slate-100">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-950/50">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-cyan-500/10 border border-cyan-500/30 text-cyan-400">
              <Sparkles className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-white tracking-wide flex items-center gap-2">
                OrcaSlicer Calibration Studio
                <span className="text-xs px-2 py-0.5 rounded-full bg-cyan-500/20 text-cyan-300 font-normal">
                  Procedural CAD
                </span>
              </h2>
              <p className="text-xs text-slate-400">
                Generate precision 3D test artifacts for printer and filament tuning
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Content Body: Two Column Grid */}
        <div className="grid grid-cols-1 md:grid-cols-12 gap-6 p-6">
          {/* Left Column: Artifact Selection Cards */}
          <div className="md:col-span-5 space-y-2.5 max-h-[480px] overflow-y-auto pr-1">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider block mb-2">
              Select Calibration Test
            </span>
            {ARTIFACT_OPTIONS.map((opt) => {
              const isSelected = selectedType === opt.type;
              const OptIcon = opt.icon;
              return (
                <button
                  key={opt.type}
                  onClick={() => setSelectedType(opt.type)}
                  className={`w-full text-left p-3 rounded-lg border transition-all flex items-start gap-3 ${
                    isSelected
                      ? "bg-cyan-500/10 border-cyan-500/50 shadow-lg shadow-cyan-950/20"
                      : "bg-slate-800/40 border-slate-800 hover:bg-slate-800/80 hover:border-slate-700 text-slate-300"
                  }`}
                >
                  <div
                    className={`mt-0.5 p-2 rounded-md ${
                      isSelected
                        ? "bg-cyan-500 text-slate-950"
                        : "bg-slate-800 text-slate-400"
                    }`}
                  >
                    <OptIcon className="h-4 w-4" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-1">
                      <h4 className={`text-sm font-semibold truncate ${isSelected ? "text-cyan-300" : "text-white"}`}>
                        {opt.title}
                      </h4>
                      <span className="text-[10px] px-1.5 py-0.2 rounded bg-slate-800 text-slate-400 border border-slate-700">
                        {opt.badge}
                      </span>
                    </div>
                    <p className="text-xs text-slate-400 line-clamp-2 mt-0.5">
                      {opt.description}
                    </p>
                  </div>
                </button>
              );
            })}
          </div>

          {/* Right Column: Active Artifact Configuration */}
          <div className="md:col-span-7 flex flex-col justify-between bg-slate-950/40 rounded-xl border border-slate-800 p-5">
            <div className="space-y-4">
              <div className="flex items-center gap-3 pb-3 border-b border-slate-800">
                <div className="p-2.5 rounded-lg bg-cyan-500/20 text-cyan-400 border border-cyan-500/30">
                  <IconComponent className="h-6 w-6" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-white">{activeOption.title}</h3>
                  <p className="text-xs text-slate-400">{activeOption.description}</p>
                </div>
              </div>

              {/* Dynamic Artifact Parameter Form */}
              {selectedType === "temp_tower" && (
                <div className="space-y-3">
                  <div className="grid grid-cols-3 gap-3">
                    <div>
                      <label className="text-xs text-slate-400 block mb-1">Start Temp (°C)</label>
                      <input
                        type="number"
                        value={startTemp}
                        onChange={(e) => setStartTemp(Number(e.target.value))}
                        className="w-full bg-slate-900 border border-slate-700 rounded-md px-3 py-1.5 text-sm text-white focus:border-cyan-500 outline-none"
                      />
                    </div>
                    <div>
                      <label className="text-xs text-slate-400 block mb-1">End Temp (°C)</label>
                      <input
                        type="number"
                        value={endTemp}
                        onChange={(e) => setEndTemp(Number(e.target.value))}
                        className="w-full bg-slate-900 border border-slate-700 rounded-md px-3 py-1.5 text-sm text-white focus:border-cyan-500 outline-none"
                      />
                    </div>
                    <div>
                      <label className="text-xs text-slate-400 block mb-1">Step (°C)</label>
                      <input
                        type="number"
                        value={tempStep}
                        onChange={(e) => setTempStep(Number(e.target.value))}
                        className="w-full bg-slate-900 border border-slate-700 rounded-md px-3 py-1.5 text-sm text-white focus:border-cyan-500 outline-none"
                      />
                    </div>
                  </div>
                  <div className="p-3 rounded-lg bg-slate-900/80 border border-slate-800 text-xs text-slate-300 space-y-1">
                    <p className="font-semibold text-cyan-400 flex items-center gap-1.5">
                      <Info className="h-3.5 w-3.5" /> Slicer Tuning Note:
                    </p>
                    <p>
                      Tower will have {Math.max(1, Math.floor((startTemp - endTemp) / tempStep) + 1)} tiers.
                      Set temperature changes every 8.0mm Z-height.
                    </p>
                  </div>
                </div>
              )}

              {selectedType === "flow_rate" && (
                <div className="space-y-3">
                  <div className="grid grid-cols-3 gap-3">
                    <div>
                      <label className="text-xs text-slate-400 block mb-1">Start Offset (%)</label>
                      <input
                        type="number"
                        value={flowStart}
                        onChange={(e) => setFlowStart(Number(e.target.value))}
                        className="w-full bg-slate-900 border border-slate-700 rounded-md px-3 py-1.5 text-sm text-white focus:border-cyan-500 outline-none"
                      />
                    </div>
                    <div>
                      <label className="text-xs text-slate-400 block mb-1">End Offset (%)</label>
                      <input
                        type="number"
                        value={flowEnd}
                        onChange={(e) => setFlowEnd(Number(e.target.value))}
                        className="w-full bg-slate-900 border border-slate-700 rounded-md px-3 py-1.5 text-sm text-white focus:border-cyan-500 outline-none"
                      />
                    </div>
                    <div>
                      <label className="text-xs text-slate-400 block mb-1">Step (%)</label>
                      <input
                        type="number"
                        value={flowStep}
                        onChange={(e) => setFlowStep(Number(e.target.value))}
                        className="w-full bg-slate-900 border border-slate-700 rounded-md px-3 py-1.5 text-sm text-white focus:border-cyan-500 outline-none"
                      />
                    </div>
                  </div>
                </div>
              )}

              {selectedType === "retraction_tower" && (
                <div className="space-y-3">
                  <div className="grid grid-cols-3 gap-3">
                    <div>
                      <label className="text-xs text-slate-400 block mb-1">Start (mm)</label>
                      <input
                        type="number"
                        step="0.5"
                        value={retractStart}
                        onChange={(e) => setRetractStart(Number(e.target.value))}
                        className="w-full bg-slate-900 border border-slate-700 rounded-md px-3 py-1.5 text-sm text-white focus:border-cyan-500 outline-none"
                      />
                    </div>
                    <div>
                      <label className="text-xs text-slate-400 block mb-1">End (mm)</label>
                      <input
                        type="number"
                        step="0.5"
                        value={retractEnd}
                        onChange={(e) => setRetractEnd(Number(e.target.value))}
                        className="w-full bg-slate-900 border border-slate-700 rounded-md px-3 py-1.5 text-sm text-white focus:border-cyan-500 outline-none"
                      />
                    </div>
                    <div>
                      <label className="text-xs text-slate-400 block mb-1">Step (mm)</label>
                      <input
                        type="number"
                        step="0.5"
                        value={retractStep}
                        onChange={(e) => setRetractStep(Number(e.target.value))}
                        className="w-full bg-slate-900 border border-slate-700 rounded-md px-3 py-1.5 text-sm text-white focus:border-cyan-500 outline-none"
                      />
                    </div>
                  </div>
                </div>
              )}

              {selectedType === "tolerance_gauge" && (
                <div className="space-y-3">
                  <div className="grid grid-cols-3 gap-3">
                    <div>
                      <label className="text-xs text-slate-400 block mb-1">Min Gap (mm)</label>
                      <input
                        type="number"
                        step="0.05"
                        value={toleranceMin}
                        onChange={(e) => setToleranceMin(Number(e.target.value))}
                        className="w-full bg-slate-900 border border-slate-700 rounded-md px-3 py-1.5 text-sm text-white focus:border-cyan-500 outline-none"
                      />
                    </div>
                    <div>
                      <label className="text-xs text-slate-400 block mb-1">Max Gap (mm)</label>
                      <input
                        type="number"
                        step="0.05"
                        value={toleranceMax}
                        onChange={(e) => setToleranceMax(Number(e.target.value))}
                        className="w-full bg-slate-900 border border-slate-700 rounded-md px-3 py-1.5 text-sm text-white focus:border-cyan-500 outline-none"
                      />
                    </div>
                    <div>
                      <label className="text-xs text-slate-400 block mb-1">Step (mm)</label>
                      <input
                        type="number"
                        step="0.05"
                        value={toleranceStep}
                        onChange={(e) => setToleranceStep(Number(e.target.value))}
                        className="w-full bg-slate-900 border border-slate-700 rounded-md px-3 py-1.5 text-sm text-white focus:border-cyan-500 outline-none"
                      />
                    </div>
                  </div>
                </div>
              )}

              {selectedType === "calibration_cube_v2" && (
                <div className="space-y-3">
                  <div>
                    <label className="text-xs text-slate-400 block mb-1">Cube Dimension (mm)</label>
                    <input
                      type="number"
                      step="1"
                      value={cubeSize}
                      onChange={(e) => setCubeSize(Number(e.target.value))}
                      className="w-full bg-slate-900 border border-slate-700 rounded-md px-3 py-1.5 text-sm text-white focus:border-cyan-500 outline-none"
                    />
                  </div>
                </div>
              )}

              {errorMsg && (
                <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-xs text-red-400">
                  {errorMsg}
                </div>
              )}

              {resultNotes && (
                <div className="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-xs text-emerald-300 space-y-1">
                  <p className="font-semibold flex items-center gap-1">
                    <Check className="h-4 w-4" /> Artifact Generated Successfully!
                  </p>
                  {resultNotes.map((note, idx) => (
                    <p key={idx} className="text-slate-300">• {note}</p>
                  ))}
                </div>
              )}
            </div>

            {/* Bottom Action Button */}
            <div className="pt-4 mt-6 border-t border-slate-800 flex justify-end gap-3">
              <button
                onClick={onClose}
                className="px-4 py-2 rounded-lg text-sm font-medium text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleGenerate}
                disabled={isGenerating}
                className="px-5 py-2 rounded-lg text-sm font-semibold bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-slate-950 flex items-center gap-2 shadow-lg shadow-cyan-950/30 disabled:opacity-50 transition-all"
              >
                {isGenerating ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Generating 3D Geometry...
                  </>
                ) : (
                  <>
                    <Sparkles className="h-4 w-4" />
                    Generate & Place on Bed
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
