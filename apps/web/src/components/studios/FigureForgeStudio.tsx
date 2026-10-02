"use client";

import React, { useState, useEffect } from "react";
import {
  WorkingModel,
  CenterOfMassAnalysis,
  PlinthShape,
  PlinthGenerateResult,
  KeyPegResult,
} from "@shared/types/api";
import { apiClient } from "@/lib/api-client";
import {
  Sparkles,
  Award,
  Scale,
  Disc,
  Hexagon,
  Square,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Loader2,
  PlusCircle,
  Pin,
  Maximize2,
  Layers,
} from "lucide-react";

interface FigureForgeStudioProps {
  projectId: string;
  mesh: WorkingModel | null;
  onModelUpdated?: (updated: WorkingModel) => void;
  onProjectRefreshed?: () => void;
  onOperationRecorded?: () => void;
}

export function FigureForgeStudio({
  projectId,
  mesh,
  onModelUpdated,
  onProjectRefreshed,
  onOperationRecorded,
}: FigureForgeStudioProps) {
  // COM State
  const [comData, setComData] = useState<CenterOfMassAnalysis | null>(null);
  const [isLoadingCOM, setIsLoadingCOM] = useState(false);

  // Plinth Generator State
  const [plinthShape, setPlinthShape] = useState<PlinthShape>("cylinder");
  const [plinthDia, setPlinthDia] = useState<number>(80.0);
  const [plinthHeight, setPlinthHeight] = useState<number>(15.0);
  const [addNameplate, setAddNameplate] = useState<boolean>(false);
  const [addSockets, setAddSockets] = useState<boolean>(true);
  const [socketDia, setSocketDia] = useState<number>(5.0);
  const [socketSpacing, setSocketSpacing] = useState<number>(25.0);
  const [isGeneratingPlinth, setIsGeneratingPlinth] = useState(false);
  const [plinthResult, setPlinthResult] = useState<PlinthGenerateResult | null>(null);

  // Key Peg State
  const [pegShape, setPegShape] = useState<"cylinder" | "square">("cylinder");
  const [pegDia, setPegDia] = useState<number>(4.8);
  const [pegLength, setPegLength] = useState<number>(8.0);
  const [footOffset, setFootOffset] = useState<number>(12.0);
  const [dualPegs, setDualPegs] = useState<boolean>(true);
  const [isAddingPegs, setIsAddingPegs] = useState(false);
  const [pegResult, setPegResult] = useState<KeyPegResult | null>(null);

  // Auto-analyze COM on model load
  useEffect(() => {
    async function loadCOM() {
      if (!mesh || !projectId) return;
      try {
        setIsLoadingCOM(true);
        const data = await apiClient.analyzeFigureCOM(projectId, mesh.id);
        setComData(data);
        if (data.recommended_plinth_diameter_mm) {
          setPlinthDia(Math.max(60.0, data.recommended_plinth_diameter_mm));
        }
      } catch (err) {
        console.warn("Could not analyze COM:", err);
      } finally {
        setIsLoadingCOM(false);
      }
    }
    loadCOM();
  }, [mesh, projectId]);

  const handleGeneratePlinth = async () => {
    if (!mesh || !projectId) return;
    setIsGeneratingPlinth(true);
    setPlinthResult(null);
    try {
      const res = await apiClient.generatePlinth(projectId, mesh.id, {
        shape: plinthShape,
        diameter_mm: plinthDia,
        height_mm: plinthHeight,
        add_nameplate_recess: addNameplate,
        add_figure_sockets: addSockets,
        socket_diameter_mm: socketDia,
        socket_spacing_mm: socketSpacing,
      });
      setPlinthResult(res);
      if (onProjectRefreshed) onProjectRefreshed();
      if (onOperationRecorded) onOperationRecorded();
    } catch (err: any) {
      alert(`Plinth generation failed: ${err.message}`);
    } finally {
      setIsGeneratingPlinth(false);
    }
  };

  const handleAddKeyPegs = async () => {
    if (!mesh || !projectId) return;
    setIsAddingPegs(true);
    setPegResult(null);
    try {
      const res = await apiClient.createKeyPegs(projectId, mesh.id, {
        peg_shape: pegShape,
        peg_diameter_mm: pegDia,
        peg_length_mm: pegLength,
        foot_offset_mm: footOffset,
        dual_feet_pegs: dualPegs,
      });
      setPegResult(res);
      if (onModelUpdated) onModelUpdated(res.model_with_pegs);
      if (onOperationRecorded) onOperationRecorded();
    } catch (err: any) {
      alert(`Key peg creation failed: ${err.message}`);
    } finally {
      setIsAddingPegs(false);
    }
  };

  return (
    <div className="space-y-4 font-mono text-xs">
      {/* Header Banner */}
      <div className="p-3 bg-gradient-to-r from-emerald-950/40 via-cyan-950/30 to-slate-900 border border-emerald-500/30 rounded-lg flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <Award className="w-4 h-4 text-emerald-400" />
          <span className="font-bold text-slate-100 text-[11px] uppercase tracking-wider">
            FigureForge Studio
          </span>
        </div>
        <span className="text-[9px] px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 font-bold">
          COLLECTIBLE CAD
        </span>
      </div>

      {/* SECTION 1: CENTER OF MASS & TOPPLE STABILITY */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-lg p-3 space-y-3">
        <div className="flex items-center justify-between border-b border-slate-800 pb-2">
          <span className="text-[11px] font-bold text-slate-200 flex items-center gap-1.5">
            <Scale className="w-3.5 h-3.5 text-cyan-400" />
            <span>Center of Mass & Stability</span>
          </span>
          {comData && (
            <span className={`text-[9px] px-1.5 py-0.5 rounded font-bold flex items-center gap-1 ${
              comData.stability_status === "STABLE"
                ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                : comData.stability_status === "MARGINAL"
                ? "bg-amber-500/20 text-amber-300 border border-amber-500/30"
                : "bg-rose-500/20 text-rose-300 border border-rose-500/30"
            }`}>
              {comData.stability_status === "STABLE" && <CheckCircle2 className="w-3 h-3" />}
              {comData.stability_status === "MARGINAL" && <AlertTriangle className="w-3 h-3" />}
              {comData.stability_status === "TOPPLE_RISK" && <XCircle className="w-3 h-3" />}
              <span>{comData.stability_status.replace("_", " ")}</span>
            </span>
          )}
        </div>

        {comData ? (
          <div className="space-y-2">
            <div className="grid grid-cols-2 gap-2 text-[10px]">
              <div className="bg-slate-950 p-2 rounded border border-slate-800">
                <span className="text-slate-400 block text-[9px]">Center of Gravity (XYZ)</span>
                <span className="text-slate-100 font-bold">
                  [{comData.center_of_mass[0]}, {comData.center_of_mass[1]}, {comData.center_of_mass[2]}]
                </span>
              </div>
              <div className="bg-slate-950 p-2 rounded border border-slate-800">
                <span className="text-slate-400 block text-[9px]">Tipping Angle</span>
                <span className={`font-bold ${comData.tipping_angle_deg >= 25 ? "text-emerald-400" : "text-amber-400"}`}>
                  {comData.tipping_angle_deg}°
                </span>
              </div>
            </div>

            <p className="text-[11px] text-slate-300 leading-relaxed bg-slate-950/40 p-2 rounded border border-slate-800">
              {comData.notes}
            </p>
          </div>
        ) : (
          <div className="text-slate-500 text-center py-2">Analyzing center of gravity...</div>
        )}
      </div>

      {/* SECTION 2: PROCEDURAL DISPLAY PLINTH GENERATOR */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-lg p-3 space-y-3">
        <div className="flex items-center justify-between border-b border-slate-800 pb-2">
          <span className="text-[11px] font-bold text-slate-200 flex items-center gap-1.5">
            <Disc className="w-3.5 h-3.5 text-emerald-400" />
            <span>Display Plinth Generator</span>
          </span>
          <span className="text-[9px] text-emerald-400 font-mono">SCENE ASSET</span>
        </div>

        <div className="space-y-1.5">
          <label className="text-slate-400 text-[10px] block">Plinth Shape</label>
          <div className="grid grid-cols-3 gap-1.5">
            <button
              onClick={() => setPlinthShape("cylinder")}
              className={`py-1.5 text-[10px] rounded border transition ${
                plinthShape === "cylinder"
                  ? "bg-emerald-950 text-emerald-300 border-emerald-500"
                  : "bg-slate-950 text-slate-400 border-slate-800 hover:border-slate-700"
              }`}
            >
              Classic Round
            </button>
            <button
              onClick={() => setPlinthShape("hexagon")}
              className={`py-1.5 text-[10px] rounded border transition ${
                plinthShape === "hexagon"
                  ? "bg-emerald-950 text-emerald-300 border-emerald-500"
                  : "bg-slate-950 text-slate-400 border-slate-800 hover:border-slate-700"
              }`}
            >
              Hexagonal
            </button>
            <button
              onClick={() => setPlinthShape("stepped_round")}
              className={`py-1.5 text-[10px] rounded border transition ${
                plinthShape === "stepped_round"
                  ? "bg-emerald-950 text-emerald-300 border-emerald-500"
                  : "bg-slate-950 text-slate-400 border-slate-800 hover:border-slate-700"
              }`}
            >
              Stepped Tier
            </button>
            <button
              onClick={() => setPlinthShape("octagon")}
              className={`py-1.5 text-[10px] rounded border transition ${
                plinthShape === "octagon"
                  ? "bg-emerald-950 text-emerald-300 border-emerald-500"
                  : "bg-slate-950 text-slate-400 border-slate-800 hover:border-slate-700"
              }`}
            >
              Octagonal
            </button>
            <button
              onClick={() => setPlinthShape("square_chamfered")}
              className={`py-1.5 text-[10px] rounded border transition col-span-2 ${
                plinthShape === "square_chamfered"
                  ? "bg-emerald-950 text-emerald-300 border-emerald-500"
                  : "bg-slate-950 text-slate-400 border-slate-800 hover:border-slate-700"
              }`}
            >
              Square Museum Chamfer
            </button>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-2 text-[10px]">
          <div>
            <div className="flex justify-between">
              <span className="text-slate-400">Diameter:</span>
              <span className="text-emerald-300">{plinthDia} mm</span>
            </div>
            <input
              type="range"
              min="30"
              max="200"
              step="5"
              value={plinthDia}
              onChange={(e) => setPlinthDia(parseFloat(e.target.value))}
              className="w-full accent-emerald-400 cursor-pointer"
            />
          </div>
          <div>
            <div className="flex justify-between">
              <span className="text-slate-400">Height:</span>
              <span className="text-emerald-300">{plinthHeight} mm</span>
            </div>
            <input
              type="range"
              min="5"
              max="40"
              step="1"
              value={plinthHeight}
              onChange={(e) => setPlinthHeight(parseFloat(e.target.value))}
              className="w-full accent-emerald-400 cursor-pointer"
            />
          </div>
        </div>

        <div className="space-y-1.5 pt-1 border-t border-slate-800">
          <label className="flex items-center space-x-2 text-[11px] text-slate-300 cursor-pointer">
            <input
              type="checkbox"
              checked={addSockets}
              onChange={(e) => setAddSockets(e.target.checked)}
              className="accent-emerald-400 rounded cursor-pointer"
            />
            <span>Include Figure Foot Peg Sockets</span>
          </label>

          <label className="flex items-center space-x-2 text-[11px] text-slate-300 cursor-pointer">
            <input
              type="checkbox"
              checked={addNameplate}
              onChange={(e) => setAddNameplate(e.target.checked)}
              className="accent-emerald-400 rounded cursor-pointer"
            />
            <span>Add Nameplate Slot Recess</span>
          </label>
        </div>

        {plinthResult && (
          <div className="p-2 rounded bg-emerald-950/40 border border-emerald-500/40 text-emerald-300 text-[10px] flex items-center gap-1.5">
            <CheckCircle2 className="w-3.5 h-3.5" />
            <span>{plinthResult.message} added to scene!</span>
          </div>
        )}

        <button
          onClick={handleGeneratePlinth}
          disabled={!mesh || isGeneratingPlinth}
          className="w-full py-2 bg-gradient-to-r from-emerald-600 to-emerald-500 hover:from-emerald-500 hover:to-emerald-400 text-slate-950 font-bold rounded transition flex items-center justify-center space-x-1.5 disabled:opacity-50 cursor-pointer text-xs"
        >
          {isGeneratingPlinth ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <PlusCircle className="w-3.5 h-3.5" />}
          <span>Generate Matching Plinth</span>
        </button>
      </div>

      {/* SECTION 3: FOOT KEY-PEG MOUNTING */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-lg p-3 space-y-3">
        <div className="flex items-center justify-between border-b border-slate-800 pb-2">
          <span className="text-[11px] font-bold text-slate-200 flex items-center gap-1.5">
            <Pin className="w-3.5 h-3.5 text-cyan-400" />
            <span>Foot Key-Peg Joiner</span>
          </span>
          <span className="text-[9px] text-cyan-400 font-mono">DOWEL PEGS</span>
        </div>

        <div className="grid grid-cols-2 gap-2 text-[10px]">
          <div>
            <div className="flex justify-between">
              <span className="text-slate-400">Peg Diameter:</span>
              <span className="text-cyan-300">{pegDia} mm</span>
            </div>
            <input
              type="range"
              min="2.0"
              max="10.0"
              step="0.2"
              value={pegDia}
              onChange={(e) => setPegDia(parseFloat(e.target.value))}
              className="w-full accent-cyan-400 cursor-pointer"
            />
          </div>
          <div>
            <div className="flex justify-between">
              <span className="text-slate-400">Peg Length:</span>
              <span className="text-cyan-300">{pegLength} mm</span>
            </div>
            <input
              type="range"
              min="4.0"
              max="20.0"
              step="1.0"
              value={pegLength}
              onChange={(e) => setPegLength(parseFloat(e.target.value))}
              className="w-full accent-cyan-400 cursor-pointer"
            />
          </div>
        </div>

        <div className="space-y-1">
          <div className="flex justify-between text-[10px]">
            <span className="text-slate-400">Foot Lateral Spacing:</span>
            <span className="text-cyan-300">±{footOffset} mm</span>
          </div>
          <input
            type="range"
            min="4"
            max="40"
            step="1"
            value={footOffset}
            onChange={(e) => setFootOffset(parseFloat(e.target.value))}
            className="w-full accent-cyan-400 cursor-pointer"
          />
        </div>

        {pegResult && (
          <div className="p-2 rounded bg-cyan-950/40 border border-cyan-500/40 text-cyan-300 text-[10px] flex items-center gap-1.5">
            <CheckCircle2 className="w-3.5 h-3.5" />
            <span>Added {pegResult.pegs_added_count} mounting key-pegs!</span>
          </div>
        )}

        <button
          onClick={handleAddKeyPegs}
          disabled={!mesh || isAddingPegs}
          className="w-full py-2 bg-slate-800 hover:bg-slate-700 border border-cyan-500/40 text-cyan-300 font-bold rounded transition flex items-center justify-center space-x-1.5 disabled:opacity-50 cursor-pointer text-xs"
        >
          {isAddingPegs ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Pin className="w-3.5 h-3.5" />}
          <span>Add Foot Key-Pegs</span>
        </button>
      </div>
    </div>
  );
}
