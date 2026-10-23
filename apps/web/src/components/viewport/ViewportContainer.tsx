'use client';

import React, { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, PerspectiveCamera, OrthographicCamera } from '@react-three/drei';
import type { OrbitControls as OrbitControlsImpl } from 'three-stdlib';
import * as THREE from 'three';
import { BuildPlate } from './BuildPlate';
import { AxisTriad } from './AxisTriad';
import { SceneLights } from './SceneLights';
import { OrientationGizmo } from './OrientationGizmo';
import { ToolpathRenderer, ParsedGCodeData } from './ToolpathRenderer';
import { ToolpathController } from './ToolpathController';
import { ModelRenderer, RenderMode, CADTool } from './ModelRenderer';
import { ModelContextAction, ModelContextMenu } from './ModelContextMenu';
import { CuttingPlane } from './CuttingPlane';
import { PrinterProfile, WorkingModel } from '@shared/types/api';
import { PresetView, ViewportSettings } from '@shared/types/viewport';
import {
  BoundingBox3D,
  MeshMetrics,
  calculatePresetCameraView,
  PlateTextureType,
  threeToSlicerVector,
} from '@three-tools';
import {
  Box,
  Eye,
  Grid,
  Layers,
  RotateCcw,
  Maximize2,
  AlertCircle,
  Loader2,
  Crosshair,
  Sparkles,
  Slice,
  ShieldAlert,
  Paintbrush,
  Sliders,
  Upload,
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

function getTransformedBounds(bounds: BoundingBox3D, modelToFrame?: WorkingModel): BoundingBox3D {
  const position = modelToFrame?.transform?.position_mm || [0, 0, 0];
  const rotation = (modelToFrame?.transform?.rotation_deg || [0, 0, 0]).map((angle) => THREE.MathUtils.degToRad(angle));
  const scale = modelToFrame?.transform?.scale_factors || [1, 1, 1];
  const matrix = new THREE.Matrix4().compose(
    new THREE.Vector3(position[0], position[1], position[2]),
    new THREE.Quaternion().setFromEuler(new THREE.Euler(rotation[0], rotation[1], rotation[2], 'XYZ')),
    new THREE.Vector3(scale[0], scale[1], scale[2])
  );
  const box = new THREE.Box3();
  for (const x of [bounds.min.x, bounds.max.x]) {
    for (const y of [bounds.min.y, bounds.max.y]) {
      for (const z of [bounds.min.z, bounds.max.z]) box.expandByPoint(new THREE.Vector3(x, y, z).applyMatrix4(matrix));
    }
  }
  const size = box.getSize(new THREE.Vector3());
  const center = box.getCenter(new THREE.Vector3());
  return {
    min: { x: box.min.x, y: box.min.y, z: box.min.z },
    max: { x: box.max.x, y: box.max.y, z: box.max.z },
    center: { x: center.x, y: center.y, z: center.z },
    dimensions: { x: size.x, y: size.y, z: size.z },
  };
}

function fitOrthographicZoom(
  camera: THREE.OrthographicCamera,
  bounds: BoundingBox3D,
  position: THREE.Vector3,
  target: THREE.Vector3,
  padding: number
): void {
  const direction = target.clone().sub(position).normalize();
  const up = Math.abs(direction.dot(new THREE.Vector3(0, 1, 0))) > 0.98
    ? new THREE.Vector3(0, 0, -1)
    : new THREE.Vector3(0, 1, 0);
  const right = direction.clone().cross(up).normalize();
  const screenUp = right.clone().cross(direction).normalize();
  let minX = Infinity;
  let maxX = -Infinity;
  let minY = Infinity;
  let maxY = -Infinity;

  for (const x of [bounds.min.x, bounds.max.x]) {
    for (const y of [bounds.min.y, bounds.max.y]) {
      for (const z of [bounds.min.z, bounds.max.z]) {
        const corner = new THREE.Vector3(x, z, -y);
        const relative = corner.sub(target);
        const projectedX = relative.dot(right);
        const projectedY = relative.dot(screenUp);
        minX = Math.min(minX, projectedX);
        maxX = Math.max(maxX, projectedX);
        minY = Math.min(minY, projectedY);
        maxY = Math.max(maxY, projectedY);
      }
    }
  }

  const width = Math.max(maxX - minX, 1);
  const height = Math.max(maxY - minY, 1);
  const frustumWidth = camera.right - camera.left;
  const frustumHeight = camera.top - camera.bottom;
  camera.zoom = Math.min(frustumWidth / width, frustumHeight / height) / padding;
  camera.updateProjectionMatrix();
}

export interface ViewportContainerProps {
  projectId?: string;
  printer?: PrinterProfile;
  model?: WorkingModel | null;
  models?: WorkingModel[];
  activeModelId?: string | null;
  selectedModelIds?: string[];
  modelBuffer?: ArrayBuffer | null;
  modelUrl?: string | null;
  activeTool?: CADTool;
  slicePlaneOrigin?: [number, number, number];
  slicePlaneNormal?: [number, number, number];
  className?: string;
  onModelMetrics?: (metrics: MeshMetrics) => void;
  onCursorCoordinates?: (coords: { x: number; y: number; z: number }) => void;
  onTransformChange?: (transform: { position: [number, number, number]; rotation: [number, number, number]; scale: [number, number, number] }) => void;
  onDropFile?: (file: File) => void;
  onSelectModel?: (modelId: string, modifiers?: { shiftKey: boolean; ctrlKey: boolean; metaKey: boolean }) => void;
  onSelectAllModels?: () => void;
  onSetTool?: (tool: CADTool) => void;
  onDuplicateModel?: (modelId: string) => void | Promise<void>;
  onDeleteModel?: (modelId: string | string[]) => void | Promise<void>;
  onMirrorModel?: (modelId: string, axis: 'X' | 'Y' | 'Z') => void | Promise<void>;
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
          const point = threeToSlicerVector(e.point);
          onHover({
            x: Math.round(point.x * 10) / 10,
            y: Math.round(point.y * 10) / 10,
            z: Math.round(point.z * 10) / 10,
          });
        }
      }}
    >
      <planeGeometry args={[bedWidth * 1.5, bedDepth * 1.5]} />
      <meshBasicMaterial />
    </mesh>
  );
};

type CameraTransition = { position: THREE.Vector3; target: THREE.Vector3 };

type PersistedCameraState = {
  version: 1;
  projection: 'perspective' | 'orthographic';
  position: [number, number, number];
  target: [number, number, number];
  zoom: number;
};

const cameraStorageKey = (projectId: string) => `outlaw-forge:viewport-camera:v1:${projectId}`;
const appearanceStorageKey = (projectId: string) => `outlaw-forge:viewport-appearance:v1:${projectId}`;

const readModelAppearance = (projectId: string): { hiddenIds: Set<string>; colors: Record<string, string> } => {
  try {
    const raw = window.localStorage.getItem(appearanceStorageKey(projectId));
    if (!raw) return { hiddenIds: new Set(), colors: {} };
    const value = JSON.parse(raw) as { hiddenIds?: unknown; colors?: unknown };
    const hiddenIds = new Set(Array.isArray(value.hiddenIds)
      ? value.hiddenIds.filter((id): id is string => typeof id === 'string')
      : []);
    const colors: Record<string, string> = {};
    if (value.colors && typeof value.colors === 'object' && !Array.isArray(value.colors)) {
      for (const [id, color] of Object.entries(value.colors)) {
        if (typeof color === 'string' && /^#[\da-f]{6}$/i.test(color)) colors[id] = color;
      }
    }
    return { hiddenIds, colors };
  } catch {
    return { hiddenIds: new Set(), colors: {} };
  }
};

const isFiniteVector = (value: unknown): value is [number, number, number] =>
  Array.isArray(value) && value.length === 3 && value.every((component) => typeof component === 'number' && Number.isFinite(component));

const readCameraState = (projectId: string): PersistedCameraState | null => {
  try {
    const raw = window.localStorage.getItem(cameraStorageKey(projectId));
    if (!raw) return null;
    const value = JSON.parse(raw) as Partial<PersistedCameraState>;
    if (
      value.version !== 1 ||
      (value.projection !== 'perspective' && value.projection !== 'orthographic') ||
      !isFiniteVector(value.position) ||
      !isFiniteVector(value.target) ||
      typeof value.zoom !== 'number' || !Number.isFinite(value.zoom) || value.zoom <= 0
    ) return null;
    return value as PersistedCameraState;
  } catch {
    return null;
  }
};

const CameraStateRestorer: React.FC<{
  projectId: string;
  pendingStateRef: React.MutableRefObject<{ projectId: string; state: PersistedCameraState } | null>;
  restoredProjectIdRef: React.MutableRefObject<string | null>;
  controlsRef: React.MutableRefObject<OrbitControlsImpl | null>;
}> = ({ projectId, pendingStateRef, restoredProjectIdRef, controlsRef }) => {
  useFrame(() => {
    const pending = pendingStateRef.current;
    if (!pending || pending.projectId !== projectId) return;
    const controls = controlsRef.current;
    if (!controls) return;
    const camera = controls.object;
    if ((pending.state.projection === 'orthographic') !== (camera instanceof THREE.OrthographicCamera)) return;

    camera.position.fromArray(pending.state.position);
    if (camera instanceof THREE.OrthographicCamera) {
      camera.zoom = pending.state.zoom;
      camera.updateProjectionMatrix();
    }
    controls.target.fromArray(pending.state.target);
    controls.update();
    pendingStateRef.current = null;
    restoredProjectIdRef.current = projectId;
  });

  return null;
};

const CameraTransitionController: React.FC<{
  controlsRef: React.MutableRefObject<OrbitControlsImpl | null>;
  transitionRef: React.MutableRefObject<CameraTransition | null>;
}> = ({ controlsRef, transitionRef }) => {
  useFrame((_, delta) => {
    const transition = transitionRef.current;
    const controls = controlsRef.current;
    if (!transition || !controls) return;

    const blend = 1 - Math.exp(-8 * delta);
    controls.object.position.lerp(transition.position, blend);
    controls.target.lerp(transition.target, blend);
    controls.update();

    if (
      controls.object.position.distanceToSquared(transition.position) < 0.0001 &&
      controls.target.distanceToSquared(transition.target) < 0.0001
    ) {
      controls.object.position.copy(transition.position);
      controls.target.copy(transition.target);
      transitionRef.current = null;
      controls.update();
    }
  });

  return null;
};

export const ViewportContainer: React.FC<ViewportContainerProps> = ({
  projectId = '',
  printer = DEFAULT_PRINTER,
  model = null,
  models = [],
  activeModelId = null,
  selectedModelIds = [],
  modelBuffer = null,
  modelUrl = null,
  activeTool = 'select',
  slicePlaneOrigin,
  slicePlaneNormal,
  className = '',
  onModelMetrics,
  onCursorCoordinates,
  onTransformChange,
  onDropFile,
  onSelectModel,
  onSelectAllModels,
  onSetTool,
  onDuplicateModel,
  onDeleteModel,
  onMirrorModel,
}) => {
  const [settings, setSettings] = useState<ViewportSettings>(DEFAULT_SETTINGS);
  const [activeView, setActiveView] = useState<PresetView>('isometric');
  const [plateType, setPlateType] = useState<PlateTextureType>('textured_pei');
  const [renderMode, setRenderMode] = useState<RenderMode>('solid');
  const [layerHeightMm, setLayerHeightMm] = useState<number>(0.20);
  const [showExclusionZone, setShowExclusionZone] = useState<boolean>(true);
  const [modelMetrics, setModelMetrics] = useState<MeshMetrics | null>(null);
  const [metricsByModelId, setMetricsByModelId] = useState<Record<string, MeshMetrics>>({});
  const [hiddenModelIds, setHiddenModelIds] = useState<Set<string>>(() => new Set());
  const [modelColors, setModelColors] = useState<Record<string, string>>({});
  const [appearanceLoadedProjectId, setAppearanceLoadedProjectId] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isGizmoDragging, setIsGizmoDragging] = useState<boolean>(false);
  const [isDraggingFile, setIsDraggingFile] = useState<boolean>(false);
  const [gcodeText, setGcodeText] = useState<string | null>(null);
  const [parsedGCode, setParsedGCode] = useState<ParsedGCodeData | null>(null);
  const [toolpathLayer, setToolpathLayer] = useState<number>(0);
  const [showSingleLayer, setShowSingleLayer] = useState<boolean>(false);
  const [showTravelMoves, setShowTravelMoves] = useState<boolean>(true);
  const [showOuterWall, setShowOuterWall] = useState<boolean>(true);
  const [showInnerWall, setShowInnerWall] = useState<boolean>(true);
  const [showInfill, setShowInfill] = useState<boolean>(true);
  const [showSupport, setShowSupport] = useState<boolean>(true);
  const [showToolpaths, setShowToolpaths] = useState<boolean>(true);
  const [contextMenu, setContextMenu] = useState<{ modelId: string; x: number; y: number } | null>(null);

  const controlsRef = useRef<OrbitControlsImpl>(null);
  const pendingCameraStateRef = useRef<{ projectId: string; state: PersistedCameraState } | null>(null);
  const restoredCameraProjectRef = useRef<string | null>(null);
  const canvasContainerRef = useRef<HTMLDivElement>(null);
  const cameraTransitionRef = useRef<CameraTransition | null>(null);
  const rightPointerStartRef = useRef<{ x: number; y: number } | null>(null);
  const rightPointerDraggedRef = useRef(false);

  useEffect(() => {
    if (!projectId) {
      setHiddenModelIds(new Set());
      setModelColors({});
      setAppearanceLoadedProjectId(null);
      return;
    }
    const appearance = readModelAppearance(projectId);
    setHiddenModelIds(appearance.hiddenIds);
    setModelColors(appearance.colors);
    setAppearanceLoadedProjectId(projectId);
  }, [projectId]);

  useEffect(() => {
    if (!projectId || appearanceLoadedProjectId !== projectId) return;
    try {
      window.localStorage.setItem(appearanceStorageKey(projectId), JSON.stringify({
        hiddenIds: [...hiddenModelIds],
        colors: modelColors,
      }));
    } catch {
      // Object appearance remains usable for the current session when storage is unavailable.
    }
  }, [appearanceLoadedProjectId, hiddenModelIds, modelColors, projectId]);

  useEffect(() => {
    cameraTransitionRef.current = null;
    restoredCameraProjectRef.current = null;
    pendingCameraStateRef.current = null;
    if (!projectId) {
      setSettings((current) => ({ ...current, cameraProjection: DEFAULT_SETTINGS.cameraProjection }));
      return;
    }

    const saved = readCameraState(projectId);
    setSettings((current) => ({
      ...current,
      cameraProjection: saved?.projection ?? DEFAULT_SETTINGS.cameraProjection,
    }));
    if (saved) pendingCameraStateRef.current = { projectId, state: saved };
    else restoredCameraProjectRef.current = projectId;
  }, [projectId]);

  const persistCameraState = useCallback(() => {
    if (!projectId || restoredCameraProjectRef.current !== projectId) return;
    const controls = controlsRef.current;
    if (!controls) return;
    const camera = controls.object;
    const state: PersistedCameraState = {
      version: 1,
      projection: camera instanceof THREE.OrthographicCamera ? 'orthographic' : 'perspective',
      position: camera.position.toArray() as [number, number, number],
      target: controls.target.toArray() as [number, number, number],
      zoom: camera.zoom,
    };
    try {
      window.localStorage.setItem(cameraStorageKey(projectId), JSON.stringify(state));
    } catch {
      // Camera navigation remains available when browser storage is disabled or full.
    }
  }, [projectId]);

  const transitionCameraTo = useCallback((position: THREE.Vector3, target: THREE.Vector3) => {
    cameraTransitionRef.current = { position: position.clone(), target: target.clone() };
  }, []);

  useEffect(() => {
    if (!activeModelId || !onDeleteModel) return;

    const deleteSelectedModel = (event: KeyboardEvent) => {
      if (event.key !== 'Delete' || event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
      const target = event.target;
      if (target instanceof HTMLElement && (
        target.isContentEditable ||
        target.matches('input, textarea, select, [role="textbox"]')
      )) return;

      event.preventDefault();
      const idsToDelete = selectedModelIds.includes(activeModelId) && selectedModelIds.length > 1
        ? selectedModelIds
        : [activeModelId];
      void onDeleteModel(idsToDelete);
    };

    window.addEventListener('keydown', deleteSelectedModel);
    return () => window.removeEventListener('keydown', deleteSelectedModel);
  }, [activeModelId, onDeleteModel, selectedModelIds]);

  useEffect(() => {
    const handleSelectionHotkeys = (event: KeyboardEvent) => {
      const target = event.target;
      if (target instanceof HTMLElement && (
        target.isContentEditable ||
        target.matches('input, textarea, select, [role="textbox"]')
      )) return;

      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'a' && models.length > 0) {
        event.preventDefault();
        onSelectAllModels?.();
      } else if (event.key === 'Escape' && selectedModelIds.length > 1 && activeModelId) {
        onSelectModel?.(activeModelId);
      }
    };

    window.addEventListener('keydown', handleSelectionHotkeys);
    return () => window.removeEventListener('keydown', handleSelectionHotkeys);
  }, [models, selectedModelIds, activeModelId, onSelectAllModels, onSelectModel]);

  const openModelContextMenu = useCallback((modelId: string, clientX: number, clientY: number) => {
    if (rightPointerDraggedRef.current) return;
    const rect = canvasContainerRef.current?.getBoundingClientRect();
    if (!rect) return;
    // Keep the full action list inside the viewport even when the model is
    // close to the right or bottom edge of the canvas.
    const x = Math.max(8, Math.min(clientX - rect.left, rect.width - 240));
    const y = Math.max(8, Math.min(clientY - rect.top, rect.height - 470));
    setContextMenu({ modelId, x, y });
  }, []);

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

  const activeId = activeModelId || model?.id || null;
  const activeMetrics = activeId ? metricsByModelId[activeId] || null : modelMetrics;
  const contextModelHidden = contextMenu ? hiddenModelIds.has(contextMenu.modelId) : false;
  const contextModelColor = contextMenu ? modelColors[contextMenu.modelId] : undefined;

  const setModelHidden = useCallback((modelId: string) => {
    setHiddenModelIds((current) => {
      const next = new Set(current);
      if (next.has(modelId)) next.delete(modelId);
      else next.add(modelId);
      return next;
    });
  }, []);

  const setModelColor = useCallback((modelId: string, color: string | null) => {
    setModelColors((current) => {
      if (color === null) {
        if (!(modelId in current)) return current;
        const next = { ...current };
        delete next[modelId];
        return next;
      }
      if (!/^#[\da-f]{6}$/i.test(color)) return current;
      return { ...current, [modelId]: color };
    });
  }, []);

  const handleContextAction = useCallback((action: ModelContextAction) => {
    const selectedId = contextMenu?.modelId;
    if (!selectedId) return;
    setContextMenu(null);
    if (action === 'toggle_visibility') return setModelHidden(selectedId);
    if (action === 'duplicate') return void onDuplicateModel?.(selectedId);
    if (action === 'delete') return void onDeleteModel?.(selectedId);
    if (action.startsWith('mirror_')) {
      return void onMirrorModel?.(selectedId, action.slice(-1).toUpperCase() as 'X' | 'Y' | 'Z');
    }
    onSetTool?.(action as CADTool);
  }, [contextMenu, onDeleteModel, onDuplicateModel, onMirrorModel, onSetTool, setModelHidden]);

  // Drag and drop 3D file handler
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDraggingFile(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDraggingFile(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDraggingFile(false);

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const droppedFile = e.dataTransfer.files[0];
      const ext = droppedFile.name.split('.').pop()?.toLowerCase();
      if (['gcode', 'gco'].includes(ext || '')) {
        droppedFile.text().then(setGcodeText).catch(() => setErrorMessage('Could not read the G-code file.'));
      } else if (['stl', 'obj', 'glb', 'gltf', '3mf'].includes(ext || '')) {
        onDropFile?.(droppedFile);
      } else {
        setErrorMessage(`Unsupported file format '.${ext}'. Drop STL, OBJ, GLB, 3MF, or G-code files.`);
      }
    }
  };

  // Transition to standard CAD Preset View
  const handlePresetView = useCallback(
    (view: PresetView) => {
      setActiveView(view);
      if (!controlsRef.current) return;

      const boundsToFrame = activeMetrics?.boundingBox
        ? getTransformedBounds(activeMetrics.boundingBox, models.find((item) => item.id === activeId) || model || undefined)
        : defaultBounds;
      const { position, target } = calculatePresetCameraView(
        view,
        boundsToFrame,
        45,
        view === 'isometric' ? 1.6 : 1.4
      );

      const camera = controlsRef.current.object;
      if (camera instanceof THREE.OrthographicCamera) {
        fitOrthographicZoom(camera, boundsToFrame, position, target, view === 'isometric' ? 1.6 : 1.4);
      }

      transitionCameraTo(position, target);
    },
    [activeMetrics, activeId, models, model, defaultBounds, transitionCameraTo]
  );

  // Frame active model ($F$ shortcut)
  const handleFrameSelection = useCallback(() => {
    if (!controlsRef.current) return;
    const boundsToFrame = activeMetrics?.boundingBox
      ? getTransformedBounds(activeMetrics.boundingBox, models.find((item) => item.id === activeId) || model || undefined)
      : defaultBounds;
    const { position, target } = calculatePresetCameraView('isometric', boundsToFrame, 45, 1.3);

    transitionCameraTo(position, target);
  }, [activeMetrics, activeId, models, model, defaultBounds, transitionCameraTo]);

  const resetCamera = useCallback(() => {
    handlePresetView('isometric');
  }, [handlePresetView]);

  // Global CAD Hotkeys (F for Frame, R for Reset, 1-4 for Views)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
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

  const handleModelLoaded = (modelId: string | undefined, geom: THREE.BufferGeometry, metrics: MeshMetrics) => {
    if (!modelId || modelId === activeId) setModelMetrics(metrics);
    if (modelId) setMetricsByModelId((current) => ({ ...current, [modelId]: metrics }));
    setLoading(false);
    setErrorMessage(null);
    if ((!modelId || modelId === activeId) && onModelMetrics) {
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
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      onPointerDown={(event) => {
        if (event.button !== 2) return;
        rightPointerStartRef.current = { x: event.clientX, y: event.clientY };
        rightPointerDraggedRef.current = false;
      }}
      onPointerMove={(event) => {
        const start = rightPointerStartRef.current;
        if (!start || (event.buttons & 2) === 0) return;
        const dx = event.clientX - start.x;
        const dy = event.clientY - start.y;
        if (dx * dx + dy * dy > 16) rightPointerDraggedRef.current = true;
      }}
      onContextMenu={(event) => {
        event.preventDefault();
        rightPointerStartRef.current = null;
        rightPointerDraggedRef.current = false;
      }}
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
          mouseButtons={{
            RIGHT: THREE.MOUSE.ROTATE,
            MIDDLE: THREE.MOUSE.PAN,
          }}
          enableDamping
          dampingFactor={0.08}
          zoomToCursor
          onChange={persistCameraState}
          minDistance={5}
          maxDistance={3000}
          screenSpacePanning
          onStart={() => { cameraTransitionRef.current = null; }}
        />

        <CameraStateRestorer
          projectId={projectId}
          pendingStateRef={pendingCameraStateRef}
          restoredProjectIdRef={restoredCameraProjectRef}
          controlsRef={controlsRef}
        />
        <CameraTransitionController controlsRef={controlsRef} transitionRef={cameraTransitionRef} />

        <SceneLights />

        {/* Slicer Space Root Group: Rotation -90 deg (-PI/2) on X-axis maps Z-up to Three.js Y-up */}
        <group rotation={[-Math.PI / 2, 0, 0]} name="SlicerSpaceRoot">
          <AxisTriad size={32} visible={settings.showOrigin} />
          {/* OrcaSlicer Build Plate Surface & Procedural PEI Texture */}
          <BuildPlate
            printer={printer}
            plateType={plateType}
            showEnvelope={settings.showEnvelope}
            showOrigin={settings.showOrigin}
            showExclusionZone={showExclusionZone}
            majorStep={settings.gridMajorStepMm}
            minorStep={settings.gridMinorStepMm}
          />

          {/* Multi-Model / Single-Model Renderer */}
          {models && models.length > 1 ? (
            models.map((m) => {
              const isSelected = m.id === (activeModelId || model?.id);
              const isInSelection = selectedModelIds.includes(m.id) || isSelected;
              return (
                <ModelRenderer
                  key={m.id}
                  model={m}
                  printer={printer}
                  activeTool={isSelected ? activeTool : 'select'}
                  renderMode={isSelected ? renderMode : 'solid'}
                  layerHeightMm={layerHeightMm}
                  slicePlaneOrigin={slicePlaneOrigin}
                  slicePlaneNormal={slicePlaneNormal}
                  showBoundingBox={isInSelection ? settings.showBoundingBoxes : false}
                  showWireframe={isSelected ? settings.showWireframe : false}
                  isSelected={isSelected}
                  visible={!hiddenModelIds.has(m.id)}
                  color={modelColors[m.id] ?? (isSelected ? '#38bdf8' : isInSelection ? '#22d3ee' : '#64748b')}
                  onModelLoaded={(geom, metrics) => handleModelLoaded(m.id, geom, metrics)}
                  onTransformChange={isSelected ? onTransformChange : undefined}
                  onSelect={(modifiers) => onSelectModel?.(m.id, modifiers)}
                  onContextMenu={(x, y) => openModelContextMenu(m.id, x, y)}
                  onGizmoDragging={(dragging) => isSelected && setIsGizmoDragging(dragging)}
                  onError={handleModelError}
                />
              );
            })
          ) : (
            <ModelRenderer
              model={model}
              modelBuffer={modelBuffer}
              modelUrl={modelUrl}
              printer={printer}
              activeTool={activeTool}
              renderMode={renderMode}
              layerHeightMm={layerHeightMm}
              slicePlaneOrigin={slicePlaneOrigin}
              slicePlaneNormal={slicePlaneNormal}
              showBoundingBox={settings.showBoundingBoxes}
              showWireframe={settings.showWireframe}
              isSelected={true}
              visible={!model?.id || !hiddenModelIds.has(model.id)}
              color={model?.id ? modelColors[model.id] ?? '#38bdf8' : '#38bdf8'}
              onModelLoaded={(geom, metrics) => handleModelLoaded(model?.id, geom, metrics)}
              onTransformChange={onTransformChange}
              onSelect={(modifiers) => model?.id && onSelectModel?.(model.id, modifiers)}
              onContextMenu={(x, y) => model?.id && openModelContextMenu(model.id, x, y)}
              onGizmoDragging={(dragging) => setIsGizmoDragging(dragging)}
              onError={handleModelError}
            />
          )}

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

          {/* Interactive raycast ground plane */}
          {onCursorCoordinates && !isGizmoDragging && (
            <BedRaycaster
              bedWidth={bedWidth}
              bedDepth={bedDepth}
              onHover={onCursorCoordinates}
            />
          )}
          {gcodeText && (
            <ToolpathRenderer
              source={gcodeText}
              bedWidth={bedWidth}
              bedDepth={bedDepth}
              visible={showToolpaths}
              currentLayer={toolpathLayer}
              showSingleLayer={showSingleLayer}
              showTravel={showTravelMoves}
              showOuterWall={showOuterWall}
              showInnerWall={showInnerWall}
              showInfill={showInfill}
              showSupport={showSupport}
              onGCodeParsed={(data) => {
                setParsedGCode(data);
                setToolpathLayer(data.totalLayers - 1);
              }}
            />
          )}
        </group>

        {/* OrcaSlicer Orientation Gizmo / View Cube */}
        <OrientationGizmo
          alignment="top-right"
          margin={[70, 70]}
          onPresetView={handlePresetView}
        />
      </Canvas>

      {contextMenu && (
        <ModelContextMenu
          x={contextMenu.x}
          y={contextMenu.y}
          hidden={contextModelHidden}
          color={contextModelColor}
          onColorChange={(color) => {
            setModelColor(contextMenu.modelId, color);
            setContextMenu(null);
          }}
          onAction={handleContextAction}
          onClose={() => setContextMenu(null)}
        />
      )}

      {/* Interactive G-code Toolpath Simulation HUD */}
      {gcodeText && showToolpaths && parsedGCode && (
        <ToolpathController
          data={parsedGCode}
          currentLayer={toolpathLayer}
          onLayerChange={setToolpathLayer}
          showSingleLayer={showSingleLayer}
          onToggleSingleLayer={setShowSingleLayer}
          showTravel={showTravelMoves}
          onToggleTravel={setShowTravelMoves}
          showOuterWall={showOuterWall}
          onToggleOuterWall={setShowOuterWall}
          showInnerWall={showInnerWall}
          onToggleInnerWall={setShowInnerWall}
          showInfill={showInfill}
          onToggleInfill={setShowInfill}
          showSupport={showSupport}
          onToggleSupport={setShowSupport}
          onClose={() => {
            setGcodeText(null);
            setParsedGCode(null);
          }}
        />
      )}

      {/* Direct Drag-and-Drop Active Overlay */}
      {isDraggingFile && (
        <div className="absolute inset-0 bg-cyan-950/70 border-4 border-dashed border-cyan-400 backdrop-blur-sm flex flex-col items-center justify-center z-40 pointer-events-none animate-in fade-in duration-150">
          <Upload className="w-16 h-16 text-cyan-300 animate-bounce mb-3" />
          <div className="text-base font-mono font-bold text-white uppercase tracking-wider">
            Drop 3D CAD Mesh onto Build Plate
          </div>
          <div className="text-xs font-mono text-cyan-200 mt-1">
            Supports STL, OBJ, GLB, GLTF, G-code, and BG-code
          </div>
        </div>
      )}

      {/* Floating HUD: Preset View Controls & OrcaSlicer Toolbar (Top-Left) */}
      <div className="absolute top-3 left-4 flex flex-col gap-2 pointer-events-auto z-20">
        {/* Preset Views */}
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

        {/* View toggles & Orca Render Mode Switcher */}
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
            title="Toggle Bounding Box & 3D Dimension Tags"
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
          <button
            onClick={() => setShowExclusionZone((v) => !v)}
            className={`p-1.5 rounded transition ${
              showExclusionZone ? 'text-amber-400 bg-amber-950/60 border border-amber-500/30' : 'hover:text-white'
            }`}
            title="Toggle Nozzle Wipe Exclusion Zone"
          >
            <ShieldAlert className="w-3.5 h-3.5" />
          </button>

          <div className="w-[1px] h-4 bg-slate-800 mx-1" />

          {/* Render Mode Selectors */}
          <div className="flex items-center gap-1 font-mono text-[11px]">
            <button
              onClick={() => setRenderMode('solid')}
              className={`px-2 py-0.5 rounded transition ${
                renderMode === 'solid'
                  ? 'bg-slate-800 text-cyan-300 font-semibold border border-slate-700'
                  : 'hover:text-white text-slate-400'
              }`}
            >
              Solid
            </button>
            <button
              onClick={() => setRenderMode('layer_lines')}
              className={`px-2 py-0.5 rounded transition ${
                renderMode === 'layer_lines'
                  ? 'bg-slate-800 text-cyan-300 font-semibold border border-slate-700'
                  : 'hover:text-white text-slate-400'
              }`}
            >
              Layers
            </button>
            <button
              onClick={() => setRenderMode('overhangs')}
              className={`px-2 py-0.5 rounded transition ${
                renderMode === 'overhangs'
                  ? 'bg-amber-900/60 text-amber-300 font-semibold border border-amber-600/40'
                  : 'hover:text-white text-slate-400'
              }`}
            >
              Overhangs
            </button>
            {gcodeText && (
              <button
                onClick={() => setShowToolpaths((visible) => !visible)}
                className={`px-2 py-0.5 rounded transition ${showToolpaths ? 'bg-amber-900/60 text-amber-300 font-semibold border border-amber-600/40' : 'hover:text-white text-slate-400'}`}
                title="Toggle loaded G-code toolpaths"
              >
                G-code
              </button>
            )}
          </div>
        </div>

        {/* OrcaSlicer Plate Selector Bar */}
        <div className="flex items-center gap-1.5 p-1 bg-slate-950/85 backdrop-blur-md border border-slate-800/90 rounded-lg shadow-cad-panel text-[11px] font-mono text-slate-400 w-fit">
          <Paintbrush className="w-3.5 h-3.5 text-slate-400 ml-1" />
          <span className="text-slate-500 text-[10px]">Plate:</span>
          <button
            onClick={() => setPlateType('textured_pei')}
            className={`px-2 py-0.5 rounded transition ${
              plateType === 'textured_pei'
                ? 'bg-amber-500/20 text-amber-300 font-semibold border border-amber-500/40'
                : 'hover:text-slate-200'
            }`}
          >
            Gold PEI
          </button>
          <button
            onClick={() => setPlateType('smooth_pei')}
            className={`px-2 py-0.5 rounded transition ${
              plateType === 'smooth_pei'
                ? 'bg-slate-800 text-slate-200 font-semibold border border-slate-700'
                : 'hover:text-slate-200'
            }`}
          >
            Smooth PEI
          </button>
          <button
            onClick={() => setPlateType('cool_plate')}
            className={`px-2 py-0.5 rounded transition ${
              plateType === 'cool_plate'
                ? 'bg-cyan-950/60 text-cyan-300 font-semibold border border-cyan-600/40'
                : 'hover:text-slate-200'
            }`}
          >
            Cool Plate
          </button>
          <button
            onClick={() => setPlateType('engineering_plate')}
            className={`px-2 py-0.5 rounded transition ${
              plateType === 'engineering_plate'
                ? 'bg-slate-800 text-slate-300 font-semibold border border-slate-700'
                : 'hover:text-slate-200'
            }`}
          >
            Eng Plate
          </button>
        </div>
      </div>

      {hiddenModelIds.size > 0 && (
        <div className="absolute top-3 right-4 z-20 flex max-w-[min(420px,45%)] flex-wrap items-center justify-end gap-1.5 pointer-events-auto">
          {[...hiddenModelIds].map((hiddenId) => {
            const hiddenModel = models.find((item) => item.id === hiddenId);
            const label = hiddenModel?.filename || hiddenId.slice(0, 8);
            return (
              <button
                key={hiddenId}
                type="button"
                onClick={() => setModelHidden(hiddenId)}
                className="flex items-center gap-1.5 rounded border border-slate-700 bg-slate-950/90 px-2 py-1 text-[10px] font-mono text-slate-300 hover:border-cyan-500 hover:text-cyan-200"
                title={`Show ${label}`}
              >
                <Eye className="h-3 w-3" />
                Show {label}
              </button>
            );
          })}
        </div>
      )}

      {/* OrcaSlicer Lay on Face Active Instructions Banner */}
      {activeTool === 'lay_flat' && (
        <div className="absolute top-3 left-1/2 -translate-x-1/2 bg-cyan-950/90 border border-cyan-500/50 rounded-lg px-4 py-1.5 shadow-glow-cyan text-xs font-mono text-cyan-200 flex items-center gap-2 z-20 animate-pulse">
          <Sparkles className="w-3.5 h-3.5 text-cyan-400" />
          <span className="font-bold text-cyan-300">LAY ON FACE TOOL ACTIVE</span>
          <span className="text-[11px] text-cyan-400/80">| Click any flat surface on the model to snap flush to bed</span>
        </div>
      )}

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
