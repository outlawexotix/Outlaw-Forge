"use client";

import React from "react";
import {
  Box,
  ChevronDown,
  CircleHelp,
  FolderOpen,
  FolderPlus,
  Gauge,
  Layers3,
  Save,
  Settings,
  Sparkles,
  Upload,
} from "lucide-react";
import { HealthStatusResponse, PrinterProfile, Project } from "@shared/types/api";

export type SaveStatus = "saved" | "saving" | "unsaved";

interface HeaderProps {
  health: HealthStatusResponse | null;
  isHealthLoading: boolean;
  healthError: string | null;
  activeProject?: Project | null;
  activePrinter?: PrinterProfile | null;
  saveStatus?: SaveStatus;
  onNewProject?: () => void;
  onOpenProjectList?: () => void;
  onSaveProject?: () => void;
  onImportClick?: () => void;
  onOpenCalibration?: () => void;
  onAutoArrange?: () => void;
}

export function Header({
  health,
  isHealthLoading,
  healthError,
  activeProject = null,
  activePrinter = null,
  saveStatus = "saved",
  onNewProject,
  onOpenProjectList,
  onSaveProject,
  onImportClick,
  onOpenCalibration,
  onAutoArrange,
}: HeaderProps) {
  const engineOnline = Boolean(health && health.status === "healthy" && !healthError);
  const projectLabel = activeProject?.name || "Untitled Project";

  return (
    <header className="h-12 w-full shrink-0 border-b border-neutral-800 bg-[#0b0d10] flex items-center select-none z-50">
      <div className="h-full px-4 flex items-center gap-3 border-r border-neutral-800 shrink-0">
        <div className="h-7 w-7 border border-amber-500/70 bg-amber-500/10 flex items-center justify-center rounded-sm">
          <Box className="h-4 w-4 text-amber-400 stroke-[2.2]" />
        </div>
        <div className="leading-none">
          <div className="text-sm font-bold tracking-[0.08em] text-neutral-100">Outlaw Forge</div>
          <div className="mt-1 text-[8px] font-mono tracking-[0.16em] text-neutral-600">LOCAL WORKBENCH</div>
        </div>
      </div>

      <nav className="hidden lg:flex h-full items-center px-3 gap-0.5 border-r border-neutral-800">
        <button onClick={onOpenProjectList} className="top-menu-button">File</button>
        <button onClick={onSaveProject} className="top-menu-button">Edit</button>
        <button onClick={onAutoArrange} className="top-menu-button">View</button>
        <button onClick={onImportClick} className="top-menu-button">Model</button>
        <button onClick={onOpenCalibration} className="top-menu-button">Repair</button>
        <button className="top-menu-button">Help</button>
      </nav>

      <div className="flex-1 min-w-0 px-3 flex items-center gap-2">
        <button
          onClick={onOpenProjectList}
          className="min-w-0 max-w-[270px] h-8 px-2.5 border border-neutral-800 bg-neutral-900/70 hover:border-neutral-700 flex items-center gap-2 rounded-sm transition-colors"
          title="Open project manager"
        >
          <FolderOpen className="h-3.5 w-3.5 shrink-0 text-amber-400" />
          <span className="truncate text-[11px] font-medium text-neutral-300">{projectLabel}</span>
          <ChevronDown className="h-3 w-3 shrink-0 text-neutral-600" />
        </button>

        <div className="hidden xl:flex items-center gap-1">
          <button onClick={onNewProject} className="header-icon-button" title="New project">
            <FolderPlus className="h-3.5 w-3.5" />
          </button>
          <button onClick={onImportClick} className="header-icon-button" title="Import model">
            <Upload className="h-3.5 w-3.5" />
          </button>
          <button onClick={onAutoArrange} className="header-icon-button" title="Auto-arrange build plate">
            <Layers3 className="h-3.5 w-3.5" />
          </button>
          <button onClick={onOpenCalibration} className="header-icon-button" title="Calibration tools">
            <Sparkles className="h-3.5 w-3.5" />
          </button>
          <button
            onClick={onSaveProject}
            disabled={saveStatus === "saved" || saveStatus === "saving"}
            className="header-icon-button disabled:opacity-35"
            title="Save project"
          >
            <Save className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      <div className="h-full flex items-center shrink-0">
        <div className="hidden md:flex h-full min-w-[190px] px-4 border-l border-neutral-800 items-center gap-2">
          <Gauge className="h-3.5 w-3.5 text-neutral-500" />
          <div className="min-w-0">
            <div className="truncate text-[10px] font-medium text-neutral-300">
              {activePrinter ? `${activePrinter.manufacturer} ${activePrinter.model}` : "No printer selected"}
            </div>
            <div className="mt-0.5 text-[8px] font-mono text-neutral-600">PRINTER PROFILE</div>
          </div>
          <ChevronDown className="ml-auto h-3 w-3 text-neutral-600" />
        </div>
        <div className="hidden xl:flex h-full px-4 border-l border-neutral-800 items-center text-[10px] font-mono text-neutral-400">
          {activePrinter?.nozzle_diameter_mm ?? 0.4} mm Nozzle
        </div>
        <div className="hidden xl:flex h-full px-4 border-l border-neutral-800 items-center gap-2 text-[10px] font-mono text-neutral-300">
          PLA <ChevronDown className="h-3 w-3 text-neutral-600" />
        </div>
        <div className="h-full px-3 border-l border-neutral-800 flex items-center gap-2">
          <span
            className={`h-1.5 w-1.5 rounded-full ${isHealthLoading ? "bg-amber-400 animate-pulse" : engineOnline ? "bg-emerald-400" : "bg-red-500"}`}
            title={engineOnline ? "Geometry engine online" : healthError || "Geometry engine offline"}
          />
          <button className="header-icon-button" title="Settings"><Settings className="h-3.5 w-3.5" /></button>
          <button className="header-icon-button" title="Help"><CircleHelp className="h-3.5 w-3.5" /></button>
        </div>
      </div>
    </header>
  );
}
