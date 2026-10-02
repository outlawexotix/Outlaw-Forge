"use client";

import React, { useState, useEffect } from "react";
import {
  WorkingModel,
  MaskFitAnalysis,
  HeadSizePreset,
  MagnetPreset,
  MagnetPlacementMode,
  StrapPreset,
  MagnetSocketPunchResult,
  StrapSlotPunchResult,
} from "@shared/types/api";
import { apiClient } from "@/lib/api-client";
import {
  Sparkles,
  Shield,
  Magnet,
  Maximize2,
  Sliders,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Layers,
  ArrowRight,
  Crosshair,
  Ruler,
} from "lucide-react";

interface MaskSmithStudioProps {
  projectId: string;
  mesh: WorkingModel | null;
  onModelUpdated?: (updated: WorkingModel) => void;
  onOperationRecorded?: () => void;
}

export function MaskSmithStudio({
  projectId,
  mesh,
  onModelUpdated,
  onOperationRecorded,
}: MaskSmithStudioProps) {
  // Wearable Sizing State
  const [headPreset, setHeadPreset] = useState<HeadSizePreset>("Adult Male (L/XL - 155mm)");
  const [paddingClearance, setPaddingClearance] = useState<number>(8.0);
  const [customWidth, setCustomWidth] = useState<number>(155.0);
  const [fitAnalysis, setFitAnalysis] = useState<MaskFitAnalysis | null>(null);
  const [isLoadingAnalysis, setIsLoadingAnalysis] = useState(false);
  const [isScaling, setIsScaling] = useState(false);
  const [scaleSuccessMsg, setScaleSuccessMsg] = useState<string | null>(null);

  // Magnet Sockets State
  const [magnetPreset, setMagnetPreset] = useState<MagnetPreset>("8x3mm (D:8mm, H:3mm)");
  const [customMagnetDia, setCustomMagnetDia] = useState<number>(8.0);
  const [customMagnetDepth, setCustomMagnetDepth] = useState<number>(3.0);
  const [magnetClearance, setMagnetClearance] = useState<number>(0.15);
  const [magnetPlacement, setMagnetPlacement] = useState<MagnetPlacementMode>("perimeter_4_corner");
  const [magnetInset, setMagnetInset] = useState<number>(6.0);
  const [isPunchingMagnets, setIsPunchingMagnets] = useState(false);
  const [magnetResult, setMagnetResult] = useState<MagnetSocketPunchResult | null>(null);

  // Strap Slots State
  const [strapPreset, setStrapPreset] = useState<StrapPreset>("25mm (1in) Tactical Webbing");
  const [strapPlacement, setStrapPlacement] = useState<"temple_bilateral" | "crown_and_temple_3point">("temple_bilateral");
  const [strapInset, setStrapInset] = useState<number>(12.0);
  const [isPunchingStraps, setIsPunchingStraps] = useState(false);
  const [strapResult, setStrapResult] = useState<StrapSlotPunchResult | null>(null);

  // Auto-analyze mask fit on model load
  useEffect(() => {
    async function loadAnalysis() {
      if (!mesh || !projectId) return;
      try {
        setIsLoadingAnalysis(true);
        const data = await apiClient.analyzeMaskFit(projectId, mesh.id);
        setFitAnalysis(data);
      } catch (err) {
        console.warn("Could not fetch mask analysis:", err);
      } finally {
        setIsLoadingAnalysis(false);
      }
    }
    loadAnalysis();
  }, [mesh?.id, projectId]);

  const handleFitScale = async () => {
    if (!mesh || !projectId) return;
    setIsScaling(true);
    setScaleSuccessMsg(null);
    try {
      const updated = await apiClient.autoScaleMask(projectId, mesh.id, {
        target_preset: headPreset,
        target_inner_width_mm: headPreset === "Custom" ? customWidth : undefined,
        padding_clearance_mm: paddingClearance,
        uniform_scale: true,
      });
      if (onModelUpdated) onModelUpdated(updated);
      if (onOperationRecorded) onOperationRecorded();
      setScaleSuccessMsg(`Mask successfully scaled for ${headPreset}!`);
      setTimeout(() => setScaleSuccessMsg(null), 4000);
      const data = await apiClient.analyzeMaskFit(projectId, updated.id);
      setFitAnalysis(data);
    } catch (err: any) {
      alert(`Mask fit scaling failed: ${err.message}`);
    } finally {
      setIsScaling(false);
    }
  };

  const handlePunchMagnets = async () => {
    if (!mesh || !projectId) return;
    setIsPunchingMagnets(true);
    setMagnetResult(null);
    try {
      const res = await apiClient.punchMagnetSockets(projectId, mesh.id, {
        magnet_preset: magnetPreset,
        custom_diameter_mm: magnetPreset === "Custom" ? customMagnetDia : undefined,
        custom_depth_mm: magnetPreset === "Custom" ? customMagnetDepth : undefined,
        clearance_tolerance_mm: magnetClearance,
        placement_mode: magnetPlacement,
        margin_inset_mm: magnetInset,
      });
      setMagnetResult(res);
      if (onModelUpdated) onModelUpdated(res.model);
      if (onOperationRecorded) onOperationRecorded();
    } catch (err: any) {
      alert(`Magnet punching failed: ${err.message}`);
    } finally {
      setIsPunchingMagnets(false);
    }
  };

  const handlePunchStraps = async () => {
    if (!mesh || !projectId) return;
    setIsPunchingStraps(true);
    setStrapResult(null);
    try {
      const res = await apiClient.punchStrapSlots(projectId, mesh.id, {
        strap_preset: strapPreset,
        placement: strapPlacement,
        inset_from_edge_mm: strapInset,
      });
      setStrapResult(res);
      if (onModelUpdated) onModelUpdated(res.model);
      if (onOperationRecorded) onOperationRecorded();
    } catch (err: any) {
      alert(`Strap slot punching failed: ${err.message}`);
    } finally {
      setIsPunchingStraps(false);
    }
  };

  return (
    <div className="space-y-4 font-mono text-xs">
      {/* Header Banner */}
      <div className="p-3 bg-gradient-to-r from-amber-950/40 via-purple-950/30 to-slate-900 border border-amber-500/30 rounded-lg flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <Shield className="w-4 h-4 text-amber-400" />
          <span className="font-bold text-slate-100 text-[11px] uppercase tracking-wider">
            MaskSmith Studio
          </span>
        </div>
        <span className="text-[9px] px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30 font-bold">
          WEARABLE CAD
        </span>
      </div>

      {/* SECTION 1: ANTHROPOMETRIC FIT & WEARABLE CALIPER */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-lg p-3 space-y-3">
        <div className="flex items-center justify-between border-b border-slate-800 pb-2">
          <span className="text-[11px] font-bold text-slate-200 flex items-center gap-1.5">
            <Ruler className="w-3.5 h-3.5 text-cyan-400" />
            <span>Anthropometric Head Fit</span>
          </span>
          {fitAnalysis && (
            <span className={`text-[9px] px-1.5 py-0.5 rounded font-bold ${
              fitAnalysis.is_wearable_scale
                ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                : "bg-amber-500/20 text-amber-300 border border-amber-500/30"
            }`}>
              {fitAnalysis.is_wearable_scale ? "WEARABLE SCALE" : "DISPLAY / MINI"}
            </span>
          )}
        </div>

        {fitAnalysis && (
          <div className="grid grid-cols-3 gap-2 text-[10px]">
            <div className="bg-slate-950 p-2 rounded border border-slate-800">
              <span className="text-slate-400 block text-[9px]">Temple Width</span>
              <span className="text-slate-100 font-bold">{fitAnalysis.inner_width_mm} mm</span>
            </div>
            <div className="bg-slate-950 p-2 rounded border border-slate-800">
              <span className="text-slate-400 block text-[9px]">Face Depth</span>
              <span className="text-slate-100 font-bold">{fitAnalysis.inner_depth_mm} mm</span>
            </div>
            <div className="bg-slate-950 p-2 rounded border border-slate-800">
              <span className="text-slate-400 block text-[9px]">Crown Height</span>
              <span className="text-slate-100 font-bold">{fitAnalysis.inner_height_mm} mm</span>
            </div>
          </div>
        )}

        <div className="space-y-1.5">
          <label className="text-slate-400 text-[10px] block">Target Head Size Profile</label>
          <select
            value={headPreset}
            onChange={(e) => setHeadPreset(e.target.value as HeadSizePreset)}
            className="w-full bg-slate-950 border border-slate-700 rounded px-2.5 py-1.5 text-slate-100 text-xs focus:outline-none focus:border-amber-400"
          >
            <option value="Adult Male (L/XL - 155mm)">Adult Male (L/XL - 155mm Temple Width)</option>
            <option value="Adult Male (M - 150mm)">Adult Male (Medium - 150mm Temple Width)</option>
            <option value="Adult Female (M - 145mm)">Adult Female (Medium - 145mm Temple Width)</option>
            <option value="Adult Female (S - 140mm)">Adult Female (Small - 140mm Temple Width)</option>
            <option value="Youth (130mm)">Youth (130mm Temple Width)</option>
            <option value="Child (120mm)">Child (120mm Temple Width)</option>
            <option value="Custom">Custom Width</option>
          </select>
        </div>

        {headPreset === "Custom" && (
          <div className="space-y-1">
            <label className="text-slate-400 text-[10px] block">Custom Temple Width (mm)</label>
            <input
              type="number"
              min="80"
              max="250"
              value={customWidth}
              onChange={(e) => setCustomWidth(parseFloat(e.target.value) || 150)}
              className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1 text-slate-100 text-xs"
            />
          </div>
        )}

        <div className="space-y-1">
          <div className="flex justify-between text-[10px]">
            <span className="text-slate-400">Comfort Foam Clearance:</span>
            <span className="text-amber-300 font-bold">{paddingClearance} mm</span>
          </div>
          <input
            type="range"
            min="0"
            max="20"
            step="1"
            value={paddingClearance}
            onChange={(e) => setPaddingClearance(parseFloat(e.target.value))}
            className="w-full accent-amber-400 cursor-pointer"
          />
        </div>

        {scaleSuccessMsg && (
          <div className="p-2 rounded bg-emerald-950/40 border border-emerald-500/40 text-emerald-300 text-[10px] flex items-center gap-1.5">
            <CheckCircle2 className="w-3.5 h-3.5" />
            <span>{scaleSuccessMsg}</span>
          </div>
        )}

        <button
          onClick={handleFitScale}
          disabled={!mesh || isScaling}
          className="w-full py-2 bg-gradient-to-r from-amber-600 to-amber-500 hover:from-amber-500 hover:to-amber-400 text-slate-950 font-bold rounded transition flex items-center justify-center space-x-1.5 disabled:opacity-50 cursor-pointer text-xs"
        >
          {isScaling ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Maximize2 className="w-3.5 h-3.5" />}
          <span>Auto-Scale Mask for Head Size</span>
        </button>
      </div>

      {/* SECTION 2: NEODYMIUM MAGNET SOCKET PUNCHER */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-lg p-3 space-y-3">
        <div className="flex items-center justify-between border-b border-slate-800 pb-2">
          <span className="text-[11px] font-bold text-slate-200 flex items-center gap-1.5">
            <Magnet className="w-3.5 h-3.5 text-cyan-400" />
            <span>Neodymium Magnet Sockets</span>
          </span>
          <span className="text-[9px] text-cyan-400 font-mono">PRESS-FIT</span>
        </div>

        <div className="space-y-1.5">
          <label className="text-slate-400 text-[10px] block">Magnet Size Preset</label>
          <select
            value={magnetPreset}
            onChange={(e) => setMagnetPreset(e.target.value as MagnetPreset)}
            className="w-full bg-slate-950 border border-slate-700 rounded px-2.5 py-1 text-slate-100 text-xs focus:outline-none focus:border-cyan-400"
          >
            <option value="6x3mm (D:6mm, H:3mm)">6×3 mm Disc (Compact)</option>
            <option value="8x3mm (D:8mm, H:3mm)">8×3 mm Disc (Standard N52 Cosplay)</option>
            <option value="10x3mm (D:10mm, H:3mm)">10×3 mm Disc (High-Strength Hold)</option>
            <option value="12x3mm (D:12mm, H:3mm)">12×3 mm Disc (Heavy Armor / Shield)</option>
            <option value="6x2mm (D:6mm, H:2mm)">6×2 mm Disc (Slim Profile)</option>
            <option value="8x2mm (D:8mm, H:2mm)">8×2 mm Disc (Slim Faceplate)</option>
            <option value="10x2mm (D:10mm, H:2mm)">10×2 mm Disc (Slim High-Strength)</option>
            <option value="Custom">Custom Magnet Dimensions</option>
          </select>
        </div>

        {magnetPreset === "Custom" && (
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="text-[9px] text-slate-400 block">Diameter (mm)</label>
              <input
                type="number"
                min="2"
                max="25"
                value={customMagnetDia}
                onChange={(e) => setCustomMagnetDia(parseFloat(e.target.value) || 8)}
                className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-0.5 text-slate-100 text-xs"
              />
            </div>
            <div>
              <label className="text-[9px] text-slate-400 block">Depth (mm)</label>
              <input
                type="number"
                min="1"
                max="15"
                value={customMagnetDepth}
                onChange={(e) => setCustomMagnetDepth(parseFloat(e.target.value) || 3)}
                className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-0.5 text-slate-100 text-xs"
              />
            </div>
          </div>
        )}

        <div className="space-y-1.5">
          <label className="text-slate-400 text-[10px] block">Placement Pattern</label>
          <select
            value={magnetPlacement}
            onChange={(e) => setMagnetPlacement(e.target.value as MagnetPlacementMode)}
            className="w-full bg-slate-950 border border-slate-700 rounded px-2.5 py-1 text-slate-100 text-xs focus:outline-none focus:border-cyan-400"
          >
            <option value="perimeter_4_corner">4-Corner Perimeter (Temples + Jaw)</option>
            <option value="perimeter_6_point">6-Point Perimeter (Crown, Temples, Cheeks, Jaw)</option>
            <option value="split_seam_flange">Split Seam Flange (2-Piece Faceplate)</option>
          </select>
        </div>

        <div className="grid grid-cols-2 gap-2 text-[10px]">
          <div>
            <div className="flex justify-between">
              <span className="text-slate-400">Clearance:</span>
              <span className="text-cyan-300">{magnetClearance} mm</span>
            </div>
            <input
              type="range"
              min="0.05"
              max="0.4"
              step="0.05"
              value={magnetClearance}
              onChange={(e) => setMagnetClearance(parseFloat(e.target.value))}
              className="w-full accent-cyan-400 cursor-pointer"
            />
          </div>
          <div>
            <div className="flex justify-between">
              <span className="text-slate-400">Edge Inset:</span>
              <span className="text-cyan-300">{magnetInset} mm</span>
            </div>
            <input
              type="range"
              min="2"
              max="20"
              step="1"
              value={magnetInset}
              onChange={(e) => setMagnetInset(parseFloat(e.target.value))}
              className="w-full accent-cyan-400 cursor-pointer"
            />
          </div>
        </div>

        {magnetResult && (
          <div className="p-2 rounded bg-cyan-950/40 border border-cyan-500/40 text-cyan-300 text-[10px] flex items-center gap-1.5">
            <CheckCircle2 className="w-3.5 h-3.5" />
            <span>Punched {magnetResult.sockets_punched} magnet sockets!</span>
          </div>
        )}

        <button
          onClick={handlePunchMagnets}
          disabled={!mesh || isPunchingMagnets}
          className="w-full py-2 bg-slate-800 hover:bg-slate-700 border border-cyan-500/40 text-cyan-300 font-bold rounded transition flex items-center justify-center space-x-1.5 disabled:opacity-50 cursor-pointer text-xs"
        >
          {isPunchingMagnets ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Magnet className="w-3.5 h-3.5" />}
          <span>Punch Neodymium Sockets</span>
        </button>
      </div>

      {/* SECTION 3: STRAP WEBBING SLOTS */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-lg p-3 space-y-3">
        <div className="flex items-center justify-between border-b border-slate-800 pb-2">
          <span className="text-[11px] font-bold text-slate-200 flex items-center gap-1.5">
            <Layers className="w-3.5 h-3.5 text-purple-400" />
            <span>Strap Webbing Slots</span>
          </span>
          <span className="text-[9px] text-purple-400 font-mono">HARNESS</span>
        </div>

        <div className="space-y-1.5">
          <label className="text-slate-400 text-[10px] block">Elastic / Webbing Width</label>
          <select
            value={strapPreset}
            onChange={(e) => setStrapPreset(e.target.value as StrapPreset)}
            className="w-full bg-slate-950 border border-slate-700 rounded px-2.5 py-1 text-slate-100 text-xs focus:outline-none focus:border-purple-400"
          >
            <option value="15mm Elastic Band">15mm Elastic Band (Lightweight)</option>
            <option value="20mm (3/4in) Webbing">20mm (3/4&quot;) Webbing</option>
            <option value="25mm (1in) Tactical Webbing">25mm (1&quot;) Tactical Webbing (Standard)</option>
            <option value="38mm (1.5in) Heavy Duty Webbing">38mm (1.5&quot;) Heavy Duty Harness</option>
          </select>
        </div>

        <div className="space-y-1.5">
          <label className="text-slate-400 text-[10px] block">Slot Placement</label>
          <select
            value={strapPlacement}
            onChange={(e) => setStrapPlacement(e.target.value as any)}
            className="w-full bg-slate-950 border border-slate-700 rounded px-2.5 py-1 text-slate-100 text-xs focus:outline-none focus:border-purple-400"
          >
            <option value="temple_bilateral">Bilateral Temples (2-Point Horizontal Strap)</option>
            <option value="crown_and_temple_3point">3-Point Y-Harness (Crown + Temples)</option>
          </select>
        </div>

        <div className="space-y-1">
          <div className="flex justify-between text-[10px]">
            <span className="text-slate-400">Inset From Edge:</span>
            <span className="text-purple-300">{strapInset} mm</span>
          </div>
          <input
            type="range"
            min="5"
            max="30"
            step="1"
            value={strapInset}
            onChange={(e) => setStrapInset(parseFloat(e.target.value))}
            className="w-full accent-purple-400 cursor-pointer"
          />
        </div>

        {strapResult && (
          <div className="p-2 rounded bg-purple-950/40 border border-purple-500/40 text-purple-300 text-[10px] flex items-center gap-1.5">
            <CheckCircle2 className="w-3.5 h-3.5" />
            <span>Punched {strapResult.slots_punched} strap slots ({strapResult.slot_width_mm}mm)!</span>
          </div>
        )}

        <button
          onClick={handlePunchStraps}
          disabled={!mesh || isPunchingStraps}
          className="w-full py-2 bg-slate-800 hover:bg-slate-700 border border-purple-500/40 text-purple-300 font-bold rounded transition flex items-center justify-center space-x-1.5 disabled:opacity-50 cursor-pointer text-xs"
        >
          {isPunchingStraps ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Layers className="w-3.5 h-3.5" />}
          <span>Punch Strap Slots</span>
        </button>
      </div>
    </div>
  );
}
