import * as THREE from 'three';

/**
 * Calculates the exact rotation quaternion and Euler angles needed to orient
 * a planar facet with normal `faceNormal` so that it lies flat against the build plate (normal pointing to [0, 0, -1] in Slicer space).
 */
export function calculateRotationToBed(faceNormal: THREE.Vector3): {
  quaternion: THREE.Quaternion;
  eulerDeg: [number, number, number];
} {
  const norm = faceNormal.clone().normalize();
  const targetNormal = new THREE.Vector3(0, 0, -1); // Downward toward the bed in Slicer space

  // If normal is already pointing straight down, no rotation needed
  if (norm.distanceTo(targetNormal) < 1e-4) {
    return {
      quaternion: new THREE.Quaternion(),
      eulerDeg: [0, 0, 0],
    };
  }

  // If normal is pointing straight up, 180 deg flip around X
  if (norm.distanceTo(new THREE.Vector3(0, 0, 1)) < 1e-4) {
    const q = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(1, 0, 0), Math.PI);
    return {
      quaternion: q,
      eulerDeg: [180, 0, 0],
    };
  }

  // Compute rotation quaternion aligning face normal to target normal
  const quaternion = new THREE.Quaternion().setFromUnitVectors(norm, targetNormal);
  const euler = new THREE.Euler().setFromQuaternion(quaternion, 'XYZ');

  const eulerDeg: [number, number, number] = [
    Math.round(((euler.x * 180) / Math.PI) * 100) / 100,
    Math.round(((euler.y * 180) / Math.PI) * 100) / 100,
    Math.round(((euler.z * 180) / Math.PI) * 100) / 100,
  ];

  return { quaternion, eulerDeg };
}

/**
 * Extracts the 3 vertices and normal vector of a triangle from a BufferGeometry given its face index.
 */
export function getTriangleFromFaceIndex(
  geometry: THREE.BufferGeometry,
  faceIndex: number
): { vA: THREE.Vector3; vB: THREE.Vector3; vC: THREE.Vector3; normal: THREE.Vector3 } | null {
  const pos = geometry.getAttribute('position');
  const index = geometry.getIndex();
  if (!pos) return null;

  let i0: number, i1: number, i2: number;
  if (index) {
    i0 = index.getX(faceIndex * 3);
    i1 = index.getX(faceIndex * 3 + 1);
    i2 = index.getX(faceIndex * 3 + 2);
  } else {
    i0 = faceIndex * 3;
    i1 = faceIndex * 3 + 1;
    i2 = faceIndex * 3 + 2;
  }

  const vA = new THREE.Vector3(pos.getX(i0), pos.getY(i0), pos.getZ(i0));
  const vB = new THREE.Vector3(pos.getX(i1), pos.getY(i1), pos.getZ(i1));
  const vC = new THREE.Vector3(pos.getX(i2), pos.getY(i2), pos.getZ(i2));

  // Compute face normal (vB - vA) x (vC - vA)
  const edge1 = new THREE.Vector3().subVectors(vB, vA);
  const edge2 = new THREE.Vector3().subVectors(vC, vA);
  const normal = new THREE.Vector3().crossVectors(edge1, edge2).normalize();

  return { vA, vB, vC, normal };
}
