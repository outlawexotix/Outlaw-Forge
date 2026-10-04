"use client";

import React, { useState, useEffect } from "react";
import { ProjectCreatePayload, ProjectType, PrinterProfile } from "@shared/types/api";
import { 
  X, 
  FolderPlus, 
  Layers, 
  Printer, 
  FileText, 
  Check, 
  AlertCircle,
  Loader2
} from "lucide-react";

export const PROJECT_TYPES: { value: ProjectType; label: string; iconDesc: string }[] = [
  { value: "Character", label: "Character", iconDesc: "Full body figures, game avatars, heroes" },
  { value: "Collectible Figure", label: "Collectible Figure", iconDesc: "Anime, scale miniatures, tabletop" },
  { value: "Mask", label: "Mask", iconDesc: "Wearable masks, cosplay helms, faceplates" },
  { value: "Bust", label: "Bust", iconDesc: "Head and shoulder sculpts, anatomical studies" },
  { value: "Statue", label: "Statue", iconDesc: "Monumental poses, diorama centrepieces" },
  { value: "Prop", label: "Prop", iconDesc: "Weapons, armor pieces, movie replica props" },
  { value: "Plaque", label: "Plaque", iconDesc: "Wall reliefs, emblems, signage and badges" },
  { value: "Mechanical Part", label: "Mechanical Part", iconDesc: "Functional gears, brackets, enclosures" },
  { value: "Decorative Object", label: "Decorative Object", iconDesc: "Vases, lampshades, artistic sculptures" },
  { value: "Other", label: "Other", iconDesc: "Custom generic mesh models" },
];

interface CreateProjectDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onCreate: (payload: ProjectCreatePayload) => Promise<void> | void;
  printers: PrinterProfile[];
  isCreating?: boolean;
}

export function CreateProjectDialog({
  isOpen,
  onClose,
  onCreate,
  printers,
  isCreating = false,
}: CreateProjectDialogProps) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [projectType, setProjectType] = useState<ProjectType>("Character");
  const [selectedPrinterId, setSelectedPrinterId] = useState<string>("");
  const [notes, setNotes] = useState("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Initialize / reset default values when opened
  useEffect(() => {
    if (isOpen) {
      setName("");
      setDescription("");
      setProjectType("Character");
      setSelectedPrinterId(printers[0]?.id || "");
      setNotes("");
      setErrorMessage(null);
    }
  }, [isOpen, printers]);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setErrorMessage("Project name is required.");
      return;
    }

    setErrorMessage(null);
    try {
      await onCreate({
        name: name.trim(),
        description: description.trim(),
        project_type: projectType,
        selected_printer_id: selectedPrinterId || undefined,
        notes: notes.trim(),
      });
      onClose();
    } catch (err: unknown) {
      setErrorMessage(err instanceof Error ? err.message : "Failed to create project");
    }
  };

  const selectedPrinter = printers.find((p) => p.id === selectedPrinterId);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-neutral-950/80 backdrop-blur-sm animate-in fade-in duration-150">
      <div 
        className="w-full max-w-2xl bg-neutral-900 border border-neutral-800 rounded-lg shadow-2xl overflow-hidden flex flex-col max-h-[90vh]"
        role="dialog"
        aria-modal="true"
        aria-labelledby="create-project-title"
      >
        {/* Modal Header */}
        <div className="px-5 py-3 border-b border-neutral-800 flex items-center justify-between bg-neutral-950">
          <div className="flex items-center space-x-2.5">
            <div className="w-7 h-7 rounded bg-amber-500 flex items-center justify-center text-neutral-950">
              <FolderPlus className="w-4 h-4 stroke-[2.5]" />
            </div>
            <div>
              <h2 id="create-project-title" className="text-xs font-mono font-bold tracking-wider text-neutral-100 uppercase flex items-center gap-2">
                Create CAD Project
                <span className="text-[9px] font-mono text-amber-400 bg-amber-500/10 border border-amber-500/30 px-1.5 py-0.2 rounded">
                  NEW
                </span>
              </h2>
            </div>
          </div>
          <button
            onClick={onClose}
            disabled={isCreating}
            className="text-neutral-400 hover:text-white hover:bg-neutral-800 p-1 rounded transition"
            title="Close (Esc)"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Modal Body / Form */}
        <form onSubmit={handleSubmit} className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
          {errorMessage && (
            <div className="p-2.5 bg-rose-500/10 border border-rose-500/30 rounded text-rose-400 text-xs font-mono flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{errorMessage}</span>
            </div>
          )}

          {/* Project Name Field */}
          <div className="space-y-1">
            <label className="text-xs font-mono font-semibold uppercase tracking-wider text-neutral-300 flex items-center justify-between">
              <span>
                Project Name <span className="text-amber-500">*</span>
              </span>
              <span className="text-[10px] text-neutral-500 font-normal">REQUIRED</span>
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g., Cyberpunk Helmet Mk3"
              required
              autoFocus
              disabled={isCreating}
              className="w-full px-3 py-2 bg-neutral-950 border border-neutral-700 focus:border-amber-500 rounded text-xs font-mono text-neutral-100 placeholder-neutral-600 outline-none transition"
            />
          </div>

          {/* Project Type Grid */}
          <div className="space-y-1">
            <label className="text-xs font-mono font-semibold uppercase tracking-wider text-neutral-300 flex items-center justify-between">
              <span className="flex items-center gap-1.5">
                <Layers className="w-3.5 h-3.5 text-amber-500" />
                Project Type
              </span>
              <span className="text-[10px] text-amber-400 font-normal">{projectType}</span>
            </label>
            <div className="grid grid-cols-2 sm:grid-cols-5 gap-1.5">
              {PROJECT_TYPES.map((type) => {
                const isSelected = projectType === type.value;
                return (
                  <button
                    key={type.value}
                    type="button"
                    onClick={() => setProjectType(type.value)}
                    disabled={isCreating}
                    className={`px-2 py-1.5 rounded border text-left flex flex-col justify-between transition-all ${
                      isSelected
                        ? "bg-amber-500/10 border-amber-500 text-amber-300"
                        : "bg-neutral-950/60 border-neutral-800 text-neutral-400 hover:border-neutral-700 hover:text-neutral-200"
                    }`}
                  >
                    <div className="flex items-center justify-between w-full">
                      <span className="text-xs font-mono font-bold truncate">
                        {type.label}
                      </span>
                      {isSelected && <Check className="w-3 h-3 text-amber-400 shrink-0 ml-1" />}
                    </div>
                    <span className="text-[8px] font-mono text-neutral-500 truncate mt-0.5">
                      {type.iconDesc}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Description Field */}
          <div className="space-y-1">
            <label className="text-xs font-mono font-semibold uppercase tracking-wider text-neutral-300 flex items-center gap-1.5">
              <FileText className="w-3.5 h-3.5 text-neutral-400" />
              Description
            </label>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Optional notes regarding mesh prep or slicer settings"
              disabled={isCreating}
              className="w-full px-3 py-1.5 bg-neutral-950 border border-neutral-700 focus:border-amber-500 rounded text-xs font-mono text-neutral-100 placeholder-neutral-600 outline-none transition"
            />
          </div>

          {/* Printer Target Selection */}
          <div className="space-y-1">
            <label className="text-xs font-mono font-semibold uppercase tracking-wider text-neutral-300 flex items-center gap-1.5">
              <Printer className="w-3.5 h-3.5 text-amber-500" />
              Target Printer Profile
            </label>
            <select
              value={selectedPrinterId}
              onChange={(e) => setSelectedPrinterId(e.target.value)}
              disabled={isCreating}
              className="w-full px-3 py-1.5 bg-neutral-950 border border-neutral-700 focus:border-amber-500 rounded text-xs font-mono text-neutral-100 outline-none transition"
            >
              {printers.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.manufacturer} {p.model} ({p.build_width_mm}x{p.build_depth_mm}x{p.build_height_mm} mm)
                </option>
              ))}
            </select>
          </div>
        </form>

        {/* Modal Footer */}
        <div className="px-5 py-3 border-t border-neutral-800 bg-neutral-950 flex items-center justify-between">
          <button
            type="button"
            onClick={onClose}
            disabled={isCreating}
            className="px-3 py-1.5 text-xs font-mono font-medium text-neutral-400 hover:text-white hover:bg-neutral-800 rounded transition"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={isCreating || !name.trim()}
            className="px-4 py-1.5 text-xs font-mono font-bold text-neutral-950 bg-amber-500 hover:bg-amber-400 disabled:opacity-50 disabled:hover:bg-amber-500 rounded transition flex items-center space-x-1.5"
          >
            {isCreating ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                <span>INITIALIZING...</span>
              </>
            ) : (
              <>
                <FolderPlus className="w-3.5 h-3.5" />
                <span>CREATE PROJECT</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
