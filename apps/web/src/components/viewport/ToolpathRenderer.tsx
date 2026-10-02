'use client';

import React, { useMemo } from 'react';
import * as THREE from 'three';

export interface ToolpathSegment {
  start: [number, number, number];
  end: [number, number, number];
  kind: 'travel' | 'extrusion';
}

export function parseGCodeToolpaths(source: string): ToolpathSegment[] {
  const segments: ToolpathSegment[] = [];
  let position: [number, number, number] = [0, 0, 0];
  let absolute = true;
  let units = 1;

  for (const rawLine of source.split(/\r?\n/)) {
    const line = rawLine.split(';', 1)[0].trim();
    if (!line) continue;
    const command = line.match(/^(G0|G1|G20|G21|G90|G91)\b/i)?.[1]?.toUpperCase();
    if (!command) continue;
    if (command === 'G20') { units = 25.4; continue; }
    if (command === 'G21') { units = 1; continue; }
    if (command === 'G90') { absolute = true; continue; }
    if (command === 'G91') { absolute = false; continue; }
    if (command !== 'G0' && command !== 'G1') continue;

    const next = [...position] as [number, number, number];
    for (const axis of ['X', 'Y', 'Z'] as const) {
      const match = line.match(new RegExp(`${axis}(-?\\d+(?:\\.\\d+)?)`, 'i'));
      if (!match) continue;
      const value = Number(match[1]) * units;
      const index = axis === 'X' ? 0 : axis === 'Y' ? 1 : 2;
      next[index] = absolute ? value : position[index] + value;
    }
    if (next[0] !== position[0] || next[1] !== position[1] || next[2] !== position[2]) {
      // A G1 without an E word is commonly a travel move; classify by actual
      // extrusion commands instead of assuming every G1 deposits material.
      const hasExtrusion = /\bE-?\d+(?:\.\d+)?/i.test(line);
      segments.push({ start: position, end: next, kind: command === 'G1' && hasExtrusion ? 'extrusion' : 'travel' });
      position = next;
    }
  }
  return segments;
}

export const ToolpathRenderer: React.FC<{ source: string; bedWidth: number; bedDepth: number; visible?: boolean }> = ({ source, bedWidth, bedDepth, visible = true }) => {
  const segments = useMemo(() => {
    const parsed = parseGCodeToolpaths(source);
    if (parsed.length === 0) return parsed;
    const points = parsed.flatMap((segment) => [segment.start, segment.end]);
    const minX = Math.min(...points.map((point) => point[0]));
    const maxX = Math.max(...points.map((point) => point[0]));
    const minY = Math.min(...points.map((point) => point[1]));
    const maxY = Math.max(...points.map((point) => point[1]));
    // Printer-origin G-code is commonly [0, bed] while the viewport uses a
    // centered build plate [-bed/2, bed/2]. Convert only when the bounds make
    // that convention clear; already-centered paths remain untouched.
    const centered = minX >= -0.001 && minY >= -0.001 && maxX <= bedWidth + 0.001 && maxY <= bedDepth + 0.001 &&
      (maxX > bedWidth * 0.6 || maxY > bedDepth * 0.6);
    if (!centered) return parsed;
    return parsed.map((segment) => ({
      ...segment,
      start: [segment.start[0] - bedWidth / 2, segment.start[1] - bedDepth / 2, segment.start[2]],
      end: [segment.end[0] - bedWidth / 2, segment.end[1] - bedDepth / 2, segment.end[2]],
    }));
  }, [source, bedWidth, bedDepth]);
  const { travel, extrusion } = useMemo(() => {
    const travel: number[] = [];
    const extrusion: number[] = [];
    for (const segment of segments) {
      const target = segment.kind === 'travel' ? travel : extrusion;
      target.push(...segment.start, ...segment.end);
    }
    return { travel, extrusion };
  }, [segments]);

  const travelGeometry = useMemo(
    () => new THREE.BufferGeometry().setAttribute('position', new THREE.Float32BufferAttribute(travel, 3)),
    [travel]
  );
  const extrusionGeometry = useMemo(
    () => new THREE.BufferGeometry().setAttribute('position', new THREE.Float32BufferAttribute(extrusion, 3)),
    [extrusion]
  );

  if (!visible || segments.length === 0) return null;
  return (
    <group name="GCodeToolpaths" renderOrder={3}>
      <lineSegments frustumCulled={false} geometry={travelGeometry}>
        <lineBasicMaterial color="#64748b" transparent opacity={0.45} depthWrite={false} />
      </lineSegments>
      <lineSegments frustumCulled={false} geometry={extrusionGeometry}>
        <lineBasicMaterial color="#f59e0b" linewidth={2} depthWrite={false} />
      </lineSegments>
    </group>
  );
};
