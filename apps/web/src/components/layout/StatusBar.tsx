"use client";

import React from "react";
import { HealthStatusResponse } from "@shared/types/api";
import { Cpu, Disc3, Gauge, Globe2 } from "lucide-react";

interface StatusBarProps {
  health: HealthStatusResponse | null;
  cursorCoords: { x: number; y: number; z: number };
  fps?: number;
  cameraMode?: "PERSPECTIVE" | "ORTHOGRAPHIC";
  unit?: string;
  gridStep?: string;
}

export function StatusBar({
  health,
  cursorCoords,
  fps = 60,
  cameraMode = "PERSPECTIVE",
  unit = "MM",
  gridStep = "10.0 mm",
}: StatusBarProps) {
  const isOnline = !!health && health.status === "healthy";

  return (
    <footer className="h-6 w-full bg-neutral-950 border-t border-neutral-800 px-3 flex items-center justify-between text-[10px] font-mono text-neutral-400 select-none z-50">
      {/* Left: Cursor 3D Coordinates & Unit */}
      <div className="flex items-center space-x-3">
        {/* Coordinates */}
        <div className="flex items-center space-x-1.5">
          <span className="text-neutral-500 font-semibold">XYZ:</span>
          <div className="flex items-center space-x-2 text-neutral-300">
            <span>
              <span className="text-rose-400">X</span> {cursorCoords.x >= 0 ? `+${cursorCoords.x.toFixed(2)}` : cursorCoords.x.toFixed(2)}
            </span>
            <span>
              <span className="text-emerald-400">Y</span> {cursorCoords.y >= 0 ? `+${cursorCoords.y.toFixed(2)}` : cursorCoords.y.toFixed(2)}
            </span>
            <span>
              <span className="text-amber-400">Z</span> {cursorCoords.z >= 0 ? `+${cursorCoords.z.toFixed(2)}` : cursorCoords.z.toFixed(2)}
            </span>
          </div>
        </div>

        <div className="h-3 w-[1px] bg-neutral-800" />

        {/* Unit & Grid step */}
        <div className="flex items-center space-x-1.5 text-neutral-400">
          <span>UNIT: <strong className="text-neutral-200">{unit}</strong></span>
          <span className="text-neutral-600">/</span>
          <span>GRID: <strong className="text-neutral-200">{gridStep}</strong></span>
        </div>
      </div>

      {/* Center: Camera & Render View */}
      <div className="hidden sm:flex items-center space-x-3 text-neutral-500">
        <div className="flex items-center space-x-1">
          <Globe2 className="w-3 h-3 text-neutral-400" />
          <span>CAM: <strong className="text-neutral-300">{cameraMode}</strong></span>
        </div>
        <span className="text-neutral-700">|</span>
        <div className="flex items-center space-x-1">
          <Disc3 className="w-3 h-3 text-neutral-400 animate-spin" style={{ animationDuration: "10s" }} />
          <span>SHADING: <strong className="text-neutral-300">MATCAP + WIRE</strong></span>
        </div>
      </div>

      {/* Right: Performance & Backend Connection Status */}
      <div className="flex items-center space-x-3">
        {/* FPS Indicator */}
        <div className="flex items-center space-x-1">
          <Gauge className="w-3 h-3 text-emerald-400" />
          <span className="text-neutral-300 font-medium">{fps} FPS</span>
          <span className="text-[9px] text-neutral-500">(16.6ms)</span>
        </div>

        <div className="h-3 w-[1px] bg-neutral-800" />

        {/* Connection State */}
        <div className="flex items-center space-x-1.5">
          <span
            className={`w-1.5 h-1.5 rounded-full ${
              isOnline ? "bg-emerald-400" : "bg-rose-500"
            }`}
          />
          <span className={isOnline ? "text-emerald-400 font-semibold" : "text-rose-400 font-semibold"}>
            {isOnline ? "API CONNECTED" : "API OFFLINE"}
          </span>
        </div>
      </div>
    </footer>
  );
}
