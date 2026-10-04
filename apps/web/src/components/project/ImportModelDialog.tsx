"use client";

import React, { useState, useRef } from "react";
import { Upload, FileUp, X, CheckCircle, AlertCircle, Loader2 } from "lucide-react";
import { apiClient } from "@/lib/api-client";
import { WorkingModel } from "@shared/types/api";

interface ImportModelDialogProps {
  isOpen: boolean;
  onClose: () => void;
  projectId: string;
  onModelImported: (model: WorkingModel) => void;
}

const SUPPORTED_EXTENSIONS = [".stl", ".obj", ".glb", ".gltf"];
const MAX_IMPORT_FILE_SIZE_MB = 500;
const MAX_IMPORT_FILE_SIZE_BYTES = MAX_IMPORT_FILE_SIZE_MB * 1024 * 1024;

export function ImportModelDialog({
  isOpen,
  onClose,
  projectId,
  onModelImported,
}: ImportModelDialogProps) {
  const [file, setFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  if (!isOpen) return null;

  const validateFile = (selectedFile: File): boolean => {
    const ext = "." + selectedFile.name.split(".").pop()?.toLowerCase();
    if (!SUPPORTED_EXTENSIONS.includes(ext)) {
      setError(`Unsupported file format '${ext}'. Supported formats: STL, OBJ, GLB, GLTF`);
      return false;
    }
    if (selectedFile.size > MAX_IMPORT_FILE_SIZE_BYTES) {
      setError(`File exceeds maximum allowed size of ${MAX_IMPORT_FILE_SIZE_MB}MB.`);
      return false;
    }
    setError(null);
    return true;
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const droppedFile = e.dataTransfer.files[0];
      if (validateFile(droppedFile)) {
        setFile(droppedFile);
      }
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const selectedFile = e.target.files[0];
      if (validateFile(selectedFile)) {
        setFile(selectedFile);
      }
    }
  };

  const handleUpload = async () => {
    if (!file) {
      setError("Choose a 3D model file before importing.");
      return;
    }
    if (!projectId) {
      setError("Select or create a project before importing this model.");
      return;
    }
    setIsUploading(true);
    setError(null);

    try {
      const model = await apiClient.importModel(projectId, file);
      setSuccess(true);
      setTimeout(() => {
        onModelImported(model);
        onClose();
        setSuccess(false);
        setFile(null);
      }, 700);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to import 3D model.");
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-neutral-950/80 backdrop-blur-sm p-4 animate-in fade-in duration-150">
      <div className="w-full max-w-lg bg-neutral-900 border border-neutral-800 rounded-lg shadow-2xl overflow-hidden flex flex-col">
        {/* Header */}
        <div className="h-10 px-4 border-b border-neutral-800 flex items-center justify-between bg-neutral-950">
          <div className="flex items-center space-x-2">
            <FileUp className="w-3.5 h-3.5 text-amber-500" />
            <span className="text-xs font-mono font-bold uppercase tracking-wider text-neutral-200">
              Import 3D Mesh
            </span>
          </div>
          <button
            onClick={onClose}
            className="text-neutral-400 hover:text-white p-1 rounded transition"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>

        {/* Body */}
        <div className="p-5 space-y-3 font-mono">
          {error && (
            <div className="p-2.5 bg-rose-500/10 border border-rose-500/30 rounded text-xs text-rose-400 flex items-start space-x-2">
              <AlertCircle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          {success && (
            <div className="p-2.5 bg-emerald-500/10 border border-emerald-500/30 rounded text-xs text-emerald-400 flex items-center space-x-2">
              <CheckCircle className="w-3.5 h-3.5 shrink-0" />
              <span>Model imported and analyzed successfully.</span>
            </div>
          )}

          <div
            onDragOver={(e) => {
              e.preventDefault();
              setIsDragging(true);
            }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`border border-dashed rounded p-6 flex flex-col items-center justify-center text-center cursor-pointer transition-all ${
              isDragging
                ? "border-amber-500 bg-amber-500/10"
                : file
                ? "border-emerald-500/40 bg-emerald-950/10"
                : "border-neutral-700 hover:border-neutral-600 bg-neutral-950/60 hover:bg-neutral-950"
            }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".stl,.obj,.glb,.gltf"
              onChange={handleFileSelect}
              className="hidden"
            />
            {file ? (
              <div className="space-y-1.5">
                <CheckCircle className="w-6 h-6 text-emerald-400 mx-auto" />
                <p className="text-xs font-semibold text-neutral-200">{file.name}</p>
                <p className="text-[11px] text-neutral-400">
                  {(file.size / (1024 * 1024)).toFixed(2)} MB / Ready for ingestion
                </p>
              </div>
            ) : (
              <div className="space-y-1.5">
                <Upload className="w-6 h-6 text-amber-500 mx-auto" />
                <p className="text-xs font-semibold text-neutral-200">
                  Drag and drop 3D mesh or click to browse
                </p>
                <p className="text-[10px] text-neutral-500">
                  Formats: STL, OBJ, GLB, GLTF (Max {MAX_IMPORT_FILE_SIZE_MB}MB)
                </p>
              </div>
            )}
          </div>

          <div className="text-[10px] text-neutral-400 bg-neutral-950 p-2.5 rounded border border-neutral-800 space-y-0.5">
            <p className="text-amber-500 font-semibold uppercase">Geometry Invariants:</p>
            <p>- Raw source files are preserved immutably in isolated storage.</p>
            <p>- Spatial coordinates normalized strictly to millimetres (mm).</p>
          </div>
        </div>

        {/* Footer */}
        <div className="h-11 px-4 border-t border-neutral-800 bg-neutral-950 flex items-center justify-between">
          <button
            onClick={onClose}
            disabled={isUploading}
            className="px-3 py-1 bg-neutral-900 hover:bg-neutral-800 border border-neutral-700 text-xs font-mono text-neutral-300 rounded transition"
          >
            Cancel
          </button>
          <button
            onClick={handleUpload}
            disabled={!file || !projectId || isUploading || success}
            className="px-4 py-1 bg-amber-500 hover:bg-amber-400 text-neutral-950 font-mono font-bold text-xs rounded transition flex items-center space-x-1.5 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isUploading ? (
              <>
                <Loader2 className="w-3 h-3 animate-spin" />
                <span>Ingesting...</span>
              </>
            ) : (
              <>
                <FileUp className="w-3 h-3" />
                <span>{projectId ? "Import Mesh" : "Select Project First"}</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
