"use client";

import React from "react";
import { 
  MousePointer, 
  Move3d, 
  Rotate3d, 
  Maximize2, 
  Scissors, 
  ScanSearch, 
  Magnet, 
  Eye, 
  Grid3X3,
  BoxSelect,
  Sparkles
} from "lucide-react";

export type CADTool = "select" | "move" | "rotate" | "scale" | "slice" | "inspect";

interface SidebarProps {
  activeTool: CADTool;
  onSelectTool: (tool: CADTool) => void;
  snapToGrid: boolean;
  onToggleSnap: () => void;
  showWireframe: boolean;
  onToggleWireframe: () => void;
  showBed: boolean;
  onToggleBed: () => void;
}

interface ToolItem {
  id: CADTool;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  hotkey: string;
  description: string;
}

const TOOLS: ToolItem[] = [
  {
    id: "select",
    label: "Select",
    icon: MousePointer,
    hotkey: "V",
    description: "Select individual mesh elements or bodies",
  },
  {
    id: "move",
    label: "Translate",
    icon: Move3d,
    hotkey: "M",
    description: "Move mesh on X/Y/Z translation axes",
  },
  {
    id: "rotate",
    label: "Rotate",
    icon: Rotate3d,
    hotkey: "R",
    description: "Rotate mesh around centroid / origin",
  },
  {
    id: "scale",
    label: "Scale",
    icon: Maximize2,
    hotkey: "S",
    description: "Uniform or non-uniform axis scaling",
  },
  {
    id: "slice",
    label: "Planar Slice",
    icon: Scissors,
    hotkey: "K",
    description: "Bisect or slice model along planar cut",
  },
  {
    id: "inspect",
    label: "Mesh Inspect",
    icon: ScanSearch,
    hotkey: "I",
    description: "Analyze non-manifold edges, volume & normals",
  },
];

export function Sidebar({
  activeTool,
  onSelectTool,
  snapToGrid,
  onToggleSnap,
  showWireframe,
  onToggleWireframe,
  showBed,
  onToggleBed,
}: SidebarProps) {
  return (
    <aside className="w-16 bg-slate-950/80 backdrop-blur-md border-r border-slate-800/80 flex flex-col items-center py-3 justify-between z-40 select-none">
      {/* CAD Transformation Tools */}
      <div className="flex flex-col items-center space-y-2 w-full px-2">
        <div className="text-[9px] font-mono font-bold text-slate-500 uppercase tracking-widest mb-1">
          Tools
        </div>
        {TOOLS.map((tool) => {
          const Icon = tool.icon;
          const isActive = activeTool === tool.id;

          return (
            <button
              key={tool.id}
              onClick={() => onSelectTool(tool.id)}
              title={`${tool.label} (${tool.hotkey}) - ${tool.description}`}
              className={`relative group w-11 h-11 rounded-lg flex flex-col items-center justify-center transition-all ${
                isActive
                  ? "bg-cyan-500/15 text-cyan-300 border border-cyan-500/50 shadow-glow-cyan"
                  : "text-slate-400 hover:text-slate-100 hover:bg-slate-900 border border-transparent"
              }`}
            >
              <Icon className={`w-5 h-5 ${isActive ? "stroke-[2.2]" : "stroke-[1.8]"}`} />
              <span className="text-[9px] font-mono mt-0.5 leading-none">
                {tool.label.slice(0, 4)}
              </span>

              {/* Hotkey badge */}
              <span className="absolute top-1 right-1 text-[8px] font-mono text-slate-500 group-hover:text-slate-300 opacity-80">
                {tool.hotkey}
              </span>

              {/* Active indicator bar */}
              {isActive && (
                <div className="absolute left-0 top-2 bottom-2 w-[2.5px] bg-cyan-400 rounded-r shadow-glow-cyan" />
              )}
            </button>
          );
        })}
      </div>

      {/* Viewport & Snapping Toggles */}
      <div className="flex flex-col items-center space-y-2 w-full px-2 pt-3 border-t border-slate-800/80">
        <div className="text-[9px] font-mono font-bold text-slate-500 uppercase tracking-widest mb-0.5">
          Toggles
        </div>

        {/* Snap to grid */}
        <button
          onClick={onToggleSnap}
          title={`Snap to Grid (${snapToGrid ? "ON" : "OFF"})`}
          className={`w-11 h-10 rounded-lg flex flex-col items-center justify-center transition-all ${
            snapToGrid
              ? "bg-amber-500/15 text-amber-400 border border-amber-500/40"
              : "text-slate-500 hover:text-slate-300 hover:bg-slate-900"
          }`}
        >
          <Magnet className="w-4 h-4" />
          <span className="text-[8px] font-mono mt-0.5">SNAP</span>
        </button>

        {/* Wireframe toggle */}
        <button
          onClick={onToggleWireframe}
          title={`Wireframe Overlay (${showWireframe ? "ON" : "OFF"})`}
          className={`w-11 h-10 rounded-lg flex flex-col items-center justify-center transition-all ${
            showWireframe
              ? "bg-cyan-500/15 text-cyan-400 border border-cyan-500/40"
              : "text-slate-500 hover:text-slate-300 hover:bg-slate-900"
          }`}
        >
          <Grid3X3 className="w-4 h-4" />
          <span className="text-[8px] font-mono mt-0.5">MESH</span>
        </button>

        {/* Bed Bounds Toggle */}
        <button
          onClick={onToggleBed}
          title={`Print Bed Boundary (${showBed ? "ON" : "OFF"})`}
          className={`w-11 h-10 rounded-lg flex flex-col items-center justify-center transition-all ${
            showBed
              ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/40"
              : "text-slate-500 hover:text-slate-300 hover:bg-slate-900"
          }`}
        >
          <BoxSelect className="w-4 h-4" />
          <span className="text-[8px] font-mono mt-0.5">BED</span>
        </button>
      </div>
    </aside>
  );
}
