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
  Clock,
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
}: HeaderProps) {
  const getHealthDisplay = () => {
    if (isHealthLoading && !health) {
      return {
        label: "CONNECTING",
        color: "bg-amber-500/20 text-amber-400 border-amber-500/30",
        dotColor: "bg-amber-400 animate-pulse",
        icon: <Activity className="w-3.5 h-3.5 text-amber-400 animate-spin" />,
      };
    }

    if (healthError || !health) {
      return {
        label: "BACKEND OFFLINE",
        color: "bg-rose-500/10 text-rose-400 border-rose-500/30",
        dotColor: "bg-rose-500",
        icon: <XCircle className="w-3.5 h-3.5 text-rose-400" />,
      };
    }

    if (health.status === "healthy") {
      return {
        label: `ONLINE v${health.version}`,
        color: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
        dotColor: "bg-emerald-400 animate-pulse",
        icon: <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />,
      };
    }

    return {
      label: "DEGRADED",
      color: "bg-amber-500/10 text-amber-400 border-amber-500/30",
      dotColor: "bg-amber-400",
      icon: <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />,
    };
  };

  const getSaveStatusDisplay = () => {
    switch (saveStatus) {
      case "saving":
        return {
          label: "Saving...",
          color: "bg-cyan-500/15 text-cyan-300 border-cyan-500/40 animate-pulse",
          icon: <Activity className="w-3 h-3 text-cyan-400 animate-spin" />,
        };
      case "unsaved":
        return {
          label: "Unsaved Changes",
          color: "bg-amber-500/15 text-amber-400 border-amber-500/40",
          icon: <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />,
        };
      case "saved":
      default:
        return {
          label: "Saved",
          color: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
          icon: <CheckCircle2 className="w-3 h-3 text-emerald-400" />,
        };
    }
  };

  const healthStatus = getHealthDisplay();
  const saveIndicator = getSaveStatusDisplay();

  return (
    <header className="h-12 w-full bg-slate-950/95 backdrop-blur-md border-b border-slate-800/80 px-4 flex items-center justify-between z-50 select-none">
      {/* Left: Brand Identity & Active Project Controls */}
      <div className="flex items-center space-x-3 sm:space-x-4 min-w-0">
        {/* App Logo */}
        <div className="flex items-center space-x-2.5 shrink-0">
          <div className="w-7 h-7 rounded bg-gradient-to-br from-cyan-500 to-blue-700 flex items-center justify-center shadow-glow-cyan">
            <Box className="w-4 h-4 text-slate-950 font-black stroke-[2.5]" />
          </div>
          <div className="hidden sm:flex flex-col">
            <div className="flex items-center space-x-1.5">
              <span className="font-mono text-xs font-black tracking-wider text-slate-100 uppercase">
                OUTLAW<span className="text-cyan-400"> FORGE</span>
              </span>
              <span className="px-1 py-0.2 text-[8px] font-mono font-semibold bg-cyan-950/80 text-cyan-400 border border-cyan-800/60 rounded">
                PRO-CAD
              </span>
            </div>
            <span className="text-[9px] font-mono text-slate-500 tracking-tight">
              PRECISION MESH ENGINE
            </span>
          </div>
        </div>

        <div className="h-5 w-[1px] bg-slate-800 shrink-0" />

        {/* Project Selector & Actions */}
        <div className="flex items-center space-x-2 min-w-0">
          {/* Active Project Breadcrumb / Selector Button */}
          <button
            onClick={onOpenProjectList}
            className="flex items-center space-x-2 bg-slate-900/90 hover:bg-slate-800/90 border border-slate-800 hover:border-slate-700 rounded-lg px-2.5 py-1 transition group max-w-[280px] sm:max-w-[360px] text-left"
            title="Open Project Manager"
          >
            <FolderOpen className="w-3.5 h-3.5 text-cyan-400 shrink-0 group-hover:scale-110 transition-transform" />
            <div className="flex items-center space-x-2 min-w-0 truncate">
              <span className="text-xs font-mono font-semibold text-slate-200 group-hover:text-cyan-300 truncate">
                {activeProject ? activeProject.name : "Select Project..."}
              </span>
              {activeProject && (
                <span className="text-[9px] font-mono px-1.5 py-0.5 bg-cyan-950/80 text-cyan-300 border border-cyan-800/50 rounded uppercase shrink-0">
                  {activeProject.project_type}
                </span>
              )}
            </div>
            <ChevronDown className="w-3 h-3 text-slate-500 group-hover:text-slate-300 shrink-0 ml-1" />
          </button>

          {/* Quick Action Buttons: New Project & Open Project */}
          <div className="flex items-center space-x-1 shrink-0">
            <button
              onClick={onNewProject}
              className="px-2 py-1 text-xs font-mono font-medium text-slate-300 hover:text-white bg-slate-900 hover:bg-cyan-950/60 border border-slate-800 hover:border-cyan-500/50 rounded-lg transition flex items-center space-x-1"
              title="Create New CAD Project"
            >
              <FolderPlus className="w-3.5 h-3.5 text-cyan-400" />
              <span className="hidden md:inline">New Project</span>
            </button>
            <button
              onClick={onOpenProjectList}
              className="px-2 py-1 text-xs font-mono font-medium text-slate-400 hover:text-white bg-slate-900/60 hover:bg-slate-800 border border-slate-800/80 rounded-lg transition flex items-center space-x-1"
              title="Browse and Switch Projects"
            >
              <FolderOpen className="w-3.5 h-3.5 text-slate-400" />
              <span className="hidden md:inline">Open Project</span>
            </button>
          </div>
        </div>
      </div>

      {/* Center: Live Save Indicator & Quick Actions */}
      <div className="hidden lg:flex items-center space-x-3">
        {/* Live Save Status Indicator Pill */}
        <div 
          className={`flex items-center space-x-1.5 px-2.5 py-1 rounded-full border text-[11px] font-mono font-medium transition-all ${saveIndicator.color}`}
          title={saveStatus === "unsaved" ? "You have unsaved changes. Click Save to persist." : "Workspace synchronized"}
        >
          {saveIndicator.icon}
          <span>{saveIndicator.label}</span>
        </div>

        {/* Quick Toolbar */}
        <div className="flex items-center space-x-1 bg-slate-900/60 border border-slate-800/60 rounded-lg p-0.5">
          <button 
            onClick={onImportClick}
            className="px-2.5 py-1 text-xs font-mono text-slate-300 hover:text-white hover:bg-slate-800 rounded transition-all flex items-center space-x-1.5"
            title="Open & Import Mesh File (STL, OBJ, 3MF, STEP)"
          >
            <FolderOpen className="w-3.5 h-3.5 text-cyan-400" />
            <span>Import</span>
          </button>
          <button 
            onClick={onSaveProject}
            disabled={saveStatus === "saved" || saveStatus === "saving"}
            className="px-2.5 py-1 text-xs font-mono text-slate-300 hover:text-white hover:bg-slate-800 disabled:opacity-50 disabled:hover:bg-transparent rounded transition-all flex items-center space-x-1.5"
            title="Save Active Project State"
          >
            <Save className={`w-3.5 h-3.5 ${saveStatus === "unsaved" ? "text-amber-400" : "text-slate-400"}`} />
            <span>Save</span>
          </button>
        </div>
      </div>

      {/* Right: System Info & Backend Health */}
      <div className="flex items-center space-x-3 shrink-0">
        {/* Mobile/Tablet Save Status Indicator */}
        <div className="lg:hidden flex items-center">
          <div className={`flex items-center space-x-1 px-2 py-0.5 rounded-full border text-[10px] font-mono ${saveIndicator.color}`}>
            {saveIndicator.icon}
            <span>{saveIndicator.label}</span>
          </div>
        </div>

        {/* Backend Health Pill */}
        <div 
          className={`flex items-center space-x-2 px-2.5 py-1 rounded-full border text-xs font-mono transition-all ${healthStatus.color}`}
          title={
            health 
              ? `Engine: ${health.services.mesh_engine} | DB: ${health.services.database} | Platform: ${health.system.platform}`
              : healthError || "Backend offline"
          }
        >
          <span className={`w-2 h-2 rounded-full ${healthStatus.dotColor}`} />
          <span className="font-semibold text-[11px] tracking-wide">
            {healthStatus.label}
          </span>
          {healthStatus.icon}
        </div>

        {/* Engine Spec Indicator */}
        <div className="hidden xl:flex items-center space-x-1 text-[11px] font-mono text-slate-400 bg-slate-900 border border-slate-800 px-2 py-1 rounded">
          <Cpu className="w-3 h-3 text-cyan-400" />
          <span>CORE: {health?.services.mesh_engine === "ready" ? "ACTIVE" : "STANDBY"}</span>
        </div>

        <div className="h-5 w-[1px] bg-slate-800" />

        {/* Quick Settings & Help */}
        <button 
          className="p-1.5 text-slate-400 hover:text-white hover:bg-slate-800 rounded transition-all"
          title="Workspace Settings"
        >
          <Settings className="w-4 h-4" />
        </button>
        <button 
          className="p-1.5 text-slate-400 hover:text-white hover:bg-slate-800 rounded transition-all"
          title="Keyboard Shortcuts & Documentation"
        >
          <HelpCircle className="w-4 h-4" />
        </button>
      </div>
    </header>
  );
}
