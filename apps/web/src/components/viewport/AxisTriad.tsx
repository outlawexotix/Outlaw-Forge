'use client';

import React from 'react';
import { Line, Text } from '@react-three/drei';

/**
 * World-space slicer axis reference. The viewport root is rotated for Three.js,
 * so these coordinates remain authored in slicer space: X/Y on the plate and Z
 * vertically out of it.
 */
export const AxisTriad: React.FC<{ size?: number; visible?: boolean }> = ({ size = 32, visible = true }) => (
  <group name="SlicerAxisTriad" visible={visible} position={[-size * 0.45, -size * 0.45, 0.15]}>
    <Line points={[[0, 0, 0], [size, 0, 0]]} color="#ef4444" lineWidth={2.5} />
    <Line points={[[0, 0, 0], [0, size, 0]]} color="#22c55e" lineWidth={2.5} />
    <Line points={[[0, 0, 0], [0, 0, size]]} color="#38bdf8" lineWidth={2.5} />
    <Text position={[size + 3, 0, 0]} fontSize={5} color="#ef4444" anchorX="left" anchorY="middle">X</Text>
    <Text position={[0, size + 3, 0]} fontSize={5} color="#22c55e" anchorX="center" anchorY="bottom">Y</Text>
    <Text position={[0, 0, size + 3]} fontSize={5} color="#38bdf8" anchorX="center" anchorY="bottom">Z</Text>
  </group>
);
