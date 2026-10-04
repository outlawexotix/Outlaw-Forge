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
    <aside className="w-[78px] shrink-0 bg-[#0b0d10] border-r border-neutral-800 flex flex-col items-center py-2 justify-between z-40 select-none">
      {/* CAD Transformation Tools */}
      <div className="flex flex-col items-center space-y-1 w-full px-1.5">
        {TOOLS.map((tool) => {
          const Icon = tool.icon;
          const isActive = activeTool === tool.id;

          return (
            <button
              key={tool.id}
              onClick={() => onSelectTool(tool.id)}
              title={`${tool.label} [${tool.hotkey}] - ${tool.description}`}
              className={`relative group w-full h-[54px] rounded-sm flex flex-col items-center justify-center transition-all ${
                isActive
                  ? "bg-amber-500/10 text-amber-400 border border-amber-500/70"
                  : "text-neutral-400 hover:text-neutral-100 hover:bg-neutral-900 border border-transparent"
              }`}
            >
              <Icon className={`w-[18px] h-[18px] ${isActive ? "stroke-[2.2] text-amber-400" : "stroke-[1.7]"}`} />
              <span className="text-[9px] font-medium mt-1 leading-none">
                {tool.label}
              </span>

              {/* Hotkey badge */}
              <span className="absolute top-1 right-1.5 text-[7px] font-mono text-neutral-600 group-hover:text-neutral-300">
                {tool.hotkey}
              </span>

              {/* Active indicator bar */}
              {isActive && (
                <div className="absolute left-0 top-2 bottom-2 w-[2px] bg-amber-500" />
              )}
            </button>
          );
        })}
      </div>

      {/* Viewport Toggles */}
      <div className="flex flex-col items-center space-y-1 w-full px-1.5 pt-2 border-t border-neutral-800">

        {/* Snap to grid */}
        <button
          onClick={onToggleSnap}
          title={`Snap to Grid (${snapToGrid ? "ON" : "OFF"})`}
          className={`w-full h-9 rounded-sm flex flex-col items-center justify-center transition-all ${
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
          className={`w-full h-9 rounded-sm flex flex-col items-center justify-center transition-all ${
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
          className={`w-full h-9 rounded-sm flex flex-col items-center justify-center transition-all ${
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
