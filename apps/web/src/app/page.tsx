"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import { Header, SaveStatus } from "@/components/layout/Header";
import { Sidebar, CADTool } from "@/components/layout/Sidebar";
import { Inspector } from "@/components/layout/Inspector";
import { StatusBar } from "@/components/layout/StatusBar";
import { CreateProjectDialog } from "@/components/project/CreateProjectDialog";
import { CreatePrinterDialog } from "@/components/project/CreatePrinterDialog";
import { ProjectListDialog } from "@/components/project/ProjectListDialog";
import { ImportModelDialog } from "@/components/project/ImportModelDialog";
import { apiClient } from "@/lib/api-client";
import { 
  HealthStatusResponse, 
  Project, 
  ProjectCreatePayload, 
  PrinterProfile, 
  WorkingModel 
} from "@shared/types/api";
import dynamic from "next/dynamic";

const ViewportContainer = dynamic(
  () => import("@/components/viewport/ViewportContainer").then((mod) => mod.ViewportContainer),
  {
    ssr: false,
    loading: () => (
      <div className="w-full h-full flex flex-col items-center justify-center bg-[#090d16] text-slate-400 font-mono text-xs">
        <div className="w-8 h-8 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin mb-3" />
        <span className="text-cyan-300">Initializing 3D Viewport Engine...</span>
      </div>
    ),
  }
);

const ACTIVE_PROJECT_STORAGE_KEY = "outlaw_forge_active_project_id";

const FALLBACK_PRINTERS: PrinterProfile[] = [
  {
    id: "creality-ender-3",
    manufacturer: "Creality",
    model: "Ender-3",
    build_width_mm: 220,
    build_depth_mm: 220,
    build_height_mm: 250,
    nozzle_diameter_mm: 0.4,
    notes: "Cartesian 3D Printer",
  },
  {
    id: "creality-ender-3-s1",
    manufacturer: "Creality",
    model: "Ender-3 S1",
    build_width_mm: 220,
    build_depth_mm: 220,
    build_height_mm: 270,
    nozzle_diameter_mm: 0.4,
    notes: "Direct-drive Cartesian 3D Printer",
  },
];

export default function WorkbenchPage() {
  // Backend health state
  const [health, setHealth] = useState<HealthStatusResponse | null>(null);
  const [isHealthLoading, setIsHealthLoading] = useState<boolean>(true);
  const [healthError, setHealthError] = useState<string | null>(null);

  // Projects & Workspace state
  const [projects, setProjects] = useState<Project[]>([]);
  const [activeProject, setActiveProject] = useState<Project | null>(null);
  const [isProjectsLoading, setIsProjectsLoading] = useState<boolean>(true);
  const [isCreatingProject, setIsCreatingProject] = useState<boolean>(false);
  const [saveStatus, setSaveStatus] = useState<SaveStatus>("saved");

  // Dialog modals
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState<boolean>(false);
  const [isListDialogOpen, setIsListDialogOpen] = useState<boolean>(false);
  const [isImportDialogOpen, setIsImportDialogOpen] = useState<boolean>(false);
  const [isCreatePrinterDialogOpen, setIsCreatePrinterDialogOpen] = useState<boolean>(false);


  // Active Tool & Viewport settings
  const [activeTool, setActiveTool] = useState<CADTool>("select");
  const [snapToGrid, setSnapToGrid] = useState<boolean>(true);
  const [showWireframe, setShowWireframe] = useState<boolean>(true);
  const [showBed, setShowBed] = useState<boolean>(true);
  const [cameraMode, setCameraMode] = useState<"PERSPECTIVE" | "ORTHOGRAPHIC">("PERSPECTIVE");

  // Printers state
  const [printers, setPrinters] = useState<PrinterProfile[]>(FALLBACK_PRINTERS);
  const [activePrinter, setActivePrinter] = useState<PrinterProfile>(FALLBACK_PRINTERS[0]);

  // Model Buffer
  const [activeModelBuffer, setActiveModelBuffer] = useState<ArrayBuffer | null>(null);

  // Slicing Cutting Plane State
  const [slicePlaneOrigin, setSlicePlaneOrigin] = useState<[number, number, number]>([0, 0, 25]);
  const [slicePlaneNormal, setSlicePlaneNormal] = useState<[number, number, number]>([0, 0, 1]);

  // Cursor 3D Coordinate tracking
  const [cursorCoords, setCursorCoords] = useState<{ x: number; y: number; z: number }>({
    x: 0,
    y: 0,
    z: 0,
  });

  // Active Model from project
  const activeWorkingModel: WorkingModel | null = 
    activeProject?.working_models && activeProject.working_models.length > 0 
      ? activeProject.working_models[activeProject.working_models.length - 1] 
      : null;

  // 1. Backend Health Check
  const checkHealth = useCallback(async (signal?: AbortSignal) => {
    try {
      const data = await apiClient.getHealth(signal);
      setHealth(data);
      setHealthError(null);
    } catch (err: unknown) {
      if (err instanceof Error && err.name === "AbortError") return;
      setHealthError(err instanceof Error ? err.message : "Backend unavailable");
      setHealth(null);
    } finally {
      setIsHealthLoading(false);
    }
  }, []);

  // 2. Fetch Printers
  const fetchPrinters = useCallback(async () => {
    try {
      const list = await apiClient.listPrinters();
      if (list && list.length > 0) {
        setPrinters(list);
        setActivePrinter(list[0]);
      }
    } catch (err) {
      console.warn("Could not fetch printers, using fallbacks:", err);
    }
  }, []);

  // 3. Fetch Projects
  const fetchProjects = useCallback(async () => {
    try {
      setIsProjectsLoading(true);
      const list = await apiClient.listProjects();
      setProjects(list);

      // Restore active project
      const savedId = typeof window !== "undefined" ? localStorage.getItem(ACTIVE_PROJECT_STORAGE_KEY) : null;
      let matched = list.find((p) => p.id === savedId);

      if (!matched && list.length > 0) {
        matched = list[0];
      }

      if (matched) {
        setActiveProject(matched);
        if (typeof window !== "undefined") {
          localStorage.setItem(ACTIVE_PROJECT_STORAGE_KEY, matched.id);
        }
      } else {
        // Auto-create default starter project if empty
        const defaultProj = await apiClient.createProject({
          name: "Calibration Project",
          description: "Default Outlaw Forge 3D Print Workspace",
          project_type: "Mechanical Part",
          selected_printer_id: "creality-ender-3",
          notes: "Initial calibrated build volume project",
        });
        setProjects([defaultProj]);
        setActiveProject(defaultProj);
        if (typeof window !== "undefined") {
          localStorage.setItem(ACTIVE_PROJECT_STORAGE_KEY, defaultProj.id);
        }
      }
    } catch (err) {
      console.error("Failed to load projects:", err);
    } finally {
      setIsProjectsLoading(false);
    }
  }, []);

  // Initial load lifecycle
  useEffect(() => {
    const controller = new AbortController();
    checkHealth(controller.signal);
    fetchPrinters();
    fetchProjects();

    const interval = setInterval(() => {
      checkHealth(controller.signal);
    }, 10000);

    return () => {
      controller.abort();
      clearInterval(interval);
    };
  }, [checkHealth, fetchPrinters, fetchProjects]);

  // Handle Project Creation
  const handleCreateProject = async (payload: ProjectCreatePayload) => {
    try {
      setIsCreatingProject(true);
      const created = await apiClient.createProject(payload);
      setProjects((prev) => [created, ...prev]);
      setActiveProject(created);
      setActiveModelBuffer(null);
      if (typeof window !== "undefined") {
        localStorage.setItem(ACTIVE_PROJECT_STORAGE_KEY, created.id);
      }
      setIsCreateDialogOpen(false);
      setSaveStatus("saved");
    } catch (err) {
      console.error("Project creation failed:", err);
      alert("Failed to create project");
    } finally {
      setIsCreatingProject(false);
    }
  };

  // Handle Project Selection
  const handleSelectProject = (project: Project) => {
    setActiveProject(project);
    setActiveModelBuffer(null);
    if (typeof window !== "undefined") {
      localStorage.setItem(ACTIVE_PROJECT_STORAGE_KEY, project.id);
    }
    setSaveStatus("saved");
  };

  // Handle Project Deletion
  const handleDeleteProject = async (id: string) => {
    try {
      await apiClient.deleteProject(id);
      setProjects((prev) => prev.filter((p) => p.id !== id));
      if (activeProject?.id === id) {
        const remaining = projects.filter((p) => p.id !== id);
        if (remaining.length > 0) {
          handleSelectProject(remaining[0]);
        } else {
          setActiveProject(null);
        }
      }
    } catch (err) {
      console.error("Delete failed:", err);
      alert("Could not delete project");
    }
  };

  // Handle Save
  const handleSaveActiveProject = async () => {
    if (!activeProject) return;
    try {
      setSaveStatus("saving");
      const updated = await apiClient.updateProject(activeProject.id, {
        name: activeProject.name,
        description: activeProject.description,
        project_type: activeProject.project_type,
        selected_printer_id: activePrinter.id,
        notes: activeProject.notes,
      });
      setActiveProject(updated);
      setSaveStatus("saved");
    } catch (err) {
      console.error("Save failed:", err);
      setSaveStatus("unsaved");
    }
  };

  // Handle Printer Change
  const handlePrinterChange = (printer: PrinterProfile) => {
    setActivePrinter(printer);
    if (activeProject) {
      setActiveProject({
        ...activeProject,
        selected_printer_id: printer.id,
      });
      setSaveStatus("unsaved");
    }
  };

  // Handle Model Imported
  const handleModelImported = (model: WorkingModel) => {
    if (!activeProject) return;
    setActiveModelBuffer(null);
    setActiveProject((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        working_models: [...prev.working_models, model],
      };
    });
    setSaveStatus("saved");
  };

  // Handle Model Updated (Scale, etc.)
  const handleModelUpdated = (updatedModel: WorkingModel) => {
    if (!activeProject) return;
    setActiveModelBuffer(null);
    setActiveProject((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        working_models: prev.working_models.map((m) =>
          m.id === updatedModel.id ? updatedModel : m
        ),
      };
    });
    setSaveStatus("saved");
  };

  // Handle Model Sliced into Top and Bottom Parts
  const handleModelSliced = (result: any) => {
    if (!activeProject) return;
    setActiveModelBuffer(null);
    setActiveProject((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        working_models: [...prev.working_models, result.top_model, result.bottom_model],
      };
    });
    setSaveStatus("saved");
    handleRefreshOperations();
  };

  // Refresh project operations
  const handleRefreshOperations = async () => {
    if (!activeProject) return;
    try {
      const refreshed = await apiClient.getProject(activeProject.id);
      setActiveProject(refreshed);
    } catch (err) {
      console.error("Could not refresh project:", err);
    }
  };

  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden bg-[#090d16] text-slate-100 font-sans select-none">
      {/* 1. Header Bar */}
      <Header
        health={health}
        isHealthLoading={isHealthLoading}
        healthError={healthError}
        activeProject={activeProject}
        saveStatus={saveStatus}
        onNewProject={() => setIsCreateDialogOpen(true)}
        onOpenProjectList={() => setIsListDialogOpen(true)}
        onSaveProject={handleSaveActiveProject}
        onImportClick={() => setIsImportDialogOpen(true)}
      />

      {/* 2. Main CAD Workbench Body */}
      <div className="flex-1 flex overflow-hidden relative">
        {/* Left CAD Tool Palette */}
        <Sidebar
          activeTool={activeTool}
          onSelectTool={setActiveTool}
          snapToGrid={snapToGrid}
          onToggleSnap={() => setSnapToGrid((prev) => !prev)}
          showWireframe={showWireframe}
          onToggleWireframe={() => setShowWireframe((prev) => !prev)}
          showBed={showBed}
          onToggleBed={() => setShowBed((prev) => !prev)}
        />

        {/* Central 3D Viewport Area */}
        <main className="flex-1 relative flex flex-col items-center justify-center bg-[#090d16] overflow-hidden">
          <ViewportContainer
            printer={activePrinter}
            model={activeWorkingModel}
            modelBuffer={activeModelBuffer}
            activeTool={activeTool}
            slicePlaneOrigin={slicePlaneOrigin}
            slicePlaneNormal={slicePlaneNormal}
            onCursorCoordinates={(coords: { x: number; y: number; z: number }) => setCursorCoords(coords)}
            className="w-full h-full"
          />
        </main>

        {/* Right Inspector & Stats Panel */}
        <Inspector
          projectId={activeProject?.id || ""}
          mesh={activeWorkingModel}
          printer={activePrinter}
          printers={printers}
          operations={activeProject?.operations || []}
          onPrinterChange={handlePrinterChange}
          onOpenCreatePrinter={() => setIsCreatePrinterDialogOpen(true)}
          onModelUpdated={handleModelUpdated}
          onModelSliced={handleModelSliced}
          onSlicePlaneChange={(origin, normal) => {
            setSlicePlaneOrigin(origin);
            setSlicePlaneNormal(normal);
          }}
          onOperationRecorded={handleRefreshOperations}
        />
      </div>

      {/* 3. Status Bar */}
      <StatusBar
        health={health}
        cursorCoords={cursorCoords}
        fps={60}
        cameraMode={cameraMode}
        unit="MM"
        gridStep="10.0 mm"
      />

      {/* 4. Project Modals */}
      <CreateProjectDialog
        isOpen={isCreateDialogOpen}
        onClose={() => setIsCreateDialogOpen(false)}
        onCreate={handleCreateProject}
        printers={printers}
        isCreating={isCreatingProject}
      />

      <CreatePrinterDialog
        isOpen={isCreatePrinterDialogOpen}
        onClose={() => setIsCreatePrinterDialogOpen(false)}
        onCreated={(newPrinter) => {
          setPrinters((prev) => [...prev, newPrinter]);
          handlePrinterChange(newPrinter);
        }}
      />

      <ProjectListDialog
        isOpen={isListDialogOpen}
        onClose={() => setIsListDialogOpen(false)}
        projects={projects}
        activeProjectId={activeProject?.id || null}
        onSelectProject={handleSelectProject}
        onDeleteProject={handleDeleteProject}
        onOpenCreate={() => setIsCreateDialogOpen(true)}
        isLoading={isProjectsLoading}
      />

      <ImportModelDialog
        isOpen={isImportDialogOpen}
        onClose={() => setIsImportDialogOpen(false)}
        projectId={activeProject?.id || ""}
        onModelImported={handleModelImported}
      />
    </div>
  );
}
