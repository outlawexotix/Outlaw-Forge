"use client";

import React from "react";
import { HealthStatusResponse, Project } from "@shared/types/api";
import { 
  Box, 
  Activity, 
  Layers, 
  Settings, 
  FolderOpen, 
  FolderPlus,
  Save, 
  Cpu, 
  CheckCircle2, 
  AlertTriangle, 
  XCircle,
  HelpCircle,
  Sparkles,
  ChevronDown
} from "lucide-react";

export type SaveStatus = "saved" | "saving" | "unsaved";

interface HeaderProps {
  health: HealthStatusResponse | null;
  isHealthLoading: boolean;
  healthError: string | null;
  activeProject?: Project | null;
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
  saveStatus = "saved",
  onNewProject,
  onOpenProjectList,
  onSaveProject,
  onImportClick,
  onOpenCalibration,
  onAutoArrange,
}: HeaderProps) {
  const getHealthDisplay = () => {
    if (isHealthLoading && !health) {
      return {
        label: "CONNECTING",
        color: "bg-amber-500/10 text-amber-400 border-amber-500/30",
        dotColor: "bg-amber-400 animate-pulse",
        icon: <Activity className="w-3 h-3 text-amber-400 animate-spin" />,
      };
    }

    if (healthError || !health) {
      return {
        label: "OFFLINE",
        color: "bg-rose-500/10 text-rose-400 border-rose-500/30",
        dotColor: "bg-rose-500",
        icon: <XCircle className="w-3 h-3 text-rose-400" />,
      };
    }

    if (health.status === "healthy") {
      return {
        label: `ONLINE v${health.version}`,
        color: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
        dotColor: "bg-emerald-400",
        icon: <CheckCircle2 className="w-3 h-3 text-emerald-400" />,
      };
    }

    return {
      label: "DEGRADED",
      color: "bg-amber-500/10 text-amber-400 border-amber-500/30",
      dotColor: "bg-amber-400",
      icon: <AlertTriangle className="w-3 h-3 text-amber-400" />,
    };
  };

  const getSaveStatusDisplay = () => {
    switch (saveStatus) {
      case "saving":
        return {
          label: "SAVING",
          color: "bg-amber-500/15 text-amber-300 border-amber-500/40 animate-pulse",
          icon: <Activity className="w-3 h-3 text-amber-400 animate-spin" />,
        };
      case "unsaved":
        return {
          label: "UNSAVED",
          color: "bg-amber-500/15 text-amber-400 border-amber-500/40",
          icon: <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />,
        };
      case "saved":
      default:
        return {
          label: "SYNCED",
          color: "bg-neutral-800 text-neutral-400 border-neutral-700",
          icon: <CheckCircle2 className="w-3 h-3 text-neutral-400" />,
        };
    }
  };

  const healthStatus = getHealthDisplay();
  const saveIndicator = getSaveStatusDisplay();

  return (
    <header className="h-10 w-full bg-neutral-950 border-b border-neutral-800 px-3 flex items-center justify-between z-50 select-none">
      {/* Left: Brand Identity & Active Project Controls */}
      <div className="flex items-center space-x-3 min-w-0">
        {/* App Logo */}
        <div className="flex items-center space-x-2 shrink-0">
          <div className="w-6 h-6 rounded bg-amber-500 flex items-center justify-center text-neutral-950 font-black">
            <Box className="w-3.5 h-3.5 stroke-[2.5]" />
          </div>
          <div className="hidden sm:flex items-center space-x-1.5">
            <span className="font-mono text-xs font-bold tracking-wider text-neutral-100 uppercase">
              OUTLAW<span className="text-amber-500">FORGE</span>
            </span>
            <span className="px-1 py-0.2 text-[8px] font-mono font-bold bg-neutral-900 text-neutral-400 border border-neutral-800 rounded">
              CAD
            </span>
          </div>
        </div>

        <div className="h-4 w-[1px] bg-neutral-800 shrink-0" />

        {/* Project Selector & Actions */}
        <div className="flex items-center space-x-1.5 min-w-0">
          {/* Active Project Breadcrumb */}
          <button
            onClick={onOpenProjectList}
            className="flex items-center space-x-2 bg-neutral-900 hover:bg-neutral-850 border border-neutral-800 hover:border-neutral-700 rounded px-2 py-1 transition group max-w-[240px] sm:max-w-[320px] text-left"
            title="Open Project Manager"
          >
            <FolderOpen className="w-3.5 h-3.5 text-amber-500 shrink-0" />
            <div className="flex items-center space-x-1.5 min-w-0 truncate">
              <span className="text-xs font-mono font-medium text-neutral-200 group-hover:text-amber-400 truncate">
                {activeProject ? activeProject.name : "Select Project..."}
              </span>
              {activeProject && (
                <span className="text-[8px] font-mono px-1 py-0.2 bg-neutral-800 text-neutral-400 border border-neutral-750 rounded uppercase shrink-0">
                  {activeProject.project_type}
                </span>
              )}
            </div>
            <ChevronDown className="w-3 h-3 text-neutral-500 group-hover:text-neutral-300 shrink-0 ml-0.5" />
          </button>

          {/* Quick Project Actions */}
          <div className="flex items-center space-x-1 shrink-0">
            <button
              onClick={onNewProject}
              className="px-2 py-1 text-xs font-mono font-medium text-neutral-300 hover:text-white bg-neutral-900 hover:bg-neutral-800 border border-neutral-800 hover:border-neutral-700 rounded transition flex items-center space-x-1"
              title="Create New CAD Project"
            >
              <FolderPlus className="w-3 h-3 text-amber-500" />
              <span className="hidden md:inline">New</span>
            </button>
            <button
              onClick={onOpenProjectList}
              className="px-2 py-1 text-xs font-mono font-medium text-neutral-400 hover:text-white bg-neutral-900 hover:bg-neutral-800 border border-neutral-800 rounded transition flex items-center space-x-1"
              title="Browse Projects"
            >
              <FolderOpen className="w-3 h-3 text-neutral-400" />
              <span className="hidden md:inline">Open</span>
            </button>
          </div>
        </div>
      </div>

      {/* Center: Command Toolbar */}
      <div className="hidden lg:flex items-center space-x-2">
        {/* Synchronized Status Pill */}
        <div 
          className={`flex items-center space-x-1 px-2 py-0.5 rounded border text-[10px] font-mono font-semibold transition-all ${saveIndicator.color}`}
          title={saveStatus === "unsaved" ? "Unsaved changes exist. Click Save to persist." : "Workspace synchronized"}
        >
          {saveIndicator.icon}
          <span>{saveIndicator.label}</span>
        </div>

        {/* Action Controls */}
        <div className="flex items-center space-x-0.5 bg-neutral-900 border border-neutral-800 rounded p-0.5">
          <button 
            onClick={onImportClick}
            className="px-2 py-0.5 text-xs font-mono text-neutral-300 hover:text-white hover:bg-neutral-800 rounded transition flex items-center space-x-1"
            title="Import Mesh (STL, OBJ, 3MF, STEP)"
          >
            <FolderOpen className="w-3 h-3 text-amber-500" />
            <span>Import</span>
          </button>
          <button 
            onClick={onOpenCalibration}
            className="px-2 py-0.5 text-xs font-mono text-amber-400 hover:text-amber-300 hover:bg-amber-500/10 rounded transition flex items-center space-x-1"
            title="Open OrcaSlicer Calibration Suite"
          >
            <Sparkles className="w-3 h-3 text-amber-500" />
            <span>Calibration</span>
          </button>
          <button 
            onClick={onAutoArrange}
            className="px-2 py-0.5 text-xs font-mono text-neutral-300 hover:text-white hover:bg-neutral-800 rounded transition flex items-center space-x-1"
            title="Auto-Arrange Models on Build Plate"
          >
            <Layers className="w-3 h-3 text-neutral-400" />
            <span>Arrange</span>
          </button>
          <button 
            onClick={onSaveProject}
            disabled={saveStatus === "saved" || saveStatus === "saving"}
            className="px-2 py-0.5 text-xs font-mono text-neutral-300 hover:text-white hover:bg-neutral-800 disabled:opacity-40 disabled:hover:bg-transparent rounded transition flex items-center space-x-1"
            title="Save Project State"
          >
            <Save className={`w-3 h-3 ${saveStatus === "unsaved" ? "text-amber-500" : "text-neutral-500"}`} />
            <span>Save</span>
          </button>
        </div>
      </div>

      {/* Right: Telemetry & Connection Status */}
      <div className="flex items-center space-x-2 shrink-0">
        {/* Backend Health Pill */}
        <div 
          className={`flex items-center space-x-1.5 px-2 py-0.5 rounded border text-[10px] font-mono font-medium transition-all ${healthStatus.color}`}
          title={
            health 
              ? `Engine: ${health.services.mesh_engine} | DB: ${health.services.database} | Platform: ${health.system.platform}`
              : healthError || "Backend offline"
          }
        >
          <span className={`w-1.5 h-1.5 rounded-full ${healthStatus.dotColor}`} />
          <span className="font-bold tracking-wide">
            {healthStatus.label}
          </span>
          {healthStatus.icon}
        </div>

        {/* Engine Spec Indicator */}
        <div className="hidden xl:flex items-center space-x-1 text-[10px] font-mono text-neutral-400 bg-neutral-900 border border-neutral-800 px-1.5 py-0.5 rounded">
          <Cpu className="w-3 h-3 text-amber-500" />
          <span>GEO: {health?.services.mesh_engine === "ready" ? "ACTIVE" : "STANDBY"}</span>
        </div>

        <div className="h-4 w-[1px] bg-neutral-800" />

        {/* Settings & Help */}
        <button 
          className="p-1 text-neutral-400 hover:text-white hover:bg-neutral-800 rounded transition"
          title="Workspace Settings"
        >
          <Settings className="w-3.5 h-3.5" />
        </button>
        <button 
          className="p-1 text-neutral-400 hover:text-white hover:bg-neutral-800 rounded transition"
          title="Shortcuts and Docs"
        >
          <HelpCircle className="w-3.5 h-3.5" />
        </button>
      </div>
    </header>
  );
}
