'use client';

import React, { useEffect, useState, useMemo, useRef, useCallback } from 'react';
import * as THREE from 'three';
import { TransformControls } from '@react-three/drei';
import { WorkingModel, PrinterProfile } from '@shared/types/api';
import {
  parseMeshBuffer,
  loadMeshFromUrl,
  centerGeometryOnBed,
  computeExactAABB,
  computeMeshMetrics,
  createOverhangInspectionMaterial,
  BoundingBox3D,
  MeshMetrics,
} from '@three-tools';

export type CADTool = 'select' | 'move' | 'rotate' | 'scale' | 'slice' | 'inspect';

export interface ModelTransformEvent {
  position: [number, number, number];
  rotation: [number, number, number]; // degrees [rx, ry, rz]
  scale: [number, number, number];
}

export interface ModelRendererProps {
  /**
   * Working model metadata from project state
   */
  model?: WorkingModel | null;

  /**
   * Raw array buffer data from client drag-and-drop or local file pick
   */
  modelBuffer?: ArrayBuffer | null;

  /**
   * File URL (e.g. /models/{model_id}/file or blob: or remote API)
   */
  modelUrl?: string | null;

  /**
   * Active 3D printer profile defining dimensions
   */
  printer: PrinterProfile;

  /**
   * Active CAD Tool mode (move, rotate, scale, inspect, select, etc.)
   */
  activeTool?: CADTool;

  /**
   * Toggle bounding box wireframe
   */
  showBoundingBox?: boolean;

  /**
   * Toggle mesh wireframe overlay / material
   */
  showWireframe?: boolean;

  /**
   * Base color of the rendered mesh material
   */
  color?: string;

  /**
   * Selected state for CAD highlight
   */
  isSelected?: boolean;

  /**
   * Callback fired when geometry is parsed, centered, and analyzed
   */
  onModelLoaded?: (geometry: THREE.BufferGeometry, metrics: MeshMetrics) => void;

  /**
   * Callback fired on live transform changes from TransformControls
   */
  onTransformChange?: (transform: ModelTransformEvent) => void;

  /**
   * Callback fired when user begins or ends dragging the transform gizmo
   */
  onGizmoDragging?: (isDragging: boolean) => void;

  /**
   * Callback fired on loading / parsing failure
   */
  onError?: (error: string) => void;
}

/**
 * Creates a precision procedural CAD specimen (Calibration Block with Chamfers & Pillars)
 * for immediate visual feedback when no custom 3D file is uploaded.
 */
function createDefaultSampleGeometry(): THREE.BufferGeometry {
  const geometries: THREE.BufferGeometry[] = [];

  // 1. Base Plate: 60 x 50 x 12 mm
  const base = new THREE.BoxGeometry(60, 50, 12);
  base.translate(0, 0, 6);
  geometries.push(base);

  // 2. Center Stepped Boss: 36 x 30 x 18 mm
  const mid = new THREE.BoxGeometry(36, 30, 18);
  mid.translate(0, 0, 12 + 9);
  geometries.push(mid);

  // 3. Top Cylindrical Boss: Radius 12 mm, Height 15 mm
  const cyl = new THREE.CylinderGeometry(12, 12, 15, 32);
  cyl.rotateX(Math.PI / 2);
  cyl.translate(0, 0, 30 + 7.5);
  geometries.push(cyl);

  // Merge geometries
  let totalVerts = 0;
  for (const g of geometries) {
    const pos = g.getAttribute('position');
    if (pos) totalVerts += pos.count;
  }

  const mergedPos = new Float32Array(totalVerts * 3);
  let offset = 0;
  for (const g of geometries) {
    const pos = g.getAttribute('position');
    if (pos) {
      const arr = pos.array as Float32Array;
      mergedPos.set(arr, offset);
      offset += arr.length;
    }
  }

  const merged = new THREE.BufferGeometry();
  merged.setAttribute('position', new THREE.BufferAttribute(mergedPos, 3));
  merged.computeVertexNormals();
  merged.computeBoundingBox();
  return merged;
}

export const ModelRenderer: React.FC<ModelRendererProps> = ({
  model,
  modelBuffer,
  modelUrl,
  printer,
  activeTool = 'select',
  showBoundingBox = true,
  showWireframe = false,
  color = '#38bdf8',
  isSelected = true,
  onModelLoaded,
  onTransformChange,
  onGizmoDragging,
  onError,
}) => {
  const [geometry, setGeometry] = useState<THREE.BufferGeometry | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [computedBounds, setComputedBounds] = useState<BoundingBox3D | null>(null);

  const modelGroupRef = useRef<THREE.Group>(null);
  const meshRef = useRef<THREE.Mesh>(null);
  const transformControlsRef = useRef<any>(null);

  const bedWidth = printer.build_width_mm || 220;
  const bedDepth = printer.build_depth_mm || 220;

  // Track active load request to prevent race conditions
  const abortControllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    let isCancelled = false;

    async function loadMesh() {
      setLoading(true);
      setLoadError(null);

      try {
        let loadedGeom: THREE.BufferGeometry | null = null;
        const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

        if (modelBuffer && modelBuffer.byteLength > 0) {
          const filename = model?.filename || 'model.stl';
          loadedGeom = await parseMeshBuffer(modelBuffer, filename);
        } else if (modelUrl) {
          abortControllerRef.current?.abort();
          const controller = new AbortController();
          abortControllerRef.current = controller;
          const filename = model?.filename || 'model.stl';
          const fullUrl = modelUrl.startsWith('http') ? modelUrl : `${apiBaseUrl.replace(/\/$/, '')}${modelUrl.startsWith('/') ? '' : '/'}${modelUrl}`;
          loadedGeom = await loadMeshFromUrl(fullUrl, filename, controller.signal);
        } else if (model?.id) {
          // Attempt to load from standard API model endpoint with cache-busting timestamp
          const versionTag = model?.updated_at ? encodeURIComponent(model.updated_at) : Date.now().toString();
          const apiUrl = `${apiBaseUrl.replace(/\/$/, '')}/models/${model.id}/file?v=${versionTag}`;
          const controller = new AbortController();
          abortControllerRef.current = controller;
          try {
            loadedGeom = await loadMeshFromUrl(apiUrl, model.filename, controller.signal);
          } catch {
            // Fall back to sample procedural model if remote file not on disk yet
            loadedGeom = createDefaultSampleGeometry();
            if (model?.transform?.uniform_scale_percent && model.transform.uniform_scale_percent !== 100) {
              const s = model.transform.uniform_scale_percent / 100;
              loadedGeom.scale(s, s, s);
            }
          }
        } else {
          // Default procedural CAD block
          loadedGeom = createDefaultSampleGeometry();
          if (model?.transform?.uniform_scale_percent && model.transform.uniform_scale_percent !== 100) {
            const s = model.transform.uniform_scale_percent / 100;
            loadedGeom.scale(s, s, s);
          }
        }

        if (isCancelled || !loadedGeom) return;

        // Clone and deterministically center geometry locally (XY at 0,0 and Z_min=0)
        const centeredGeom = loadedGeom.clone();
        const { bounds } = centerGeometryOnBed(centeredGeom, bedWidth, bedDepth, true);

        // Compute full engineering metrics
        const metrics = computeMeshMetrics(centeredGeom);

        setGeometry(centeredGeom);
        setComputedBounds(bounds);
        setLoading(false);

        if (onModelLoaded) {
          onModelLoaded(centeredGeom, metrics);
        }
      } catch (err: unknown) {
        if (isCancelled) return;
        const msg = err instanceof Error ? err.message : 'Failed to parse 3D mesh';
        console.warn('Mesh load exception, falling back to default sample model:', msg);
        
        // Fallback to sample model on parse error so viewport never goes blank
        const sampleGeom = createDefaultSampleGeometry();
        const { bounds } = centerGeometryOnBed(sampleGeom, bedWidth, bedDepth, true);
        const metrics = computeMeshMetrics(sampleGeom);
        setGeometry(sampleGeom);
        setComputedBounds(bounds);
        setLoading(false);
        if (onModelLoaded) onModelLoaded(sampleGeom, metrics);
      }
    }

    loadMesh();

    return () => {
      isCancelled = true;
      abortControllerRef.current?.abort();
    };
  }, [model?.id, model?.updated_at, model?.filename, model?.transform?.uniform_scale_percent, modelBuffer, modelUrl, bedWidth, bedDepth, onModelLoaded, onError]);

  // Overhang Inspection Material (Amber/Red highlight for downward faces > 45 deg)
  const overhangMaterial = useMemo(() => {
    return createOverhangInspectionMaterial({
      thresholdDeg: 45.0,
      wireframe: showWireframe,
    });
  }, [showWireframe]);

  // Model Transform state to prevent snapping back on re-renders
  const [modelTransform, setModelTransform] = useState<{
    position: [number, number, number];
    rotation: [number, number, number];
    scale: [number, number, number];
  }>({
    position: [
      model?.transform?.position_mm?.[0] ?? 0,
      model?.transform?.position_mm?.[1] ?? 0,
      model?.transform?.position_mm?.[2] ?? 0,
    ],
    rotation: [0, 0, 0],
    scale: [1, 1, 1],
  });

  const lastModelIdRef = useRef<string | null>(null);

  // Initialize or re-center only when model ID genuinely changes
  useEffect(() => {
    const currentId = model?.id || 'sample';
    if (lastModelIdRef.current !== currentId) {
      lastModelIdRef.current = currentId;
      const initialPos: [number, number, number] = [
        model?.transform?.position_mm?.[0] ?? 0,
        model?.transform?.position_mm?.[1] ?? 0,
        model?.transform?.position_mm?.[2] ?? 0,
      ];
      const initialRot: [number, number, number] = [
        model?.transform?.rotation_deg?.[0] ? (model.transform.rotation_deg[0] * Math.PI) / 180 : 0,
        model?.transform?.rotation_deg?.[1] ? (model.transform.rotation_deg[1] * Math.PI) / 180 : 0,
        model?.transform?.rotation_deg?.[2] ? (model.transform.rotation_deg[2] * Math.PI) / 180 : 0,
      ];
      const initialScl: [number, number, number] = [
        model?.transform?.scale_factors?.[0] ?? 1,
        model?.transform?.scale_factors?.[1] ?? 1,
        model?.transform?.scale_factors?.[2] ?? 1,
      ];
      setModelTransform({ position: initialPos, rotation: initialRot, scale: initialScl });
      if (modelGroupRef.current) {
        modelGroupRef.current.position.set(...initialPos);
        modelGroupRef.current.rotation.set(...initialRot);
        modelGroupRef.current.scale.set(...initialScl);
      }
    }
  }, [model?.id, model?.transform?.position_mm, model?.transform?.rotation_deg, model?.transform?.scale_factors, bedWidth, bedDepth]);

  // Live transform event handling while user drags gizmo
  const handleTransformChange = useCallback(() => {
    if (!modelGroupRef.current) return;
    const group = modelGroupRef.current;

    const pos = group.position;
    const rot = group.rotation;
    const scl = group.scale;

    if (onTransformChange) {
      onTransformChange({
        position: [
          Math.round(pos.x * 100) / 100,
          Math.round(pos.y * 100) / 100,
          Math.round(pos.z * 100) / 100,
        ],
        rotation: [
          Math.round(((rot.x * 180) / Math.PI) * 10) / 10,
          Math.round(((rot.y * 180) / Math.PI) * 10) / 10,
          Math.round(((rot.z * 180) / Math.PI) * 10) / 10,
        ],
        scale: [
          Math.round(scl.x * 1000) / 1000,
          Math.round(scl.y * 1000) / 1000,
          Math.round(scl.z * 1000) / 1000,
        ],
      });
    }
  }, [onTransformChange]);

  // When user finishes manipulating the transform gizmo, persist final transform to React state
  const handleGizmoRelease = useCallback(() => {
    onGizmoDragging?.(false);
    if (!modelGroupRef.current) return;
    const group = modelGroupRef.current;
    setModelTransform({
      position: [group.position.x, group.position.y, group.position.z],
      rotation: [group.rotation.x, group.rotation.y, group.rotation.z],
      scale: [group.scale.x, group.scale.y, group.scale.z],
    });
  }, [onGizmoDragging]);

  // Determine Drei TransformControls mode
  const transformMode = useMemo(() => {
    if (activeTool === 'move') return 'translate';
    if (activeTool === 'rotate') return 'rotate';
    if (activeTool === 'scale') return 'scale';
    return null;
  }, [activeTool]);

  // Bounding box wireframe helper
  const boundingBoxLines = useMemo(() => {
    if (!computedBounds) return null;
    const { min, max } = computedBounds;

    const points: THREE.Vector3[] = [
      // Bottom face
      new THREE.Vector3(min.x, min.y, min.z),
      new THREE.Vector3(max.x, min.y, min.z),
      new THREE.Vector3(max.x, min.y, min.z),
      new THREE.Vector3(max.x, max.y, min.z),
      new THREE.Vector3(max.x, max.y, min.z),
      new THREE.Vector3(min.x, max.y, min.z),
      new THREE.Vector3(min.x, max.y, min.z),
      new THREE.Vector3(min.x, min.y, min.z),

      // Top face
      new THREE.Vector3(min.x, min.y, max.z),
      new THREE.Vector3(max.x, min.y, max.z),
      new THREE.Vector3(max.x, min.y, max.z),
      new THREE.Vector3(max.x, max.y, max.z),
      new THREE.Vector3(max.x, max.y, max.z),
      new THREE.Vector3(min.x, max.y, max.z),
      new THREE.Vector3(min.x, max.y, max.z),
      new THREE.Vector3(min.x, min.y, max.z),

      // Vertical pillars
      new THREE.Vector3(min.x, min.y, min.z),
      new THREE.Vector3(min.x, min.y, max.z),
      new THREE.Vector3(max.x, min.y, min.z),
      new THREE.Vector3(max.x, min.y, max.z),
      new THREE.Vector3(max.x, max.y, min.z),
      new THREE.Vector3(max.x, max.y, max.z),
      new THREE.Vector3(min.x, max.y, min.z),
      new THREE.Vector3(min.x, max.y, max.z),
    ];

    return new THREE.BufferGeometry().setFromPoints(points);
  }, [computedBounds]);

  if (!geometry) {
    return null;
  }

  return (
    <>
      {/* 3D Model Group Container */}
      <group
        ref={modelGroupRef}
        position={modelTransform.position}
        rotation={modelTransform.rotation}
        scale={modelTransform.scale}
        name="ActiveModelNode"
      >
        {/* 1. Primary Solid Model Mesh */}
        {activeTool === 'inspect' ? (
          <mesh
            ref={meshRef}
            geometry={geometry}
            castShadow
            receiveShadow
            material={overhangMaterial}
          />
        ) : (
          <mesh
            ref={meshRef}
            geometry={geometry}
            castShadow
            receiveShadow
          >
            <meshStandardMaterial
              color={color}
              roughness={0.25}
              metalness={0.1}
              wireframe={showWireframe}
            />
          </mesh>
        )}

        {/* 2. Bounding Box Wireframe with Millimeter Precision Dimensions */}
        {showBoundingBox && boundingBoxLines && (
          <group name="ModelBoundingBox">
            <lineSegments geometry={boundingBoxLines}>
              <lineBasicMaterial color="#38bdf8" linewidth={1.5} transparent opacity={0.6} />
            </lineSegments>

            {/* Corner Marker Anchors */}
            {computedBounds && (
              <>
                <mesh position={[computedBounds.min.x, computedBounds.min.y, computedBounds.min.z]}>
                  <sphereGeometry args={[1.5, 8, 8]} />
                  <meshBasicMaterial color="#38bdf8" />
                </mesh>
                <mesh position={[computedBounds.max.x, computedBounds.max.y, computedBounds.max.z]}>
                  <sphereGeometry args={[1.5, 8, 8]} />
                  <meshBasicMaterial color="#38bdf8" />
                </mesh>
              </>
            )}
          </group>
        )}
      </group>

      {/* 3. Drei TransformControls Manipulator */}
      {transformMode && modelGroupRef.current && (
        <TransformControls
          ref={transformControlsRef}
          object={modelGroupRef.current}
          mode={transformMode}
          size={0.75}
          space="local"
          onChange={handleTransformChange}
          onMouseDown={() => onGizmoDragging?.(true)}
          onMouseUp={handleGizmoRelease}
        />
      )}
    </>
  );
};
