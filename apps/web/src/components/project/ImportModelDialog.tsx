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
    if (selectedFile.size > 100 * 1024 * 1024) {
      setError("File exceeds maximum allowed size of 100MB.");
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
    if (!file || !projectId) return;
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
    } catch (err: any) {
      setError(err.message || "Failed to import 3D model.");
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4">
      <div className="w-full max-w-lg bg-slate-950 border border-slate-800 rounded-xl shadow-2xl overflow-hidden flex flex-col animate-in fade-in zoom-in-95 duration-200">
        {/* Header */}
        <div className="h-12 px-5 border-b border-slate-800/80 flex items-center justify-between bg-slate-900/60">
          <div className="flex items-center space-x-2">
            <FileUp className="w-4 h-4 text-cyan-400" />
            <span className="text-xs font-mono font-bold uppercase tracking-wider text-slate-200">
              Import 3D Model
            </span>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-200 p-1 rounded hover:bg-slate-800 transition"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Body */}
        <div className="p-6 space-y-4 font-mono">
          {error && (
            <div className="p-3 bg-rose-500/10 border border-rose-500/30 rounded text-xs text-rose-400 flex items-start space-x-2">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          {success && (
            <div className="p-3 bg-emerald-500/10 border border-emerald-500/30 rounded text-xs text-emerald-400 flex items-center space-x-2">
              <CheckCircle className="w-4 h-4 shrink-0" />
              <span>Model imported and analyzed successfully!</span>
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
            className={`border-2 border-dashed rounded-xl p-8 flex flex-col items-center justify-center text-center cursor-pointer transition-all ${
              isDragging
                ? "border-cyan-400 bg-cyan-950/20"
                : file
                ? "border-emerald-500/40 bg-emerald-950/10"
                : "border-slate-800 hover:border-slate-700 bg-slate-900/30 hover:bg-slate-900/50"
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
              <div className="space-y-2">
                <CheckCircle className="w-8 h-8 text-emerald-400 mx-auto" />
                <p className="text-sm font-semibold text-slate-200">{file.name}</p>
                <p className="text-xs text-slate-400">
                  {(file.size / (1024 * 1024)).toFixed(2)} MB • Ready for ingestion
                </p>
              </div>
            ) : (
              <div className="space-y-2">
                <Upload className="w-8 h-8 text-cyan-400 mx-auto" />
                <p className="text-sm font-semibold text-slate-200">
                  Drag & Drop 3D mesh or click to browse
                </p>
                <p className="text-xs text-slate-400">
                  Supports binary/ASCII STL, Wavefront OBJ, GLB, and GLTF (Max 100MB)
                </p>
              </div>
            )}
          </div>

          <div className="text-[11px] text-slate-400 bg-slate-900/50 p-3 rounded border border-slate-800/80 space-y-1">
            <p className="text-cyan-400 font-semibold">Deterministic Invariants:</p>
            <p>• Original source files are preserved immutably in isolated storage.</p>
            <p>• Linear spatial dimensions are normalized to millimeters (mm) without silent conversion.</p>
          </div>
        </div>

        {/* Footer */}
        <div className="h-14 px-6 border-t border-slate-800/80 bg-slate-900/40 flex items-center justify-between">
          <button
            onClick={onClose}
            disabled={isUploading}
            className="px-4 py-2 bg-slate-900 hover:bg-slate-800 border border-slate-700 text-xs font-mono text-slate-300 rounded transition"
          >
            Cancel
          </button>
          <button
            onClick={handleUpload}
            disabled={!file || isUploading || success}
            className="px-5 py-2 bg-gradient-to-r from-cyan-600 to-cyan-500 hover:from-cyan-500 hover:to-cyan-400 text-slate-950 font-mono font-bold text-xs rounded transition flex items-center space-x-2 disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-cyan-950/50"
          >
            {isUploading ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                <span>Ingesting & Analyzing...</span>
              </>
            ) : (
              <>
                <FileUp className="w-3.5 h-3.5" />
                <span>Import to Project</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
