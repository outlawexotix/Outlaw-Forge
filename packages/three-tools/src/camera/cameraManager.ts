import * as THREE from 'three';
import { BoundingBox3D } from '../transforms/coordinateTransforms';

export type PresetViewType = 'isometric' | 'top' | 'bottom' | 'front' | 'back' | 'left' | 'right';

export interface CameraViewConfig {
  position: THREE.Vector3;
  target: THREE.Vector3;
}

/**
 * Calculates camera position and target for standard CAD preset views.
 * Space: Three.js coordinates (Y-up), viewing the build volume / geometry.
 */
export function calculatePresetCameraView(
  preset: PresetViewType,
  bounds: BoundingBox3D,
  fov: number = 45,
  padding: number = 1.6
): CameraViewConfig {
  // Slicer to Three.js mapping of center: (x, z, -y)
  const target = new THREE.Vector3(
    bounds.center.x,
    bounds.center.z,
    -bounds.center.y
  );

  const maxDimension = Math.max(
    bounds.dimensions.x,
    bounds.dimensions.y,
    bounds.dimensions.z,
    50
  );

  // Distance required to fit object in vertical FOV
  const fovRad = (fov * Math.PI) / 180;
  const distance = (maxDimension / 2 / Math.tan(fovRad / 2)) * padding;

  const position = new THREE.Vector3();

  switch (preset) {
    case 'top':
      position.set(target.x, target.y + distance, target.z + 0.001);
      break;

    case 'bottom':
      position.set(target.x, target.y - distance, target.z + 0.001);
      break;

    case 'front':
      position.set(target.x, target.y, target.z + distance);
      break;

    case 'back':
      position.set(target.x, target.y, target.z - distance);
      break;

    case 'right':
      position.set(target.x + distance, target.y, target.z);
      break;

    case 'left':
      position.set(target.x - distance, target.y, target.z);
      break;

    case 'isometric':
    default: {
      const isoDist = distance * 0.707;
      position.set(
        target.x + isoDist,
        target.y + isoDist * 0.9,
        target.z + isoDist
      );
      break;
    }
  }

  return { position, target };
}

/**
 * Frames the active object in view ($F$ shortcut)
 */
export function frameObjectInCamera(
  camera: THREE.Camera,
  controls: { target: THREE.Vector3; update: () => void },
  bounds: BoundingBox3D,
  fov: number = 45
): void {
  const config = calculatePresetCameraView('isometric', bounds, fov, 1.4);
  camera.position.copy(config.position);
  controls.target.copy(config.target);
  controls.update();
}
