import React, { useMemo } from 'react';
import * as THREE from 'three';
import { Text } from '@react-three/drei';
import { PrinterProfile } from '@shared/types/api';
import { createOrcaBedMaterial, PlateTextureType } from '@three-tools';

interface BuildPlateProps {
  printer: PrinterProfile;
  plateType?: PlateTextureType;
  showEnvelope?: boolean;
  showOrigin?: boolean;
  showExclusionZone?: boolean;
  majorStep?: number; // mm, default 10
  minorStep?: number; // mm, default 1
}

export const BuildPlate: React.FC<BuildPlateProps> = ({
  printer,
  plateType = 'textured_pei',
  showEnvelope = true,
  showOrigin = true,
  showExclusionZone = true,
  majorStep = 10,
  minorStep = 1,
}) => {
  const bedWidth = printer.build_width_mm || 256;
  const bedDepth = printer.build_depth_mm || 256;
  const bedHeight = printer.build_height_mm || 256;

  // OrcaSlicer Shader Bed Material
  const bedMaterial = useMemo(() => {
    return createOrcaBedMaterial({
      plateType,
      bedWidth,
      bedDepth,
      majorGridMm: majorStep,
      minorGridMm: minorStep,
      showExclusionZone,
    });
  }, [plateType, bedWidth, bedDepth, majorStep, minorStep, showExclusionZone]);

  // Height ruler ticks on the build volume envelope corners (every 50mm)
  const heightTicks = useMemo(() => {
    const ticks: { z: number; label: string }[] = [];
    for (let z = 50; z <= bedHeight; z += 50) {
      ticks.push({ z, label: `${z}mm` });
    }
    return ticks;
  }, [bedHeight]);

  return (
    <group name="BuildPlateRoot">
      {/* 1. Physical Build Sheet Surface with Procedural OrcaSlicer PEI Shader */}
      <group position={[0, 0, 0]}>
        {/* Top Surface Quad for Shader */}
        <mesh receiveShadow position={[0, 0, 0]}>
          <planeGeometry args={[bedWidth, bedDepth]} />
          <primitive object={bedMaterial} attach="material" />
        </mesh>

        {/* Physical Plate Base & Edge Chamfer */}
        <mesh receiveShadow position={[0, 0, -1.0]}>
          <boxGeometry args={[bedWidth + 2, bedDepth + 2, 2.0]} />
          <meshStandardMaterial
            color="#0b0f17"
            roughness={0.9}
            metalness={0.3}
          />
        </mesh>
      </group>

      {/* 2. Origin Triad Marker (0,0,0) */}
      {showOrigin && (
        <group position={[0, 0, 0.2]} name="OriginIndicator">
          {/* X Axis - Red */}
          <arrowHelper
            args={[
              new THREE.Vector3(1, 0, 0),
              new THREE.Vector3(0, 0, 0),
              24,
              0xef4444,
              5,
              2.5,
            ]}
          />
          <Text
            position={[30, 0, 0]}
            fontSize={6}
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
              24,
              0x22c55e,
              5,
              2.5,
            ]}
          />
          <Text
            position={[0, 30, 0]}
            fontSize={6}
            color="#22c55e"
            anchorX="center"
            anchorY="middle"
          >
            Y
          </Text>

          {/* Z Axis - Cyan */}
          <arrowHelper
            args={[
              new THREE.Vector3(0, 0, 1),
              new THREE.Vector3(0, 0, 0),
              24,
              0x38bdf8,
              5,
              2.5,
            ]}
          />
          <Text
            position={[0, 0, 30]}
            fontSize={6}
            color="#38bdf8"
            anchorX="center"
            anchorY="middle"
          >
            Z
          </Text>

          {/* Center Origin Dot */}
          <mesh position={[0, 0, 0]}>
            <sphereGeometry args={[1.5, 16, 16]} />
            <meshBasicMaterial color="#f8fafc" />
          </mesh>
        </group>
      )}

      {/* 3. Printable Volume Bounding Envelope (Wireframe Box + Height Rulers) */}
      {showEnvelope && (
        <group position={[0, 0, bedHeight / 2]} name="PrintVolumeEnvelope">
          <mesh>
            <boxGeometry args={[bedWidth, bedDepth, bedHeight]} />
            <meshBasicMaterial
              color="#0ea5e9"
              wireframe
              transparent
              opacity={0.2}
            />
          </mesh>

          {/* Height Ruler Ticks along rear-left vertical pillar */}
          {heightTicks.map((tick) => (
            <group
              key={tick.z}
              position={[-bedWidth / 2, -bedDepth / 2, tick.z - bedHeight / 2]}
            >
              {/* Tick line */}
              <mesh position={[2.5, 0, 0]}>
                <boxGeometry args={[5, 0.6, 0.6]} />
                <meshBasicMaterial color="#38bdf8" opacity={0.7} transparent />
              </mesh>
              <Text
                position={[10, 0, 0]}
                fontSize={5}
                color="#7dd3fc"
                anchorX="left"
                anchorY="middle"
              >
                {tick.label}
              </Text>
            </group>
          ))}
        </group>
      )}
    </group>
  );
};
