import React, { useMemo } from 'react';
import * as THREE from 'three';
import { Grid, Text } from '@react-three/drei';
import { PrinterProfile } from '@shared/types/api';

interface BuildPlateProps {
  printer: PrinterProfile;
  showEnvelope?: boolean;
  showOrigin?: boolean;
  majorStep?: number; // mm, default 10
  minorStep?: number; // mm, default 1
}

export const BuildPlate: React.FC<BuildPlateProps> = ({
  printer,
  showEnvelope = true,
  showOrigin = true,
  majorStep = 10,
  minorStep = 1,
}) => {
  const bedWidth = printer.build_width_mm || 256;
  const bedDepth = printer.build_depth_mm || 256;
  const bedHeight = printer.build_height_mm || 256;
  const isCenterOrigin = true;

  // Build plate offset if origin is front-left vs center
  const bedCenterOffset = useMemo<[number, number, number]>(() => {
    if (isCenterOrigin) {
      return [0, 0, 0];
    }
    return [bedWidth / 2, bedDepth / 2, 0];
  }, [isCenterOrigin, bedWidth, bedDepth]);

  // Origin indicator position in slicer coordinates
  const originPos = useMemo<[number, number, number]>(() => {
    return [0, 0, 0];
  }, []);

  return (
    <group name="BuildPlateRoot">
      {/* Bed Base Surface & Dual Frequency Grid */}
      <group position={[bedCenterOffset[0], bedCenterOffset[1], -0.1]}>
        {/* Physical Build Sheet Surface */}
        <mesh receiveShadow position={[0, 0, -0.5]}>
          <boxGeometry args={[bedWidth, bedDepth, 1]} />
          <meshStandardMaterial
            color="#1e293b"
            roughness={0.8}
            metalness={0.2}
          />
        </mesh>

        {/* High precision Drei Grid overlay aligned with millimeter grid */}
        {/* Note: In SlicerSpace (Z-up), ground is XY plane (rotation [Math.PI / 2, 0, 0]) */}
        <group position={[0, 0, 0.1]} rotation={[Math.PI / 2, 0, 0]}>
          <Grid
            args={[bedWidth, bedDepth]}
            cellSize={minorStep}
            cellThickness={0.4}
            cellColor="#334155"
            sectionSize={majorStep}
            sectionThickness={1.0}
            sectionColor="#64748b"
            fadeDistance={Math.max(bedWidth, bedDepth) * 2.5}
            fadeStrength={1.2}
            infiniteGrid={false}
          />
        </group>
      </group>

      {/* Origin Triad Marker (0,0,0) */}
      {showOrigin && (
        <group position={originPos} name="OriginIndicator">
          {/* X Axis - Red */}
          <arrowHelper
            args={[
              new THREE.Vector3(1, 0, 0),
              new THREE.Vector3(0, 0, 0),
              22,
              0xef4444,
              5,
              2.5,
            ]}
          />
          <Text
            position={[28, 0, 0]}
            fontSize={7}
            color="#ef4444"
            anchorX="center"
            anchorY="middle"
          >
            X
          </Text>

          {/* Y Axis - Green */}
          <arrowHelper
            args={[
              new THREE.Vector3(0, 1, 0),
              new THREE.Vector3(0, 0, 0),
              22,
              0x22c55e,
              5,
              2.5,
            ]}
          />
          <Text
            position={[0, 28, 0]}
            fontSize={7}
            color="#22c55e"
            anchorX="center"
            anchorY="middle"
          >
            Y
          </Text>

          {/* Z Axis - Blue */}
          <arrowHelper
            args={[
              new THREE.Vector3(0, 0, 1),
              new THREE.Vector3(0, 0, 0),
              22,
              0x38bdf8,
              5,
              2.5,
            ]}
          />
          <Text
            position={[0, 0, 28]}
            fontSize={7}
            color="#38bdf8"
            anchorX="center"
            anchorY="middle"
          >
            Z
          </Text>

          {/* Origin Origin Sphere Marker */}
          <mesh position={[0, 0, 0]}>
            <sphereGeometry args={[1.5, 16, 16]} />
            <meshBasicMaterial color="#f8fafc" />
          </mesh>
        </group>
      )}

      {/* Printable Volume Bounding Envelope (Wireframe Box) */}
      {showEnvelope && (
        <group position={[bedCenterOffset[0], bedCenterOffset[1], bedHeight / 2]} name="PrintVolumeEnvelope">
          <mesh>
            <boxGeometry args={[bedWidth, bedDepth, bedHeight]} />
            <meshBasicMaterial
              color="#0ea5e9"
              wireframe
              transparent
              opacity={0.25}
            />
          </mesh>
        </group>
      )}
    </group>
  );
};
