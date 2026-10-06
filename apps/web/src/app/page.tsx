"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import { Header, SaveStatus } from "@/components/layout/Header";
import { Sidebar, CADTool } from "@/components/layout/Sidebar";
import { Inspector } from "@/components/layout/Inspector";
import { ReadinessPanel } from "@/components/layout/ReadinessPanel";
import { StatusBar } from "@/components/layout/StatusBar";
import { WorkflowRail } from "@/components/layout/WorkflowRail";
import { CreateProjectDialog } from "@/components/project/CreateProjectDialog";
import { CreatePrinterDialog } from "@/components/project/CreatePrinterDialog";
import { ProjectListDialog } from "@/components/project/ProjectListDialog";
import { ImportModelDialog } from "@/components/project/ImportModelDialog";
import { CalibrationDialog } from "@/components/project/CalibrationDialog";
import { apiClient } from "@/lib/api-client";
import { 
  HealthStatusResponse, 
  Project, 
  ProjectCreatePayload, 
  PrinterProfile, 
  WorkingModel 
} from "@shared/types/api";
import dynamic from "next/dynamic";
import { X } from "lucide-react";
import type { ViewportContainerProps } from "@/components/viewport/ViewportContainer";

const ViewportContainer: React.ComponentType<ViewportContainerProps> = dynamic(
  () => import("@/components/viewport/ViewportContainer").then((mod) => mod.ViewportContainer),
  {
    ssr: false,
    loading: () => (
      <div className="w-full h-full flex flex-col items-center justify-center bg-neutral-950 text-neutral-400 font-mono text-xs">
        <div className="w-8 h-8 border-2 border-amber-500 border-t-transparent rounded-full animate-spin mb-3" />
        <span className="text-amber-400 font-medium">INITIALIZING 3D VIEWPORT ENGINE...</span>
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
  const [isCalibrationDialogOpen, setIsCalibrationDialogOpen] = useState<boolean>(false);
  const [isAdvancedToolsOpen, setIsAdvancedToolsOpen] = useState<boolean>(false);



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

  // Active Selected Model ID
  const [selectedModelId, setSelectedModelId] = useState<string | null>(null);

  // Active Model from project
  const workingModels = activeProject?.working_models || [];
  const activeWorkingModel: WorkingModel | null = 
    workingModels.find((m) => m.id === selectedModelId) ||
    (workingModels.length > 0 ? workingModels[workingModels.length - 1] : null);

  const activeDimensions = activeWorkingModel?.bounds.dimensions_mm ?? [0, 0, 0];
  const activeModelFits = Boolean(
    activeWorkingModel &&
      activeDimensions[0] <= activePrinter.build_width_mm &&
      activeDimensions[1] <= activePrinter.build_depth_mm &&
      activeDimensions[2] <= activePrinter.build_height_mm
  );

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
      throw err;
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

  // Handle Direct Model Import (e.g. Viewport Drag and Drop)
  const handleModelImport = async (file: File) => {
    if (!activeProject) {
      alert("Please select or create a project before importing 3D models.");
      return;
    }
    try {
      const imported = await apiClient.importModel(activeProject.id, file);
      handleModelImported(imported);
    } catch (err: unknown) {
      console.error("Model import failed:", err);
      const msg = err instanceof Error ? err.message : "Failed to import model.";
      alert(msg);
    }
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

  const handleModelDeleted = (modelId: string) => {
    setActiveProject((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        working_models: prev.working_models.filter((model) => model.id !== modelId),
      };
    });
    setSelectedModelId((current) => (current === modelId ? null : current));
    setActiveModelBuffer(null);
    setSaveStatus("saved");
  };

  const handleViewportDuplicate = async (modelId: string) => {
    if (!activeProject) return;
    try {
      const duplicate = await apiClient.duplicateModel(activeProject.id, modelId);
      setActiveProject((prev) => prev ? {
        ...prev,
        working_models: [...prev.working_models, duplicate],
      } : prev);
      setSelectedModelId(duplicate.id);
      setSaveStatus("saved");
    } catch (err) {
      alert(err instanceof Error ? err.message : "Could not duplicate model.");
    }
  };

  const handleViewportDelete = async (modelId: string) => {
    if (!activeProject || !confirm("Delete this model from the build plate?")) return;
    try {
      await apiClient.deleteModel(activeProject.id, modelId);
      handleModelDeleted(modelId);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Could not delete model.");
    }
  };

  const handleViewportMirror = (modelId: string, axis: "X" | "Y" | "Z") => {
    const axisIndex = { X: 0, Y: 1, Z: 2 }[axis];
    setActiveProject((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        working_models: prev.working_models.map((m) => {
          if (m.id !== modelId) return m;
          const scale = [...m.transform.scale_factors] as [number, number, number];
          scale[axisIndex] *= -1;
          return { ...m, transform: { ...m.transform, scale_factors: scale } };
        }),
      };
    });
    setSelectedModelId(modelId);
    setSaveStatus("unsaved");
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

  // Handle Auto-Arrange multi-model nesting
  const handleAutoArrange = async () => {
    if (!activeProject || !activeProject.working_models || activeProject.working_models.length === 0) {
      alert("No models on the build plate to arrange.");
      return;
    }
    try {
      const res = await apiClient.autoArrange(activeProject.id, {
        spacing_mm: 10.0,
        bed_width_mm: activePrinter.build_width_mm,
        bed_depth_mm: activePrinter.build_depth_mm,
      });
      if (res.arranged_models && res.arranged_models.length > 0) {
        setActiveProject((prev) => {
          if (!prev) return prev;
          return {
            ...prev,
            working_models: res.arranged_models,
          };
        });
        setActiveModelBuffer(null);
        setSaveStatus("saved");
        handleRefreshOperations();
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Auto-arrange failed";
      alert(msg);
    }
  };

  // Handle Slice Plane Changed
  const handleSlicePlaneChange = useCallback(
    (origin: [number, number, number], normal: [number, number, number]) => {
      setSlicePlaneOrigin((prev) => {
        if (prev[0] === origin[0] && prev[1] === origin[1] && prev[2] === origin[2]) return prev;
        return origin;
      });
      setSlicePlaneNormal((prev) => {
        if (prev[0] === normal[0] && prev[1] === normal[1] && prev[2] === normal[2]) return prev;
        return normal;
      });
    },
    []
  );

  // Handle Live Transform Changes from Viewport Gizmos / Lay on Face
  const handleViewportTransformChange = useCallback(
    (transform: { position: [number, number, number]; rotation: [number, number, number]; scale: [number, number, number] }) => {
      if (!activeWorkingModel) return;
      setActiveProject((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          working_models: prev.working_models.map((m) =>
            m.id === activeWorkingModel.id
              ? {
                  ...m,
                  transform: {
                    ...m.transform,
                    position_mm: transform.position,
                    rotation_deg: transform.rotation,
                    scale_factors: transform.scale,
                  },
                }
              : m
          ),
        };
      });
      setSaveStatus("unsaved");
    },
    [activeWorkingModel]
  );

  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden bg-[#090d16] text-slate-100 font-sans select-none">
      {/* 1. Header Bar */}
      <Header
        health={health}
        isHealthLoading={isHealthLoading}
        healthError={healthError}
        activeProject={activeProject}
        activePrinter={activePrinter}
        saveStatus={saveStatus}
        onNewProject={() => setIsCreateDialogOpen(true)}
        onOpenProjectList={() => setIsListDialogOpen(true)}
        onSaveProject={handleSaveActiveProject}
        onImportClick={() => {
          if (activeProject) {
            setIsImportDialogOpen(true);
          } else {
            setIsListDialogOpen(true);
          }
        }}
        onOpenCalibration={() => setIsCalibrationDialogOpen(true)}
        onAutoArrange={handleAutoArrange}
      />

      {/* 2. Main CAD Workbench Body */}
      <div className="flex-1 flex overflow-hidden relative min-h-0">
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
        <main className="flex-1 min-w-0 relative flex flex-col items-center justify-center bg-neutral-950 overflow-hidden">
          <div className="absolute top-4 left-5 z-20 pointer-events-none">
            <div className="text-[14px] font-semibold text-neutral-100 drop-shadow-lg">
              {activeWorkingModel?.filename || "No model loaded"}
            </div>
            <div className="mt-1 text-[10px] font-mono text-neutral-500">
              {activeWorkingModel
                ? `${activeDimensions[0].toFixed(1)} × ${activeDimensions[1].toFixed(1)} × ${activeDimensions[2].toFixed(1)} mm`
                : "Drop a mesh file into the viewport"}
            </div>
          </div>
          <ViewportContainer
            printer={activePrinter}
            model={activeWorkingModel}
            models={workingModels}
            activeModelId={activeWorkingModel?.id || null}
            modelBuffer={activeModelBuffer}
            activeTool={activeTool}
            slicePlaneOrigin={slicePlaneOrigin}
            slicePlaneNormal={slicePlaneNormal}
            onSelectModel={(id: string) => setSelectedModelId(id)}
            onSetTool={setActiveTool}
            onDuplicateModel={handleViewportDuplicate}
            onDeleteModel={handleViewportDelete}
            onMirrorModel={handleViewportMirror}
            onTransformChange={handleViewportTransformChange}
            onCursorCoordinates={(coords: { x: number; y: number; z: number }) => setCursorCoords(coords)}
            onDropFile={(file) => handleModelImport(file)}
            className="w-full h-full"
          />
        </main>


        <ReadinessPanel
          projectId={activeProject?.id || ""}
          mesh={activeWorkingModel}
          printer={activePrinter}
          onModelUpdated={handleModelUpdated}
          onOperationRecorded={handleRefreshOperations}
          onOpenAdvanced={() => setIsAdvancedToolsOpen(true)}
        />

        {isAdvancedToolsOpen && (
          <div className="absolute inset-0 z-[70] bg-black/60 backdrop-blur-[2px] flex justify-end">
            <div className="relative h-full w-[420px] max-w-[92vw] border-l border-neutral-700 bg-neutral-950 shadow-2xl">
              <button
                onClick={() => setIsAdvancedToolsOpen(false)}
                className="absolute top-2 right-2 z-[80] h-7 w-7 border border-neutral-700 bg-neutral-900 hover:bg-neutral-800 text-neutral-400 hover:text-white flex items-center justify-center rounded-sm"
                title="Close advanced tools"
              >
                <X className="h-4 w-4" />
              </button>
              <Inspector
                projectId={activeProject?.id || ""}
                mesh={activeWorkingModel}
                models={workingModels}
                selectedModelId={activeWorkingModel?.id || null}
                printer={activePrinter}
                printers={printers}
                operations={activeProject?.operations || []}
                onSelectModel={(id) => setSelectedModelId(id)}
                onPrinterChange={handlePrinterChange}
                onOpenCreatePrinter={() => setIsCreatePrinterDialogOpen(true)}
                onModelUpdated={handleModelUpdated}
                onModelDeleted={handleModelDeleted}
                onModelSliced={handleModelSliced}
                onSlicePlaneChange={handleSlicePlaneChange}
                onOperationRecorded={handleRefreshOperations}
                onProjectRefreshed={handleRefreshOperations}
                onAutoArrange={handleAutoArrange}
              />
            </div>
          </div>
        )}
      </div>

      <WorkflowRail
        hasModel={Boolean(activeWorkingModel)}
        isWatertight={Boolean(activeWorkingModel?.is_watertight)}
        fitsBuildVolume={activeModelFits}
        operations={activeProject?.operations ?? []}
      />

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

      <CalibrationDialog
        isOpen={isCalibrationDialogOpen}
        onClose={() => setIsCalibrationDialogOpen(false)}
        projectId={activeProject?.id || ""}
        onModelGenerated={handleModelImported}
      />
    </div>
  );
}
