'use client';

import React, { useState, useEffect, useRef } from 'react';
import {
  Play,
  Pause,
  SkipBack,
  SkipForward,
  Layers,
  Eye,
  Sliders,
  Sparkles,
  Zap,
  Activity,
  X,
} from 'lucide-react';
import { ParsedGCodeData } from './ToolpathRenderer';

interface ToolpathControllerProps {
  data: ParsedGCodeData | null;
  currentLayer: number;
  onLayerChange: (layer: number) => void;
  showSingleLayer: boolean;
  onToggleSingleLayer: (single: boolean) => void;
  showTravel: boolean;
  onToggleTravel: (show: boolean) => void;
  showOuterWall: boolean;
  onToggleOuterWall: (show: boolean) => void;
  showInnerWall: boolean;
  onToggleInnerWall: (show: boolean) => void;
  showInfill: boolean;
  onToggleInfill: (show: boolean) => void;
  showSupport: boolean;
  onToggleSupport: (show: boolean) => void;
  onClose?: () => void;
}

export const ToolpathController: React.FC<ToolpathControllerProps> = ({
  data,
  currentLayer,
  onLayerChange,
  showSingleLayer,
  onToggleSingleLayer,
  showTravel,
  onToggleTravel,
  showOuterWall,
  onToggleOuterWall,
  showInnerWall,
  onToggleInnerWall,
  showInfill,
  onToggleInfill,
  showSupport,
  onToggleSupport,
  onClose,
}) => {
  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackSpeed, setPlaybackSpeed] = useState<number>(1); // 1x, 2x, 5x, 10x
  const [showFeatureFilters, setShowFeatureFilters] = useState(false);

  const totalLayers = data?.totalLayers || 1;
  const currentZ = data?.layers[Math.min(currentLayer, totalLayers - 1)]?.zHeight || 0;
  const currentLayerData = data?.layers[Math.min(currentLayer, totalLayers - 1)];

  // Playback timer loop
  useEffect(() => {
    if (!isPlaying) return;

    const intervalMs = Math.max(50, 400 / playbackSpeed);
    const interval = setInterval(() => {
      onLayerChange(currentLayer >= totalLayers - 1 ? 0 : currentLayer + 1);
    }, intervalMs);

    return () => clearInterval(interval);
  }, [isPlaying, currentLayer, totalLayers, playbackSpeed, onLayerChange]);

  const handleSliderChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = parseInt(e.target.value, 10);
    onLayerChange(val);
  };

  const handleStepBack = () => {
    setIsPlaying(false);
    onLayerChange(Math.max(0, currentLayer - 1));
  };

  const handleStepForward = () => {
    setIsPlaying(false);
    onLayerChange(Math.min(totalLayers - 1, currentLayer + 1));
  };

  return (
    <div className="absolute bottom-16 left-1/2 -translate-x-1/2 z-30 flex flex-col items-center gap-1.5 w-[92%] max-w-2xl animate-in fade-in slide-in-from-bottom-2 duration-200">
      {/* Feature Visibility Sub-Bar */}
      {showFeatureFilters && (
        <div className="flex items-center gap-2 px-3 py-1.5 bg-slate-950/95 backdrop-blur-md border border-slate-800 rounded-lg shadow-2xl text-[11px] font-mono text-slate-300 animate-in fade-in duration-150">
          <span className="text-slate-500 font-bold uppercase tracking-wider text-[10px]">Filter:</span>
          
          <button
            onClick={() => onToggleOuterWall(!showOuterWall)}
            className={`flex items-center gap-1 px-2 py-0.5 rounded transition ${
              showOuterWall ? 'bg-cyan-950 text-cyan-300 border border-cyan-500/50' : 'text-slate-500 hover:text-slate-300'
            }`}
          >
            <span className="w-2 h-2 rounded-full bg-[#06b6d4]" />
            Outer Wall
          </button>

          <button
            onClick={() => onToggleInnerWall(!showInnerWall)}
            className={`flex items-center gap-1 px-2 py-0.5 rounded transition ${
              showInnerWall ? 'bg-blue-950 text-blue-300 border border-blue-500/50' : 'text-slate-500 hover:text-slate-300'
            }`}
          >
            <span className="w-2 h-2 rounded-full bg-[#3b82f6]" />
            Inner Wall
          </button>

          <button
            onClick={() => onToggleInfill(!showInfill)}
            className={`flex items-center gap-1 px-2 py-0.5 rounded transition ${
              showInfill ? 'bg-amber-950 text-amber-300 border border-amber-500/50' : 'text-slate-500 hover:text-slate-300'
            }`}
          >
            <span className="w-2 h-2 rounded-full bg-[#f59e0b]" />
            Infill
          </button>

          <button
            onClick={() => onToggleSupport(!showSupport)}
            className={`flex items-center gap-1 px-2 py-0.5 rounded transition ${
              showSupport ? 'bg-emerald-950 text-emerald-300 border border-emerald-500/50' : 'text-slate-500 hover:text-slate-300'
            }`}
          >
            <span className="w-2 h-2 rounded-full bg-[#10b981]" />
            Support
          </button>

          <button
            onClick={() => onToggleTravel(!showTravel)}
            className={`flex items-center gap-1 px-2 py-0.5 rounded transition ${
              showTravel ? 'bg-slate-800 text-slate-200 border border-slate-600' : 'text-slate-500 hover:text-slate-300'
            }`}
          >
            <span className="w-2 h-2 rounded-full bg-[#64748b]" />
            Travel Moves
          </button>
        </div>
      )}

      {/* Main Toolpath Playback Bar */}
      <div className="w-full flex items-center justify-between gap-3 px-4 py-2 bg-slate-950/95 backdrop-blur-md border border-cyan-500/40 rounded-xl shadow-glow-cyan text-xs font-mono text-slate-200">
        {/* Playback Controls */}
        <div className="flex items-center gap-1.5 shrink-0">
          <button
            onClick={() => onLayerChange(0)}
            title="Jump to Start (Layer 0)"
            className="p-1.5 hover:bg-slate-800 rounded text-slate-400 hover:text-slate-100 transition"
          >
            <SkipBack className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={handleStepBack}
            title="Previous Layer"
            className="px-1.5 py-1 hover:bg-slate-800 rounded text-slate-300 hover:text-cyan-300 transition text-[11px]"
          >
            -1
          </button>
          <button
            onClick={() => setIsPlaying(!isPlaying)}
            title={isPlaying ? 'Pause Simulation' : 'Play Toolpath Simulation'}
            className={`p-2 rounded-lg transition ${
              isPlaying
                ? 'bg-amber-500 text-slate-950 font-bold shadow-glow-amber'
                : 'bg-cyan-500 text-slate-950 font-bold shadow-glow-cyan hover:bg-cyan-400'
            }`}
          >
            {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4 ml-0.5" />}
          </button>
          <button
            onClick={handleStepForward}
            title="Next Layer"
            className="px-1.5 py-1 hover:bg-slate-800 rounded text-slate-300 hover:text-cyan-300 transition text-[11px]"
          >
            +1
          </button>
          <button
            onClick={() => onLayerChange(totalLayers - 1)}
            title="Jump to Top Layer"
            className="p-1.5 hover:bg-slate-800 rounded text-slate-400 hover:text-slate-100 transition"
          >
            <SkipForward className="w-3.5 h-3.5" />
          </button>
        </div>

        {/* Layer Slider & Info */}
        <div className="flex-1 flex flex-col gap-1 px-2">
          <div className="flex items-center justify-between text-[11px]">
            <div className="flex items-center gap-2">
              <span className="text-cyan-300 font-bold">
                Layer {currentLayer + 1} <span className="text-slate-500 font-normal">/ {totalLayers}</span>
              </span>
              <span className="text-slate-400">
                (Z: <span className="text-slate-200 font-semibold">{currentZ.toFixed(2)} mm</span>)
              </span>
            </div>
            {currentLayerData && (
              <span className="text-slate-400 text-[10px]">
                {currentLayerData.segmentCount} moves | {(currentLayerData.extrusionLengthMm / 10).toFixed(1)} cm filament
              </span>
            )}
          </div>

          {/* Slider input */}
          <input
            type="range"
            min={0}
            max={Math.max(0, totalLayers - 1)}
            value={Math.min(currentLayer, totalLayers - 1)}
            onChange={handleSliderChange}
            className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-cyan-400 hover:accent-cyan-300 focus:outline-none"
          />
        </div>

        {/* Toggles & Options */}
        <div className="flex items-center gap-1.5 shrink-0 text-[11px]">
          {/* Speed Selector */}
          <div className="flex items-center bg-slate-900 border border-slate-700/70 rounded p-0.5">
            {[1, 2, 5, 10].map((spd) => (
              <button
                key={spd}
                onClick={() => setPlaybackSpeed(spd)}
                className={`px-1.5 py-0.5 text-[10px] rounded transition ${
                  playbackSpeed === spd
                    ? 'bg-cyan-600 text-white font-bold'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                {spd}x
              </button>
            ))}
          </div>

          {/* Single Layer Mode Toggle */}
          <button
            onClick={() => onToggleSingleLayer(!showSingleLayer)}
            title="Toggle Single Layer View vs Accumulated Layers"
            className={`px-2 py-1 rounded border transition ${
              showSingleLayer
                ? 'bg-purple-950 text-purple-300 border-purple-500/60'
                : 'bg-slate-900 text-slate-400 border-slate-700/60 hover:text-slate-200'
            }`}
          >
            {showSingleLayer ? '1 Layer' : 'All <= Z'}
          </button>

          {/* Filter Dropdown Toggle */}
          <button
            onClick={() => setShowFeatureFilters(!showFeatureFilters)}
            title="Toggle Feature Color Filters"
            className={`p-1.5 rounded border transition ${
              showFeatureFilters
                ? 'bg-cyan-950 text-cyan-300 border-cyan-500/60'
                : 'bg-slate-900 text-slate-400 border-slate-700/60 hover:text-slate-200'
            }`}
          >
            <Sliders className="w-3.5 h-3.5" />
          </button>

          {/* Close toolpath simulation */}
          {onClose && (
            <button
              onClick={onClose}
              title="Close G-code Toolpath Simulation"
              className="p-1.5 hover:bg-slate-800 rounded text-slate-500 hover:text-rose-400 transition ml-1"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
