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
  Grid3X3,
  BoxSelect,
  Sparkles
} from "lucide-react";

export type CADTool = "select" | "move" | "rotate" | "scale" | "slice" | "inspect" | "lay_flat";

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
    description: "Select mesh bodies and instances",
  },
  {
    id: "move",
    label: "Translate",
    icon: Move3d,
    hotkey: "M",
    description: "Translate mesh along X, Y, Z axes",
  },
  {
    id: "rotate",
    label: "Rotate",
    icon: Rotate3d,
    hotkey: "R",
    description: "Rotate mesh around centroid",
  },
  {
    id: "scale",
    label: "Scale",
    icon: Maximize2,
    hotkey: "S",
    description: "Uniform or per-axis scaling",
  },
  {
    id: "lay_flat",
    label: "Lay Face",
    icon: Sparkles,
    hotkey: "L",
    description: "Click any facet to align flush on build plate",
  },
  {
    id: "slice",
    label: "Planar Cut",
    icon: Scissors,
    hotkey: "K",
    description: "Planar bisect and slice tool",
  },
  {
    id: "inspect",
    label: "Inspect",
    icon: ScanSearch,
    hotkey: "I",
    description: "Overhang, volume, and wall inspection",
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
    <aside className="w-14 bg-neutral-950 border-r border-neutral-800 flex flex-col items-center py-2 justify-between z-40 select-none">
      {/* CAD Transformation Tools */}
      <div className="flex flex-col items-center space-y-1.5 w-full px-1.5">
        <div className="text-[8px] font-mono font-bold text-neutral-500 uppercase tracking-widest mb-0.5">
          CAD
        </div>
        {TOOLS.map((tool) => {
          const Icon = tool.icon;
          const isActive = activeTool === tool.id;

          return (
            <button
              key={tool.id}
              onClick={() => onSelectTool(tool.id)}
              title={`${tool.label} [${tool.hotkey}] - ${tool.description}`}
              className={`relative group w-11 h-10 rounded flex flex-col items-center justify-center transition-all ${
                isActive
                  ? "bg-amber-500/10 text-amber-400 border border-amber-500/50"
                  : "text-neutral-400 hover:text-neutral-100 hover:bg-neutral-900 border border-transparent"
              }`}
            >
              <Icon className={`w-4 h-4 ${isActive ? "stroke-[2.2] text-amber-400" : "stroke-[1.8]"}`} />
              <span className="text-[8px] font-mono mt-0.5 leading-none">
                {tool.label.slice(0, 4)}
              </span>

              {/* Hotkey badge */}
              <span className="absolute top-0.5 right-1 text-[7px] font-mono text-neutral-500 group-hover:text-neutral-300">
                {tool.hotkey}
              </span>

              {/* Active indicator bar */}
              {isActive && (
                <div className="absolute left-0 top-1.5 bottom-1.5 w-[2px] bg-amber-500 rounded-r" />
              )}
            </button>
          );
        })}
      </div>

      {/* Viewport Toggles */}
      <div className="flex flex-col items-center space-y-1 w-full px-1.5 pt-2 border-t border-neutral-800">
        <div className="text-[8px] font-mono font-bold text-neutral-500 uppercase tracking-widest mb-0.5">
          VIEW
        </div>

        {/* Snap to grid */}
        <button
          onClick={onToggleSnap}
          title={`Snap to Grid (${snapToGrid ? "ON" : "OFF"})`}
          className={`w-11 h-8 rounded flex flex-col items-center justify-center transition-all ${
            snapToGrid
              ? "bg-amber-500/10 text-amber-400 border border-amber-500/40"
              : "text-neutral-500 hover:text-neutral-300 hover:bg-neutral-900"
          }`}
        >
          <Magnet className="w-3.5 h-3.5" />
          <span className="text-[7px] font-mono">SNAP</span>
        </button>

        {/* Wireframe toggle */}
        <button
          onClick={onToggleWireframe}
          title={`Wireframe Overlay (${showWireframe ? "ON" : "OFF"})`}
          className={`w-11 h-8 rounded flex flex-col items-center justify-center transition-all ${
            showWireframe
              ? "bg-neutral-800 text-neutral-200 border border-neutral-700"
              : "text-neutral-500 hover:text-neutral-300 hover:bg-neutral-900"
          }`}
        >
          <Grid3X3 className="w-3.5 h-3.5" />
          <span className="text-[7px] font-mono">WIRE</span>
        </button>

        {/* Bed Bounds Toggle */}
        <button
          onClick={onToggleBed}
          title={`Print Bed Boundary (${showBed ? "ON" : "OFF"})`}
          className={`w-11 h-8 rounded flex flex-col items-center justify-center transition-all ${
            showBed
              ? "bg-neutral-800 text-neutral-200 border border-neutral-700"
              : "text-neutral-500 hover:text-neutral-300 hover:bg-neutral-900"
          }`}
        >
          <BoxSelect className="w-3.5 h-3.5" />
          <span className="text-[7px] font-mono">BED</span>
        </button>
      </div>
    </aside>
  );
}
