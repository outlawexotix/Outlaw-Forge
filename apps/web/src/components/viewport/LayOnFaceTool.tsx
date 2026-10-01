'use client';

import React, { useState, useCallback, useMemo } from 'react';
import * as THREE from 'three';
import { ThreeEvent } from '@react-three/fiber';
import { getTriangleFromFaceIndex, calculateRotationToBed } from '@three-tools';

export interface LayOnFaceToolProps {
  geometry: THREE.BufferGeometry | null;
  meshRef: React.RefObject<THREE.Mesh>;
  enabled: boolean;
  onOrientToFace: (rotationDeg: [number, number, number]) => void;
}

export const LayOnFaceTool: React.FC<LayOnFaceToolProps> = ({
  geometry,
  meshRef,
  enabled,
  onOrientToFace,
}) => {
  const [hoveredFace, setHoveredFace] = useState<{
    faceIndex: number;
    normal: THREE.Vector3;
    centroid: THREE.Vector3;
    triangle: [THREE.Vector3, THREE.Vector3, THREE.Vector3];
  } | null>(null);

  const handlePointerMove = useCallback(
    (e: ThreeEvent<PointerEvent>) => {
      if (!enabled || !geometry) return;
      e.stopPropagation();

      const intersection = e.intersections.find((i) => i.object === meshRef.current);
      if (intersection && intersection.faceIndex !== undefined) {
        const triData = getTriangleFromFaceIndex(geometry, intersection.faceIndex);
        if (triData) {
          const centroid = new THREE.Vector3()
            .add(triData.vA)
            .add(triData.vB)
            .add(triData.vC)
            .divideScalar(3);

          setHoveredFace({
            faceIndex: intersection.faceIndex,
            normal: triData.normal,
            centroid,
            triangle: [triData.vA, triData.vB, triData.vC],
          });
          return;
        }
      }
      setHoveredFace(null);
    },
    [enabled, geometry, meshRef]
  );

  const handlePointerOut = useCallback(() => {
    setHoveredFace(null);
  }, []);

  const handleClick = useCallback(
    (e: ThreeEvent<MouseEvent>) => {
      if (!enabled || !hoveredFace) return;
      e.stopPropagation();

      const { eulerDeg } = calculateRotationToBed(hoveredFace.normal);
      onOrientToFace(eulerDeg);
      setHoveredFace(null);
    },
    [enabled, hoveredFace, onOrientToFace]
  );

  // Geometry for highlighted facet polygon
  const highlightGeometry = useMemo(() => {
    if (!hoveredFace) return null;
    const geom = new THREE.BufferGeometry();
    const [vA, vB, vC] = hoveredFace.triangle;
    // Elevate slightly along normal to prevent z-fighting
    const offset = hoveredFace.normal.clone().multiplyScalar(0.15);
    const pA = vA.clone().add(offset);
    const pB = vB.clone().add(offset);
    const pC = vC.clone().add(offset);

    const positions = new Float32Array([
      pA.x, pA.y, pA.z,
      pB.x, pB.y, pB.z,
      pC.x, pC.y, pC.z,
    ]);
    geom.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geom.computeVertexNormals();
    return geom;
  }, [hoveredFace]);

  if (!enabled) return null;

  return (
    <group
      name="LayOnFaceInteraction"
      onPointerMove={handlePointerMove}
      onPointerOut={handlePointerOut}
      onClick={handleClick}
    >
      {/* Invisible raycast catcher proxy aligned with mesh */}
      {hoveredFace && highlightGeometry && (
        <group>
          {/* Highlighted Facet Fill */}
          <mesh geometry={highlightGeometry}>
            <meshBasicMaterial
              color="#38bdf8"
              transparent
              opacity={0.7}
              side={THREE.DoubleSide}
              depthTest={true}
            />
          </mesh>

          {/* Normal Vector Indicator Arrow */}
          <arrowHelper
            args={[
              hoveredFace.normal,
              hoveredFace.centroid,
              18,
              0x0ea5e9,
              4,
              2,
            ]}
          />

          {/* Center Point Dot */}
          <mesh position={hoveredFace.centroid.clone().add(hoveredFace.normal.clone().multiplyScalar(0.2))}>
            <sphereGeometry args={[1.0, 8, 8]} />
            <meshBasicMaterial color="#ffffff" />
          </mesh>
        </group>
      )}
    </group>
  );
};
