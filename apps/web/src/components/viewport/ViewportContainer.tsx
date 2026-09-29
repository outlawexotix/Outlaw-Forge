'use client';

import React, { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { Canvas, useThree } from '@react-three/fiber';
import { OrbitControls, PerspectiveCamera, OrthographicCamera } from '@react-three/drei';
import type { OrbitControls as OrbitControlsImpl } from 'three-stdlib';
import * as THREE from 'three';
import { BuildPlate } from './BuildPlate';
import { SceneLights } from './SceneLights';
import { OrientationGizmo } from './OrientationGizmo';
import { ModelRenderer } from './ModelRenderer';
import { CuttingPlane } from './CuttingPlane';
import { PrinterProfile, WorkingModel } from '@shared/types/api';
import { PresetView, ViewportSettings } from '@shared/types/viewport';
import {
  BoundingBox3D,
  MeshMetrics,
  calculatePresetCameraView,
  frameObjectInCamera,
} from '@three-tools';
import {
  Box,
  Eye,
  Grid,
  Layers,
  RotateCcw,
  Maximize2,
  Compass,
  AlertCircle,
  Loader2,
  Crosshair,
} from 'lucide-react';

const DEFAULT_PRINTER: PrinterProfile = {
  id: 'bambu-x1c',
  manufacturer: 'Bambu Lab',
  model: 'X1-Carbon',
  build_width_mm: 256,
  build_depth_mm: 256,
  build_height_mm: 256,
  nozzle_diameter_mm: 0.4,
};

const DEFAULT_SETTINGS: ViewportSettings = {
  showGrid: true,
  showEnvelope: true,
  showOrigin: true,
  showBoundingBoxes: true,
  showWireframe: false,
  cameraProjection: 'perspective',
  backgroundColor: '#090d16',
  gridMajorStepMm: 10,
  gridMinorStepMm: 1,
};

export interface ViewportContainerProps {
  printer?: PrinterProfile;
  model?: WorkingModel | null;
  modelBuffer?: ArrayBuffer | null;
  modelUrl?: string | null;
  activeTool?: 'select' | 'move' | 'rotate' | 'scale' | 'slice' | 'inspect';
  slicePlaneOrigin?: [number, number, number];
  slicePlaneNormal?: [number, number, number];
  className?: string;
  onModelMetrics?: (metrics: MeshMetrics) => void;
  onCursorCoordinates?: (coords: { x: number; y: number; z: number }) => void;
  onTransformChange?: (transform: { position: [number, number, number]; rotation: [number, number, number]; scale: [number, number, number] }) => void;
}

/**
 * Internal helper component to catch mouse coordinates over the bed surface
 */
const BedRaycaster: React.FC<{
  bedWidth: number;
  bedDepth: number;
  onHover: (coords: { x: number; y: number; z: number }) => void;
}> = ({ bedWidth, bedDepth, onHover }) => {
  return (
    <mesh
      position={[0, 0, 0]}
      visible={false}
      onPointerMove={(e) => {
        e.stopPropagation();
        if (e.point) {
          // Point in slicer coords (since inside SlicerSpaceRoot group)
          onHover({
            x: Math.round(e.point.x * 10) / 10,
            y: Math.round(e.point.y * 10) / 10,
            z: Math.round(e.point.z * 10) / 10,
          });
        }
      }}
    >
      <planeGeometry args={[bedWidth * 1.5, bedDepth * 1.5]} />
      <meshBasicMaterial />
    </mesh>
  );
};

export const ViewportContainer: React.FC<ViewportContainerProps> = ({
  printer = DEFAULT_PRINTER,
  model = null,
  modelBuffer = null,
  modelUrl = null,
  activeTool = 'select',
  slicePlaneOrigin,
  slicePlaneNormal,
  className = '',
  onModelMetrics,
  onCursorCoordinates,
  onTransformChange,
}) => {
  const [settings, setSettings] = useState<ViewportSettings>(DEFAULT_SETTINGS);
  const [activeView, setActiveView] = useState<PresetView>('isometric');
  const [modelMetrics, setModelMetrics] = useState<MeshMetrics | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isGizmoDragging, setIsGizmoDragging] = useState<boolean>(false);

  const controlsRef = useRef<OrbitControlsImpl>(null);
  const canvasContainerRef = useRef<HTMLDivElement>(null);


  const bedWidth = printer.build_width_mm || 256;
  const bedDepth = printer.build_depth_mm || 256;
  const bedHeight = printer.build_height_mm || 256;

  const defaultBounds: BoundingBox3D = useMemo(
    () => ({
      min: { x: -bedWidth / 2, y: -bedDepth / 2, z: 0 },
      max: { x: bedWidth / 2, y: bedDepth / 2, z: bedHeight },
      center: { x: 0, y: 0, z: bedHeight / 2 },
      dimensions: { x: bedWidth, y: bedDepth, z: bedHeight },
    }),
    [bedWidth, bedDepth, bedHeight]
  );

  // Transition to standard CAD Preset View
  const handlePresetView = useCallback(
    (view: PresetView) => {
      setActiveView(view);
      if (!controlsRef.current) return;

      const boundsToFrame = modelMetrics?.boundingBox || defaultBounds;
      const { position, target } = calculatePresetCameraView(
        view,
        boundsToFrame,
        45,
        view === 'isometric' ? 1.6 : 1.4
      );

      controlsRef.current.object.position.copy(position);
      controlsRef.current.target.copy(target);
      controlsRef.current.update();
    },
    [modelMetrics, defaultBounds]
  );

  // Frame active model ($F$ shortcut)
  const handleFrameSelection = useCallback(() => {
    if (!controlsRef.current) return;
    const boundsToFrame = modelMetrics?.boundingBox || defaultBounds;
    const { position, target } = calculatePresetCameraView('isometric', boundsToFrame, 45, 1.3);

    controlsRef.current.object.position.copy(position);
    controlsRef.current.target.copy(target);
    controlsRef.current.update();
  }, [modelMetrics, defaultBounds]);

  const resetCamera = useCallback(() => {
    handlePresetView('isometric');
  }, [handlePresetView]);

  // Global CAD Hotkeys (F for Frame, R for Reset, 1-4 for Views)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Don't capture when typing in text fields
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes((e.target as HTMLElement)?.tagName)) {
        return;
      }

      if (e.key === 'f' || e.key === 'F') {
        e.preventDefault();
        handleFrameSelection();
      } else if (e.key === 'r' || e.key === 'R') {
        e.preventDefault();
        resetCamera();
      } else if (e.key === '1') {
        e.preventDefault();
        handlePresetView('isometric');
      } else if (e.key === '2') {
        e.preventDefault();
        handlePresetView('top');
      } else if (e.key === '3') {
        e.preventDefault();
        handlePresetView('front');
      } else if (e.key === '4') {
        e.preventDefault();
        handlePresetView('right');
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleFrameSelection, resetCamera, handlePresetView]);

  const handleModelLoaded = (geom: THREE.BufferGeometry, metrics: MeshMetrics) => {
    setModelMetrics(metrics);
    setLoading(false);
    setErrorMessage(null);
    if (onModelMetrics) {
      onModelMetrics(metrics);
    }
  };

  const handleModelError = (err: string) => {
    setErrorMessage(err);
    setLoading(false);
  };

  const toggleProjection = () => {
    setSettings((s) => ({
      ...s,
      cameraProjection: s.cameraProjection === 'perspective' ? 'orthographic' : 'perspective',
    }));
  };

  return (
    <div
      ref={canvasContainerRef}
      className={`relative w-full h-full min-h-[500px] overflow-hidden bg-[#090d16] select-none ${className}`}
    >
      {/* 3D Canvas Scene */}
      <Canvas
        shadows
        className="w-full h-full"
        gl={{
          antialias: true,
          powerPreference: 'high-performance',
          alpha: false,
        }}
      >
        <color attach="background" args={[settings.backgroundColor]} />

        {settings.cameraProjection === 'perspective' ? (
          <PerspectiveCamera
            makeDefault
            position={[200, 220, 220]}
            fov={45}
            near={0.5}
            far={5000}
          />
        ) : (
          <OrthographicCamera
            makeDefault
            position={[200, 220, 220]}
            zoom={2.2}
            near={-2000}
            far={5000}
          />
        )}

        <OrbitControls
          ref={controlsRef}
          makeDefault
          target={[0, 25, 0]}
          enabled={!isGizmoDragging}
          enableDamping
          dampingFactor={0.08}
          minDistance={5}
          maxDistance={3000}
          screenSpacePanning
        />

        <SceneLights />

        {/* Slicer Space Root Group: Rotation -90 deg (-PI/2) on X-axis maps Z-up to Three.js Y-up */}
        <group rotation={[-Math.PI / 2, 0, 0]} name="SlicerSpaceRoot">
          {/* Build Plate Surface & Coordinate Grid */}
          <BuildPlate
            printer={printer}
            showEnvelope={settings.showEnvelope}
            showOrigin={settings.showOrigin}
            majorStep={settings.gridMajorStepMm}
            minorStep={settings.gridMinorStepMm}
          />

          {/* Model Mesh Loader & Renderer */}
          <ModelRenderer
            model={model}
            modelBuffer={modelBuffer}
            modelUrl={modelUrl}
            printer={printer}
            activeTool={activeTool}
            showBoundingBox={settings.showBoundingBoxes}
            showWireframe={settings.showWireframe}
            onModelLoaded={handleModelLoaded}
            onTransformChange={onTransformChange}
            onGizmoDragging={(dragging) => setIsGizmoDragging(dragging)}
            onError={handleModelError}
          />

          {/* Planar Slicing Cutting Plane */}
          {activeTool === 'slice' && (
            <CuttingPlane
              visible={true}
              planeOrigin={slicePlaneOrigin || [0, 0, model ? (model.bounds.dimensions_mm[2] / 2) : 25]}
              planeNormal={slicePlaneNormal || [0, 0, 1]}
              width={bedWidth}
              depth={bedDepth}
            />
          )}

          {/* Interactive raycast ground plane (muted during gizmo dragging) */}
          {onCursorCoordinates && !isGizmoDragging && (
            <BedRaycaster
              bedWidth={bedWidth}
              bedDepth={bedDepth}
              onHover={onCursorCoordinates}
            />
          )}
        </group>

        {/* Orientation Gizmo / View Cube */}
        <OrientationGizmo alignment="top-right" margin={[70, 70]} />
      </Canvas>

      {/* Floating HUD: Preset View Controls (Top-Left) */}
      <div className="absolute top-3 left-4 flex flex-col gap-2 pointer-events-auto z-20">
        <div className="flex items-center gap-1 p-1 bg-slate-950/85 backdrop-blur-md border border-slate-800/90 rounded-lg shadow-cad-panel text-xs text-slate-300">
          <button
            onClick={() => handlePresetView('isometric')}
            className={`px-2.5 py-1 rounded font-mono transition ${
              activeView === 'isometric'
                ? 'bg-cyan-600 text-white font-semibold shadow'
                : 'hover:bg-slate-800 text-slate-300'
            }`}
            title="Isometric View [1]"
          >
            ISO
          </button>
          <button
            onClick={() => handlePresetView('top')}
            className={`px-2.5 py-1 rounded font-mono transition ${
              activeView === 'top'
                ? 'bg-cyan-600 text-white font-semibold shadow'
                : 'hover:bg-slate-800 text-slate-300'
            }`}
            title="Top View [2]"
          >
            Top
          </button>
          <button
            onClick={() => handlePresetView('front')}
            className={`px-2.5 py-1 rounded font-mono transition ${
              activeView === 'front'
                ? 'bg-cyan-600 text-white font-semibold shadow'
                : 'hover:bg-slate-800 text-slate-300'
            }`}
            title="Front View [3]"
          >
            Front
          </button>
          <button
            onClick={() => handlePresetView('right')}
            className={`px-2.5 py-1 rounded font-mono transition ${
              activeView === 'right'
                ? 'bg-cyan-600 text-white font-semibold shadow'
                : 'hover:bg-slate-800 text-slate-300'
            }`}
            title="Right View [4]"
          >
            Right
          </button>
          <div className="w-[1px] h-4 bg-slate-800 mx-1" />
          <button
            onClick={handleFrameSelection}
            title="Frame Model [F]"
            className="p-1 hover:bg-slate-800 rounded text-slate-400 hover:text-cyan-400 transition"
          >
            <Maximize2 className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={resetCamera}
            title="Reset Camera [R]"
            className="p-1 hover:bg-slate-800 rounded text-slate-400 hover:text-slate-100 transition"
          >
            <RotateCcw className="w-3.5 h-3.5" />
          </button>
          <div className="w-[1px] h-4 bg-slate-800 mx-1" />
          <button
            onClick={toggleProjection}
            title="Toggle Perspective / Orthographic"
            className="px-2 py-1 bg-slate-900 hover:bg-slate-800 text-[10px] font-mono rounded text-cyan-300 border border-slate-700/60 transition"
          >
            {settings.cameraProjection === 'perspective' ? 'PERSP' : 'ORTHO'}
          </button>
        </div>

        {/* View toggles */}
        <div className="flex items-center gap-1.5 p-1 bg-slate-950/85 backdrop-blur-md border border-slate-800/90 rounded-lg shadow-cad-panel text-xs text-slate-400 w-fit">
          <button
            onClick={() => setSettings((s) => ({ ...s, showGrid: !s.showGrid }))}
            className={`p-1.5 rounded transition ${
              settings.showGrid ? 'text-cyan-400 bg-cyan-950/60 border border-cyan-500/30' : 'hover:text-white'
            }`}
            title="Toggle Bed Grid"
          >
            <Grid className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => setSettings((s) => ({ ...s, showEnvelope: !s.showEnvelope }))}
            className={`p-1.5 rounded transition ${
              settings.showEnvelope ? 'text-cyan-400 bg-cyan-950/60 border border-cyan-500/30' : 'hover:text-white'
            }`}
            title="Toggle Print Volume Envelope"
          >
            <Box className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => setSettings((s) => ({ ...s, showBoundingBoxes: !s.showBoundingBoxes }))}
            className={`p-1.5 rounded transition ${
              settings.showBoundingBoxes ? 'text-cyan-400 bg-cyan-950/60 border border-cyan-500/30' : 'hover:text-white'
            }`}
            title="Toggle Bounding Box"
          >
            <Layers className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => setSettings((s) => ({ ...s, showWireframe: !s.showWireframe }))}
            className={`p-1.5 rounded transition ${
              settings.showWireframe ? 'text-cyan-400 bg-cyan-950/60 border border-cyan-500/30' : 'hover:text-white'
            }`}
            title="Toggle Wireframe Overlay"
          >
            <Eye className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => setSettings((s) => ({ ...s, showOrigin: !s.showOrigin }))}
            className={`p-1.5 rounded transition ${
              settings.showOrigin ? 'text-cyan-400 bg-cyan-950/60 border border-cyan-500/30' : 'hover:text-white'
            }`}
            title="Toggle Origin Axes Triad"
          >
            <Crosshair className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Overhang Inspection HUD banner */}
      {activeTool === 'inspect' && (
        <div className="absolute top-3 left-1/2 -translate-x-1/2 bg-amber-950/90 border border-amber-500/50 rounded-lg px-3 py-1.5 shadow-glow-amber text-xs font-mono text-amber-200 flex items-center gap-2 z-20">
          <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
          <span className="font-bold text-amber-300">OVERHANG INSPECTION ACTIVE</span>
          <span className="text-[11px] text-amber-400/80">| Downward faces &gt; 45° in Amber/Red</span>
        </div>
      )}

      {/* Loading Overlay */}
      {loading && (
        <div className="absolute inset-0 bg-slate-950/60 backdrop-blur-sm flex flex-col items-center justify-center z-30 pointer-events-none">
          <Loader2 className="w-8 h-8 text-cyan-400 animate-spin" />
          <span className="mt-2 text-xs font-mono text-cyan-200">Parsing 3D Geometry...</span>
        </div>
      )}

      {/* Error Alert Overlay */}
      {errorMessage && (
        <div className="absolute top-16 left-4 max-w-sm bg-red-950/90 border border-red-800 rounded-lg p-3 text-xs text-red-200 shadow-xl flex items-start gap-2 z-30">
          <AlertCircle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
          <div>
            <div className="font-semibold text-red-300">Model Load Error</div>
            <div className="text-[11px] text-red-200/90 mt-0.5">{errorMessage}</div>
          </div>
        </div>
      )}

      {/* Engineering Precision HUD (Bottom-Left) */}
      <div className="absolute bottom-3 left-4 flex items-center gap-3 px-3 py-1.5 bg-slate-950/85 backdrop-blur-md border border-slate-800/90 rounded-lg shadow-cad-panel text-xs font-mono text-slate-300 z-20">
        <div className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
          <span className="text-slate-400">Scale:</span>
          <span className="text-white font-semibold">1 unit = 1.0 mm</span>
        </div>
        <div className="w-[1px] h-3.5 bg-slate-800" />
        <div>
          <span className="text-slate-400">Bed:</span>{' '}
          <span>{bedWidth} × {bedDepth} × {bedHeight} mm</span>
        </div>
        {modelMetrics && (
          <>
            <div className="w-[1px] h-3.5 bg-slate-800" />
            <div>
              <span className="text-slate-400">Triangles:</span>{' '}
              <span className="text-cyan-300">{modelMetrics.triangleCount.toLocaleString()}</span>
            </div>
            <div className="w-[1px] h-3.5 bg-slate-800" />
            <div>
              <span className="text-slate-400">Volume:</span>{' '}
              <span className="text-cyan-300">{modelMetrics.volumeCm3} cm³</span>
            </div>
          </>
        )}
      </div>
    </div>
  );
};
