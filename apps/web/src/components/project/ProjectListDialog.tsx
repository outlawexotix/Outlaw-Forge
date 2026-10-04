"use client";

import React, { useState, useMemo } from "react";
import { Project } from "@shared/types/api";
import { 
  X, 
  Search, 
  Folder, 
  FolderOpen, 
  Plus, 
  Trash2, 
  Clock, 
  Box, 
  Layers, 
  CheckCircle2, 
  Loader2
} from "lucide-react";

interface ProjectListDialogProps {
  isOpen: boolean;
  onClose: () => void;
  projects: Project[];
  activeProjectId: string | null;
  onSelectProject: (project: Project) => void;
  onDeleteProject: (projectId: string) => Promise<void> | void;
  onOpenCreate: () => void;
  isLoading?: boolean;
}

export function ProjectListDialog({
  isOpen,
  onClose,
  projects,
  activeProjectId,
  onSelectProject,
  onDeleteProject,
  onOpenCreate,
  isLoading = false,
}: ProjectListDialogProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedTypeFilter, setSelectedTypeFilter] = useState<string>("ALL");
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);

  const filteredProjects = useMemo(() => {
    return projects.filter((p) => {
      const matchesSearch = 
        p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (p.description && p.description.toLowerCase().includes(searchQuery.toLowerCase())) ||
        (p.notes && p.notes.toLowerCase().includes(searchQuery.toLowerCase()));
      
      const matchesType = selectedTypeFilter === "ALL" || p.project_type === selectedTypeFilter;
      return matchesSearch && matchesType;
    });
  }, [projects, searchQuery, selectedTypeFilter]);

  if (!isOpen) return null;

  const handleDelete = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (confirmDeleteId !== id) {
      setConfirmDeleteId(id);
      return;
    }

    try {
      setDeletingId(id);
      await onDeleteProject(id);
      setConfirmDeleteId(null);
    } catch (err) {
      console.error("Failed to delete project:", err);
    } finally {
      setDeletingId(null);
    }
  };

  const formatDate = (isoString?: string) => {
    if (!isoString) return "N/A";
    try {
      const date = new Date(isoString);
      return date.toLocaleDateString(undefined, {
        month: "short",
        day: "numeric",
        year: "numeric",
      });
    } catch {
      return isoString;
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-neutral-950/80 backdrop-blur-sm animate-in fade-in duration-150">
      <div 
        className="w-full max-w-3xl bg-neutral-900 border border-neutral-800 rounded-lg shadow-2xl overflow-hidden flex flex-col max-h-[85vh]"
        role="dialog"
        aria-modal="true"
        aria-labelledby="project-manager-title"
      >
        {/* Header */}
        <div className="px-5 py-3 border-b border-neutral-800 flex items-center justify-between bg-neutral-950">
          <div className="flex items-center space-x-2.5">
            <div className="w-7 h-7 rounded bg-amber-500 flex items-center justify-center text-neutral-950">
              <FolderOpen className="w-4 h-4 stroke-[2.5]" />
            </div>
            <div>
              <h2 id="project-manager-title" className="text-xs font-mono font-bold tracking-wider text-neutral-100 uppercase flex items-center gap-2">
                Project Workspace Manager
                <span className="text-[9px] font-mono text-amber-400 bg-amber-500/10 border border-amber-500/30 px-1.5 py-0.2 rounded">
                  {projects.length} PROJECTS
                </span>
              </h2>
            </div>
          </div>
          <div className="flex items-center space-x-1.5">
            <button
              onClick={() => {
                onClose();
                onOpenCreate();
              }}
              className="px-2.5 py-1 text-xs font-mono font-bold uppercase bg-amber-500 hover:bg-amber-400 text-neutral-950 rounded flex items-center space-x-1 transition"
            >
              <Plus className="w-3.5 h-3.5 stroke-[2.5]" />
              <span>New Project</span>
            </button>
            <button
              onClick={onClose}
              className="text-neutral-400 hover:text-white p-1 rounded transition"
              title="Close (Esc)"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Filter / Search Bar */}
        <div className="px-5 py-2.5 border-b border-neutral-800 bg-neutral-950 flex flex-col sm:flex-row items-center gap-2">
          {/* Search Input */}
          <div className="relative flex-1 w-full">
            <Search className="w-3.5 h-3.5 text-neutral-500 absolute left-2.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search projects..."
              className="w-full pl-8 pr-3 py-1 bg-neutral-900 border border-neutral-700 focus:border-amber-500 rounded text-xs font-mono text-neutral-200 placeholder-neutral-500 outline-none transition"
            />
          </div>

          {/* Type Filter Select */}
          <select
            value={selectedTypeFilter}
            onChange={(e) => setSelectedTypeFilter(e.target.value)}
            className="w-full sm:w-44 px-2 py-1 bg-neutral-900 border border-neutral-700 focus:border-amber-500 rounded text-xs font-mono text-neutral-300 outline-none cursor-pointer"
          >
            <option value="ALL">All Categories</option>
            <option value="Character">Character</option>
            <option value="Collectible Figure">Collectible Figure</option>
            <option value="Mask">Mask</option>
            <option value="Bust">Bust</option>
            <option value="Statue">Statue</option>
            <option value="Prop">Prop</option>
            <option value="Plaque">Plaque</option>
            <option value="Mechanical Part">Mechanical Part</option>
            <option value="Decorative Object">Decorative Object</option>
            <option value="Other">Other</option>
          </select>
        </div>

        {/* Projects List Content */}
        <div className="flex-1 overflow-y-auto p-4 space-y-2">
          {isLoading ? (
            <div className="flex flex-col items-center justify-center py-12 text-neutral-400 space-y-2">
              <Loader2 className="w-5 h-5 animate-spin text-amber-500" />
              <span className="text-xs font-mono">Loading projects...</span>
            </div>
          ) : filteredProjects.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-10 text-center border border-dashed border-neutral-800 rounded p-6">
              <Folder className="w-8 h-8 text-neutral-600 mb-2" />
              <span className="text-xs font-mono text-neutral-300 font-semibold">
                {projects.length === 0 ? "No Projects Found" : "No Matching Projects"}
              </span>
              <p className="text-[10px] font-mono text-neutral-500 mt-1 max-w-sm">
                {projects.length === 0
                  ? "Create your first Outlaw Forge CAD project to begin preparing and slicing meshes."
                  : "Try clearing your search query or changing the category filter."}
              </p>
            </div>
          ) : (
            filteredProjects.map((project) => {
              const isActive = project.id === activeProjectId;
              const isDeleting = deletingId === project.id;
              const isConfirming = confirmDeleteId === project.id;

              return (
                <div
                  key={project.id}
                  onClick={() => {
                    onSelectProject(project);
                    onClose();
                  }}
                  className={`group relative p-3 rounded border transition-all cursor-pointer flex flex-col sm:flex-row sm:items-center justify-between gap-3 ${
                    isActive
                      ? "bg-amber-500/10 border-amber-500/60"
                      : "bg-neutral-950/60 border-neutral-800 hover:border-neutral-700 hover:bg-neutral-950"
                  }`}
                >
                  <div className="flex items-start space-x-3 min-w-0">
                    <div
                      className={`w-8 h-8 rounded flex items-center justify-center shrink-0 mt-0.5 ${
                        isActive
                          ? "bg-amber-500 text-neutral-950"
                          : "bg-neutral-800 text-neutral-400 group-hover:text-neutral-200"
                      }`}
                    >
                      <Box className="w-4 h-4" />
                    </div>

                    <div className="min-w-0 space-y-0.5">
                      <div className="flex items-center space-x-2">
                        <span className="text-xs font-mono font-bold text-neutral-100 group-hover:text-amber-400 truncate">
                          {project.name}
                        </span>
                        {isActive && (
                          <span className="px-1.5 py-0.2 text-[8px] font-mono font-bold bg-amber-500 text-neutral-950 rounded flex items-center gap-1 shrink-0">
                            <CheckCircle2 className="w-2.5 h-2.5" />
                            ACTIVE
                          </span>
                        )}
                        <span className="px-1.5 py-0.2 text-[8px] font-mono bg-neutral-800 text-neutral-400 border border-neutral-700 rounded uppercase shrink-0">
                          {project.project_type}
                        </span>
                      </div>

                      {project.description && (
                        <p className="text-[11px] font-mono text-neutral-400 truncate max-w-lg">
                          {project.description}
                        </p>
                      )}

                      <div className="flex items-center space-x-3 text-[10px] font-mono text-neutral-500 pt-0.5">
                        <span className="flex items-center gap-1">
                          <Layers className="w-3 h-3 text-neutral-500" />
                          {project.working_models?.length || 0} Meshes
                        </span>
                        <span>/</span>
                        <span className="flex items-center gap-1">
                          <Clock className="w-3 h-3 text-neutral-500" />
                          {formatDate(project.updated_at)}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center space-x-1.5 shrink-0 self-end sm:self-center">
                    <button
                      onClick={(e) => handleDelete(project.id, e)}
                      disabled={isDeleting}
                      className={`px-2 py-1 text-[10px] font-mono rounded border transition flex items-center space-x-1 ${
                        isConfirming
                          ? "bg-rose-500 text-white border-rose-600 animate-pulse"
                          : "bg-neutral-900 border-neutral-800 text-neutral-400 hover:text-rose-400 hover:border-rose-900/60"
                      }`}
                      title={isConfirming ? "Click again to confirm delete" : "Delete Project"}
                    >
                      {isDeleting ? (
                        <Loader2 className="w-3 h-3 animate-spin" />
                      ) : (
                        <Trash2 className="w-3 h-3" />
                      )}
                      <span>{isConfirming ? "Confirm Delete" : "Delete"}</span>
                    </button>
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Footer */}
        <div className="px-5 py-2.5 border-t border-neutral-800 bg-neutral-950 flex items-center justify-between text-xs font-mono text-neutral-500">
          <span>{filteredProjects.length} projects displayed</span>
          <button
            onClick={onClose}
            className="px-3 py-1 bg-neutral-900 hover:bg-neutral-800 border border-neutral-700 text-neutral-300 rounded transition"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
