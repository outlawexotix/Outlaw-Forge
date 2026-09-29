import { PrinterProfile, WorkingModel } from './api';

export type CameraProjection = 'perspective' | 'orthographic';

export type PresetView = 'isometric' | 'top' | 'bottom' | 'front' | 'back' | 'left' | 'right';

export interface Vector3D {
  x: number;
  y: number;
  z: number;
}

export interface BoundingBox3D {
  min: Vector3D;
  max: Vector3D;
  center: Vector3D;
  dimensions: Vector3D; // mm [width (X), depth (Y), height (Z)]
}

export interface MeshTransform {
  position: Vector3D; // mm in Slicer space
  rotation: Vector3D; // Euler angles in radians or degrees
  scale: Vector3D;    // Uniform or non-uniform scaling factor (1.0 = 100%)
}

export interface ViewportMeshNode {
  id: string;
  name: string;
  visible: boolean;
  selected: boolean;
  transform: MeshTransform;
  metadata?: WorkingModel;
  bounds?: BoundingBox3D;
  color?: string;
  wireframe?: boolean;
  opacity?: number;
}

export interface ViewportSettings {
  showGrid: boolean;
  showEnvelope: boolean;
  showOrigin: boolean;
  showBoundingBoxes: boolean;
  showWireframe: boolean;
  cameraProjection: CameraProjection;
  backgroundColor: string;
  gridMajorStepMm: number;
  gridMinorStepMm: number;
}

export interface ViewportState {
  activePrinter: PrinterProfile;
  meshes: ViewportMeshNode[];
  selectedMeshId: string | null;
  settings: ViewportSettings;
  activePresetView: PresetView;
}
