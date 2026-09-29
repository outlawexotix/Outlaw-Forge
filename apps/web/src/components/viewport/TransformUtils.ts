import * as THREE from 'three';
import { Vector3D, BoundingBox3D } from '@shared/types/viewport';

/**
 * Deterministic Transformation Matrix: Slicer Space (Z-up) -> Three.js Space (Y-up)
 * Applies a -90 deg (-PI/2 rad) rotation around the X-axis.
 * [ x_three ]   [ 1   0   0   0 ] [ x_slicer ]
 * [ y_three ] = [ 0   0   1   0 ] [ y_slicer ]
 * [ z_three ]   [ 0  -1   0   0 ] [ z_slicer ]
 * [    1    ]   [ 0   0   0   1 ] [    1     ]
 */
export const MAT_SLICER_TO_THREE = new THREE.Matrix4().set(
  1,  0,  0,  0,
  0,  0,  1,  0,
  0, -1,  0,  0,
  0,  0,  0,  1
);

/**
 * Deterministic Inverse Transformation Matrix: Three.js Space (Y-up) -> Slicer Space (Z-up)
 * Applies a +90 deg (+PI/2 rad) rotation around the X-axis.
 */
export const MAT_THREE_TO_SLICER = new THREE.Matrix4().set(
  1,  0,  0,  0,
  0,  0, -1,  0,
  0,  1,  0,  0,
  0,  0,  0,  1
);

/**
 * Converts a point from Slicer Space (Z-up) to Three.js Space (Y-up).
 */
export function slicerToThreeVector(slicerPoint: Vector3D): THREE.Vector3 {
  return new THREE.Vector3(slicerPoint.x, slicerPoint.z, -slicerPoint.y);
}

/**
 * Converts a point from Three.js Space (Y-up) to Slicer Space (Z-up).
 */
export function threeToSlicerVector(threePoint: THREE.Vector3): Vector3D {
  return {
    x: threePoint.x,
    y: -threePoint.z,
    z: threePoint.y,
  };
}

/**
 * Calculates the exact Axis-Aligned Bounding Box (AABB) in Slicer Space from a Three.js BufferGeometry.
 */
export function computeSlicerAABB(geometry: THREE.BufferGeometry): BoundingBox3D {
  geometry.computeBoundingBox();
  const box = geometry.boundingBox || new THREE.Box3();

  // In slicer space coordinates:
  const min: Vector3D = { x: box.min.x, y: box.min.y, z: box.min.z };
  const max: Vector3D = { x: box.max.x, y: box.max.y, z: box.max.z };

  const dimensions: Vector3D = {
    x: Math.abs(max.x - min.x),
    y: Math.abs(max.y - min.y),
    z: Math.abs(max.z - min.z),
  };

  const center: Vector3D = {
    x: (min.x + max.x) / 2,
    y: (min.y + max.y) / 2,
    z: (min.z + max.z) / 2,
  };

  return { min, max, center, dimensions };
}

/**
 * Computes the signed volume of a triangular mesh in cm^3 (assuming vertex units are mm).
 * 1 mm^3 = 10^-3 cm^3 = 0.001 cm^3
 */
export function computeMeshVolumeCm3(geometry: THREE.BufferGeometry): number {
  const positionAttr = geometry.getAttribute('position');
  if (!positionAttr) return 0;

  const index = geometry.getIndex();
  let totalSignedVolumeMm3 = 0;

  const p1 = new THREE.Vector3();
  const p2 = new THREE.Vector3();
  const p3 = new THREE.Vector3();

  const getTriangleVolume = (v1: THREE.Vector3, v2: THREE.Vector3, v3: THREE.Vector3): number => {
    return v1.dot(p2.crossVectors(v2, v3)) / 6.0;
  };

  if (index) {
    for (let i = 0; i < index.count; i += 3) {
      p1.fromBufferAttribute(positionAttr, index.getX(i));
      p2.fromBufferAttribute(positionAttr, index.getX(i + 1));
      p3.fromBufferAttribute(positionAttr, index.getX(i + 2));
      totalSignedVolumeMm3 += getTriangleVolume(p1, p2, p3);
    }
  } else {
    for (let i = 0; i < positionAttr.count; i += 3) {
      p1.fromBufferAttribute(positionAttr, i);
      p2.fromBufferAttribute(positionAttr, i + 1);
      p3.fromBufferAttribute(positionAttr, i + 2);
      totalSignedVolumeMm3 += getTriangleVolume(p1, p2, p3);
    }
  }

  // Convert mm^3 to cm^3
  return Math.abs(totalSignedVolumeMm3) * 0.001;
}
