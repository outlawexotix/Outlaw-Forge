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
export declare function calculatePresetCameraView(preset: PresetViewType, bounds: BoundingBox3D, fov?: number, padding?: number): CameraViewConfig;
/**
 * Frames the active object in view ($F$ shortcut)
 */
export declare function frameObjectInCamera(camera: THREE.Camera, controls: {
    target: THREE.Vector3;
    update: () => void;
}, bounds: BoundingBox3D, fov?: number): void;
//# sourceMappingURL=cameraManager.d.ts.map