'use client';

import React from 'react';
import { Billboard, Text } from '@react-three/drei';
import { BoundingBox3D } from '@three-tools';

export interface ModelDimensionTagsProps {
  bounds: BoundingBox3D | null;
  scale: [number, number, number];
  visible?: boolean;
}

/**
 * 3D Floating CAD Dimension HUD Tags.
 * Renders millimeter dimensions directly along the bounding box axes (X, Y, Z)
 * in 3D space with auto-orienting camera billboards, matching OrcaSlicer CAD inspect & scale tools.
 */
export const ModelDimensionTags: React.FC<ModelDimensionTagsProps> = ({
  bounds,
  scale,
  visible = true,
}) => {
  if (!visible || !bounds) return null;

  const { min, max, dimensions } = bounds;

  // Actual scaled dimensions in millimeters
  const dimX = Math.round(dimensions.x * scale[0] * 10) / 10;
  const dimY = Math.round(dimensions.y * scale[1] * 10) / 10;
  const dimZ = Math.round(dimensions.z * scale[2] * 10) / 10;

  const scalePct = Math.round(scale[0] * 100 * 10) / 10;

  return (
    <group name="ModelDimensionTags">
      {/* 1. X Dimension Tag (Front Bottom Edge) */}
      <Billboard
        position={[(min.x + max.x) / 2, min.y - 8, min.z]}
        follow={true}
        lockX={false}
        lockY={false}
        lockZ={false}
      >
        <group>
          <mesh position={[0, 0, -0.1]}>
            <planeGeometry args={[26, 7]} />
            <meshBasicMaterial color="#090d16" transparent opacity={0.85} />
          </mesh>
          <Text
            fontSize={4}
            color="#ef4444"
            anchorX="center"
            anchorY="middle"
          >
            {`X: ${dimX}mm`}
          </Text>
        </group>
      </Billboard>

      {/* 2. Y Dimension Tag (Right Bottom Edge) */}
      <Billboard
        position={[max.x + 8, (min.y + max.y) / 2, min.z]}
        follow={true}
        lockX={false}
        lockY={false}
        lockZ={false}
      >
        <group>
          <mesh position={[0, 0, -0.1]}>
            <planeGeometry args={[26, 7]} />
            <meshBasicMaterial color="#090d16" transparent opacity={0.85} />
          </mesh>
          <Text
            fontSize={4}
            color="#22c55e"
            anchorX="center"
            anchorY="middle"
          >
            {`Y: ${dimY}mm`}
          </Text>
        </group>
      </Billboard>

      {/* 3. Z Dimension Tag (Rear Right Vertical Pillar) */}
      <Billboard
        position={[max.x + 8, max.y + 8, (min.z + max.z) / 2]}
        follow={true}
        lockX={false}
        lockY={false}
        lockZ={false}
      >
        <group>
          <mesh position={[0, 0, -0.1]}>
            <planeGeometry args={[26, 7]} />
            <meshBasicMaterial color="#090d16" transparent opacity={0.85} />
          </mesh>
          <Text
            fontSize={4}
            color="#38bdf8"
            anchorX="center"
            anchorY="middle"
          >
            {`Z: ${dimZ}mm`}
          </Text>
        </group>
      </Billboard>

      {/* 4. Top Scale Factor Badge */}
      <Billboard
        position={[(min.x + max.x) / 2, (min.y + max.y) / 2, max.z + 12]}
        follow={true}
        lockX={false}
        lockY={false}
        lockZ={false}
      >
        <group>
          <mesh position={[0, 0, -0.1]}>
            <planeGeometry args={[28, 8]} />
            <meshBasicMaterial color="#0ea5e9" transparent opacity={0.9} />
          </mesh>
          <Text
            fontSize={4.2}
            color="#ffffff"
            anchorX="center"
            anchorY="middle"
            fontWeight="bold"
          >
            {`${scalePct}%`}
          </Text>
        </group>
      </Billboard>
    </group>
  );
};
