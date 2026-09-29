"use client";

import React, { useState, useMemo } from "react";
import { Project, ProjectType } from "@shared/types/api";
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
  Printer, 
  CheckCircle2, 
  AlertTriangle,
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
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in duration-200">
      <div 
        className="w-full max-w-3xl bg-[#0b101b] border border-slate-800 rounded-xl shadow-2xl shadow-cyan-950/30 overflow-hidden flex flex-col max-h-[85vh]"
        role="dialog"
        aria-modal="true"
        aria-labelledby="project-manager-title"
      >
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between bg-slate-900/50">
          <div className="flex items-center space-x-3">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center text-slate-950 shadow-glow-cyan">
              <FolderOpen className="w-4 h-4 font-black" />
            </div>
            <div>
              <h2 id="project-manager-title" className="text-sm font-mono font-bold tracking-wider text-slate-100 uppercase flex items-center gap-2">
                Project Workspace Manager
                <span className="text-[10px] font-mono font-normal text-cyan-400 bg-cyan-950/80 border border-cyan-800/60 px-2 py-0.5 rounded">
                  {projects.length} PROJECTS
                </span>
              </h2>
              <p className="text-xs font-mono text-slate-400 mt-0.5">
                Switch active projects, manage mesh assemblies, or initialize a new project
              </p>
            </div>
          </div>
          <div className="flex items-center space-x-2">
            <button
              onClick={() => {
                onClose();
                onOpenCreate();
              }}
              className="px-3 py-1.5 text-xs font-mono font-bold uppercase tracking-wider bg-cyan-500/15 hover:bg-cyan-500/25 border border-cyan-500/40 text-cyan-300 rounded-lg flex items-center space-x-1.5 transition"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>New Project</span>
            </button>
            <button
              onClick={onClose}
              className="text-slate-400 hover:text-slate-200 hover:bg-slate-800/80 p-1.5 rounded-lg transition-colors"
              title="Close (Esc)"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Filter / Search Bar */}
        <div className="px-6 py-3 border-b border-slate-800/80 bg-slate-950/40 flex flex-col sm:flex-row items-center gap-3">
          {/* Search Input */}
          <div className="relative flex-1 w-full">
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search projects by name, description, or notes..."
              className="w-full pl-9 pr-3 py-1.5 bg-slate-900/90 border border-slate-700/80 focus:border-cyan-400 rounded-lg text-xs font-mono text-slate-200 placeholder-slate-500 outline-none transition"
            />
          </div>

          {/* Type Filter Select */}
          <select
            value={selectedTypeFilter}
            onChange={(e) => setSelectedTypeFilter(e.target.value)}
            className="w-full sm:w-48 px-2.5 py-1.5 bg-slate-900/90 border border-slate-700/80 focus:border-cyan-400 rounded-lg text-xs font-mono text-slate-300 outline-none cursor-pointer"
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
        <div className="flex-1 overflow-y-auto p-6 space-y-3">
          {isLoading ? (
            <div className="flex flex-col items-center justify-center py-12 text-slate-400 space-y-2">
              <Loader2 className="w-6 h-6 animate-spin text-cyan-400" />
              <span className="text-xs font-mono">Loading projects...</span>
            </div>
          ) : filteredProjects.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-center border-2 border-dashed border-slate-800 rounded-xl p-8">
              <Folder className="w-10 h-10 text-slate-600 mb-2" />
              <span className="text-xs font-mono text-slate-300 font-semibold">
                {projects.length === 0 ? "No Projects Found" : "No Matching Projects"}
              </span>
              <p className="text-[11px] font-mono text-slate-500 mt-1 max-w-sm">
                {projects.length === 0
                  ? "Create your first Outlaw Forge CAD project to begin preparing and slicing meshes."
                  : "Try clearing your search query or changing the category filter."}
              </p>
              {projects.length === 0 && (
                <button
                  onClick={() => {
                    onClose();
                    onOpenCreate();
                  }}
                  className="mt-4 px-4 py-2 text-xs font-mono font-bold uppercase tracking-wider bg-cyan-500/15 hover:bg-cyan-500/25 border border-cyan-500/40 text-cyan-300 rounded-lg flex items-center space-x-1.5 transition"
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>Create Project</span>
                </button>
              )}
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
                  className={`group relative p-4 rounded-xl border transition-all cursor-pointer flex flex-col sm:flex-row sm:items-center justify-between gap-4 ${
                    isActive
                      ? "bg-cyan-950/30 border-cyan-500/60 shadow-glow-cyan"
                      : "bg-slate-900/40 border-slate-800/80 hover:border-slate-700 hover:bg-slate-900/70"
                  }`}
                >
                  {/* Left: Project Info */}
                  <div className="flex items-start space-x-3.5 flex-1 min-w-0">
                    <div className={`p-2.5 rounded-lg shrink-0 mt-0.5 ${
                      isActive ? "bg-cyan-500/20 text-cyan-400 border border-cyan-500/40" : "bg-slate-800 text-slate-400"
                    }`}>
                      <Box className="w-4 h-4" />
                    </div>
                    <div className="space-y-1 min-w-0 flex-1">
                      <div className="flex items-center space-x-2 flex-wrap gap-y-1">
                        <span className="font-mono text-sm font-bold text-slate-100 group-hover:text-cyan-300 transition-colors truncate">
                          {project.name}
                        </span>
                        <span className="px-2 py-0.5 text-[9px] font-mono font-semibold rounded bg-cyan-950/80 text-cyan-400 border border-cyan-800/60 uppercase">
                          {project.project_type}
                        </span>
                        {isActive && (
                          <span className="px-2 py-0.5 text-[9px] font-mono font-bold rounded bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 flex items-center gap-1">
                            <CheckCircle2 className="w-2.5 h-2.5" />
                            ACTIVE
                          </span>
                        )}
                      </div>

                      {project.description && (
                        <p className="text-xs font-mono text-slate-400 line-clamp-1">
                          {project.description}
                        </p>
                      )}

                      {/* Meta stats badges */}
                      <div className="flex items-center space-x-3 text-[10px] font-mono text-slate-500 pt-1 flex-wrap gap-y-1">
                        <span className="flex items-center gap-1">
                          <Layers className="w-3 h-3 text-slate-400" />
                          {project.working_models?.length || 0} Models
                        </span>
                        <span>•</span>
                        <span className="flex items-center gap-1">
                          <Clock className="w-3 h-3 text-slate-400" />
                          Updated {formatDate(project.updated_at || project.created_at)}
                        </span>
                        {project.notes && (
                          <>
                            <span>•</span>
                            <span className="text-slate-400 italic truncate max-w-[200px]">
                              &ldquo;{project.notes}&rdquo;
                            </span>
                          </>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Right: Actions */}
                  <div className="flex items-center space-x-2 shrink-0 self-end sm:self-center">
                    {isConfirming ? (
                      <div 
                        className="flex items-center space-x-2 bg-rose-950/80 border border-rose-500/40 px-2 py-1 rounded-lg animate-in fade-in"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <AlertTriangle className="w-3.5 h-3.5 text-rose-400" />
                        <span className="text-[10px] font-mono text-rose-300">Confirm delete?</span>
                        <button
                          onClick={(e) => handleDelete(project.id, e)}
                          disabled={isDeleting}
                          className="px-2 py-0.5 text-[10px] font-mono font-bold bg-rose-600 hover:bg-rose-500 text-white rounded transition"
                        >
                          {isDeleting ? "..." : "YES"}
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setConfirmDeleteId(null);
                          }}
                          className="px-2 py-0.5 text-[10px] font-mono bg-slate-800 hover:bg-slate-700 text-slate-300 rounded transition"
                        >
                          NO
                        </button>
                      </div>
                    ) : (
                      <button
                        onClick={(e) => handleDelete(project.id, e)}
                        className="p-2 text-slate-500 hover:text-rose-400 hover:bg-rose-950/40 rounded-lg border border-transparent hover:border-rose-800/40 transition opacity-0 group-hover:opacity-100"
                        title="Delete Project"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    )}

                    <button
                      onClick={() => {
                        onSelectProject(project);
                        onClose();
                      }}
                      className={`px-3 py-1.5 text-xs font-mono font-semibold rounded-lg border transition ${
                        isActive
                          ? "bg-cyan-500/20 text-cyan-300 border-cyan-500/40 hover:bg-cyan-500/30"
                          : "bg-slate-800 text-slate-300 border-slate-700 hover:bg-slate-700 hover:text-white"
                      }`}
                    >
                      {isActive ? "Current" : "Switch"}
                    </button>
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-slate-800 bg-slate-900/40 flex items-center justify-between text-xs font-mono text-slate-500">
          <span>Click any project to switch active CAD workspace.</span>
          <button
            onClick={onClose}
            className="px-3 py-1 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded transition"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
