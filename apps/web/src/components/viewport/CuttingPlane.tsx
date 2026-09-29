'use client';

import React, { useMemo } from 'react';
import * as THREE from 'three';

export interface CuttingPlaneProps {
  visible?: boolean;
  planeOrigin?: [number, number, number];
  planeNormal?: [number, number, number];
  width?: number;
  depth?: number;
  color?: string;
  opacity?: number;
}

/**
 * Interactive 3D Cutting Plane visualization for planar slicing.
 * Rendered directly within SlicerSpaceRoot (Z-up coordinate space).
 */
export const CuttingPlane: React.FC<CuttingPlaneProps> = ({
  visible = true,
  planeOrigin = [0, 0, 25],
  planeNormal = [0, 0, 1],
  width = 250,
  depth = 250,
  color = '#06b6d4', // Cyan 500
  opacity = 0.35,
}) => {
  // Compute rotation matrix from default normal [0, 0, 1] to target plane normal
  const rotationEuler = useMemo(() => {
    const defaultNormal = new THREE.Vector3(0, 0, 1);
    const targetNormal = new THREE.Vector3(...planeNormal).normalize();
    const quaternion = new THREE.Quaternion().setFromUnitVectors(defaultNormal, targetNormal);
    return new THREE.Euler().setFromQuaternion(quaternion);
  }, [planeNormal]);

  // Perimeter border line object
  const borderLine = useMemo(() => {
    const w2 = (width * 1.2) / 2;
    const d2 = (depth * 1.2) / 2;
    const points = [
      new THREE.Vector3(-w2, -d2, 0),
      new THREE.Vector3(w2, -d2, 0),
      new THREE.Vector3(w2, d2, 0),
      new THREE.Vector3(-w2, d2, 0),
    ];
    const geometry = new THREE.BufferGeometry().setFromPoints(points);
    const material = new THREE.LineBasicMaterial({ color: 0x22d3ee, linewidth: 2 });
    return new THREE.LineLoop(geometry, material);
  }, [width, depth]);

  // Center crosshair lines object
  const crosshairLines = useMemo(() => {
    const w2 = (width * 1.2) / 2;
    const d2 = (depth * 1.2) / 2;
    const points = [
      new THREE.Vector3(-w2, 0, 0),
      new THREE.Vector3(w2, 0, 0),
      new THREE.Vector3(0, -d2, 0),
      new THREE.Vector3(0, d2, 0),
    ];
    const geometry = new THREE.BufferGeometry().setFromPoints(points);
    const material = new THREE.LineBasicMaterial({ color: 0x0891b2, transparent: true, opacity: 0.6 });
    return new THREE.LineSegments(geometry, material);
  }, [width, depth]);

  // Normal arrow indicator helper
  const arrowHelper = useMemo(() => {
    return new THREE.ArrowHelper(
      new THREE.Vector3(0, 0, 1),
      new THREE.Vector3(0, 0, 0),
      15,
      0x06b6d4,
      4,
      2.5
    );
  }, []);

  if (!visible) return null;

  return (
    <group position={planeOrigin} rotation={rotationEuler}>
      {/* Semi-transparent cut sheet */}
      <mesh receiveShadow={false} castShadow={false}>
        <planeGeometry args={[width * 1.2, depth * 1.2]} />
        <meshStandardMaterial
          color={color}
          transparent
          opacity={opacity}
          side={THREE.DoubleSide}
          depthWrite={false}
          roughness={0.2}
          metalness={0.1}
        />
      </mesh>

      {/* Perimeter border and crosshairs rendered via primitives */}
      <primitive object={borderLine} />
      <primitive object={crosshairLines} />
      <primitive object={arrowHelper} />
    </group>
  );
};
