"use client";

import React, { useState, useEffect } from "react";
import { ProjectCreatePayload, ProjectType, PrinterProfile } from "@shared/types/api";
import { 
  X, 
  FolderPlus, 
  Layers, 
  Printer, 
  FileText, 
  Sparkles, 
  Check, 
  AlertCircle,
  Loader2
} from "lucide-react";

export const PROJECT_TYPES: { value: ProjectType; label: string; iconDesc: string }[] = [
  { value: "Character", label: "Character", iconDesc: "Full body figures, game avatars, heroes" },
  { value: "Collectible Figure", label: "Collectible Figure", iconDesc: "Anime, scale miniatures, tabletop" },
  { value: "Mask", label: "Mask", iconDesc: "Wearable masks, cosplay helms, faceplates" },
  { value: "Bust", label: "Bust", iconDesc: "Head & shoulder sculpts, anatomical studies" },
  { value: "Statue", label: "Statue", iconDesc: "Monumental poses, diorama centrepieces" },
  { value: "Prop", label: "Prop", iconDesc: "Weapons, armor pieces, movie replica props" },
  { value: "Plaque", label: "Plaque", iconDesc: "Wall reliefs, emblems, signage & badges" },
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
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in duration-200">
      <div 
        className="w-full max-w-2xl bg-[#0b101b] border border-slate-800 rounded-xl shadow-2xl shadow-cyan-950/30 overflow-hidden flex flex-col max-h-[90vh]"
        role="dialog"
        aria-modal="true"
        aria-labelledby="create-project-title"
      >
        {/* Modal Header */}
        <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between bg-slate-900/50">
          <div className="flex items-center space-x-3">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center text-slate-950 shadow-glow-cyan">
              <FolderPlus className="w-4 h-4 font-black" />
            </div>
            <div>
              <h2 id="create-project-title" className="text-sm font-mono font-bold tracking-wider text-slate-100 uppercase flex items-center gap-2">
                Create New Project
                <span className="text-[10px] font-mono font-normal text-cyan-400 bg-cyan-950/80 border border-cyan-800/60 px-2 py-0.5 rounded">
                  STAGE 01
                </span>
              </h2>
              <p className="text-xs font-mono text-slate-400 mt-0.5">
                Configure taxonomy, target build volume, and mesh fabrication parameters
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            disabled={isCreating}
            className="text-slate-400 hover:text-slate-200 hover:bg-slate-800/80 p-1.5 rounded-lg transition-colors"
            title="Close (Esc)"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Modal Body / Form */}
        <form onSubmit={handleSubmit} className="flex-1 overflow-y-auto px-6 py-5 space-y-5">
          {errorMessage && (
            <div className="p-3 bg-rose-500/10 border border-rose-500/30 rounded-lg text-rose-400 text-xs font-mono flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{errorMessage}</span>
            </div>
          )}

          {/* Project Name Field */}
          <div className="space-y-1.5">
            <label className="text-xs font-mono font-semibold uppercase tracking-wider text-slate-300 flex items-center justify-between">
              <span>
                Project Name <span className="text-cyan-400">*</span>
              </span>
              <span className="text-[10px] text-slate-500 font-normal">REQUIRED</span>
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g., Cyberpunk Oni Mask v2"
              required
              autoFocus
              disabled={isCreating}
              className="w-full px-3.5 py-2.5 bg-slate-900/90 border border-slate-700/80 focus:border-cyan-400 focus:ring-1 focus:ring-cyan-400/50 rounded-lg text-sm font-mono text-slate-100 placeholder-slate-500 outline-none transition"
            />
          </div>

          {/* Project Type Grid / Selector */}
          <div className="space-y-1.5">
            <label className="text-xs font-mono font-semibold uppercase tracking-wider text-slate-300 flex items-center justify-between">
              <span className="flex items-center gap-1.5">
                <Layers className="w-3.5 h-3.5 text-cyan-400" />
                Project Type & Category (10 Types)
              </span>
              <span className="text-[10px] text-cyan-400 font-normal">{projectType}</span>
            </label>
            <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
              {PROJECT_TYPES.map((type) => {
                const isSelected = projectType === type.value;
                return (
                  <button
                    key={type.value}
                    type="button"
                    onClick={() => setProjectType(type.value)}
                    disabled={isCreating}
                    className={`px-2.5 py-2 rounded-lg border text-left flex flex-col justify-between transition-all ${
                      isSelected
                        ? "bg-cyan-950/60 border-cyan-400 text-cyan-200 shadow-glow-cyan"
                        : "bg-slate-900/50 border-slate-800 text-slate-400 hover:border-slate-700 hover:text-slate-200"
                    }`}
                  >
                    <div className="flex items-center justify-between w-full">
                      <span className="text-xs font-mono font-bold truncate">
                        {type.label}
                      </span>
                      {isSelected && <Check className="w-3 h-3 text-cyan-400 shrink-0 ml-1" />}
                    </div>
                    <span className="text-[9px] font-mono text-slate-500 truncate mt-1">
                      {type.iconDesc}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Description Field */}
          <div className="space-y-1.5">
            <label className="text-xs font-mono font-semibold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
              <FileText className="w-3.5 h-3.5 text-cyan-400" />
              Description
            </label>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="e.g., High-resolution mesh split into 3 wearable interlocking segments"
              disabled={isCreating}
              className="w-full px-3.5 py-2 bg-slate-900/90 border border-slate-700/80 focus:border-cyan-400 focus:ring-1 focus:ring-cyan-400/50 rounded-lg text-xs font-mono text-slate-100 placeholder-slate-500 outline-none transition"
            />
          </div>

          {/* Printer Selector */}
          <div className="space-y-1.5">
            <label className="text-xs font-mono font-semibold uppercase tracking-wider text-slate-300 flex items-center justify-between">
              <span className="flex items-center gap-1.5">
                <Printer className="w-3.5 h-3.5 text-cyan-400" />
                Target 3D Printer Profile
              </span>
              {selectedPrinter && (
                <span className="text-[10px] font-mono text-emerald-400">
                  {selectedPrinter.build_width_mm} × {selectedPrinter.build_depth_mm} × {selectedPrinter.build_height_mm} mm
                </span>
              )}
            </label>
            <select
              value={selectedPrinterId}
              onChange={(e) => setSelectedPrinterId(e.target.value)}
              disabled={isCreating}
              className="w-full px-3.5 py-2.5 bg-slate-900/90 border border-slate-700/80 focus:border-cyan-400 focus:ring-1 focus:ring-cyan-400/50 rounded-lg text-xs font-mono text-slate-100 outline-none cursor-pointer transition"
            >
              <option value="">None / Unassigned Profile</option>
              {printers.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.manufacturer} {p.model} ({p.build_width_mm}×{p.build_depth_mm}×{p.build_height_mm}mm, nozzle {p.nozzle_diameter_mm}mm)
                </option>
              ))}
            </select>
          </div>

          {/* Notes Field */}
          <div className="space-y-1.5">
            <label className="text-xs font-mono font-semibold uppercase tracking-wider text-slate-300 flex items-center justify-between">
              <span>Fabrication Notes & Slicing Directives</span>
              <span className="text-[10px] text-slate-500 font-normal">OPTIONAL</span>
            </label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="e.g., Target 0.12mm layer height with tree supports. PLA+ Carbon Fiber filament."
              rows={3}
              disabled={isCreating}
              className="w-full px-3.5 py-2 bg-slate-900/90 border border-slate-700/80 focus:border-cyan-400 focus:ring-1 focus:ring-cyan-400/50 rounded-lg text-xs font-mono text-slate-100 placeholder-slate-500 outline-none resize-none transition"
            />
          </div>

          {/* Action Buttons */}
          <div className="pt-3 border-t border-slate-800 flex items-center justify-end space-x-3">
            <button
              type="button"
              onClick={onClose}
              disabled={isCreating}
              className="px-4 py-2 text-xs font-mono text-slate-400 hover:text-slate-100 hover:bg-slate-800/80 rounded-lg transition"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isCreating || !name.trim()}
              className="px-5 py-2 text-xs font-mono font-bold uppercase tracking-wider bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-slate-950 rounded-lg shadow-glow-cyan disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-2 transition"
            >
              {isCreating ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>Creating Project...</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-3.5 h-3.5 font-bold" />
                  <span>Initialize Project</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
