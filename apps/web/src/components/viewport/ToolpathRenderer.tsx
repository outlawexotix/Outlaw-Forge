'use client';

import React, { useMemo } from 'react';
import * as THREE from 'three';

export type FeatureType = 'travel' | 'outer_wall' | 'inner_wall' | 'infill' | 'solid_infill' | 'support' | 'skirt';

export interface ToolpathSegment {
  start: [number, number, number];
  end: [number, number, number];
  kind: 'travel' | 'extrusion';
  featureType: FeatureType;
  layerIndex: number;
  feedrate?: number;
  extrusionLength?: number;
}

export interface ParsedGCodeData {
  segments: ToolpathSegment[];
  layers: {
    layerIndex: number;
    zHeight: number;
    segmentCount: number;
    extrusionLengthMm: number;
  }[];
  totalLayers: number;
  maxZ: number;
  totalExtrusionMm: number;
}

/**
 * Parses G-code text into categorized toolpath segments with layer index and feature type tagging.
 */
export function parseGCodeToolpaths(source: string): ParsedGCodeData {
  const segments: ToolpathSegment[] = [];
  const layerMap = new Map<number, { zHeight: number; segmentCount: number; extrusionLengthMm: number }>();
  
  let position: [number, number, number] = [0, 0, 0];
  let absolute = true;
  let units = 1;
  let currentLayer = 0;
  let currentZ = 0;
  let currentFeature: FeatureType = 'infill';
  let totalExtrusionMm = 0;

  const lines = source.split(/\r?\n/);

  for (const rawLine of lines) {
    const trimmed = rawLine.trim();
    if (!trimmed) continue;

    // Detect OrcaSlicer / Bambu / PrusaSlicer feature comments
    if (trimmed.startsWith(';TYPE:')) {
      const typeStr = trimmed.slice(6).toLowerCase();
      if (typeStr.includes('outer wall') || typeStr.includes('perimeter')) {
        currentFeature = 'outer_wall';
      } else if (typeStr.includes('inner wall') || typeStr.includes('internal perimeter')) {
        currentFeature = 'inner_wall';
      } else if (typeStr.includes('solid fill') || typeStr.includes('top solid')) {
        currentFeature = 'solid_infill';
      } else if (typeStr.includes('fill') || typeStr.includes('sparse infill')) {
        currentFeature = 'infill';
      } else if (typeStr.includes('support')) {
        currentFeature = 'support';
      } else if (typeStr.includes('skirt') || typeStr.includes('brim')) {
        currentFeature = 'skirt';
      }
    } else if (trimmed.startsWith(';LAYER_CHANGE') || trimmed.startsWith(';LAYER:')) {
      const match = trimmed.match(/;LAYER:(\d+)/i);
      if (match) {
        currentLayer = parseInt(match[1], 10);
      }
    }

    const line = trimmed.split(';', 1)[0].trim();
    if (!line) continue;

    const command = line.match(/^(G0|G1|G20|G21|G90|G91)\b/i)?.[1]?.toUpperCase();
    if (!command) continue;

    if (command === 'G20') { units = 25.4; continue; }
    if (command === 'G21') { units = 1; continue; }
    if (command === 'G90') { absolute = true; continue; }
    if (command === 'G91') { absolute = false; continue; }
    if (command !== 'G0' && command !== 'G1') continue;

    const next = [...position] as [number, number, number];
    let hasZChange = false;

    for (const axis of ['X', 'Y', 'Z'] as const) {
      const match = line.match(new RegExp(`${axis}(-?\\d+(?:\\.\\d+)?)`, 'i'));
      if (!match) continue;
      const value = Number(match[1]) * units;
      const index = axis === 'X' ? 0 : axis === 'Y' ? 1 : 2;
      next[index] = absolute ? value : position[index] + value;
      if (axis === 'Z' && Math.abs(next[2] - currentZ) > 0.001) {
        hasZChange = true;
      }
    }

    // Extrusion detection
    const eMatch = line.match(/\bE(-?\d+(?:\.\d+)?)/i);
    const hasExtrusion = !!eMatch && Number(eMatch[1]) > 0;
    const eLength = eMatch ? Math.max(0, Number(eMatch[1])) : 0;

    if (hasZChange && next[2] > currentZ + 0.05) {
      currentZ = next[2];
      // Increment layer if not explicitly set by comments
      if (!trimmed.includes(';LAYER:')) {
        currentLayer = layerMap.size;
      }
    }

    if (next[0] !== position[0] || next[1] !== position[1] || next[2] !== position[2]) {
      const isExtrusion = command === 'G1' && hasExtrusion;
      const segKind = isExtrusion ? 'extrusion' : 'travel';
      const feature = segKind === 'travel' ? 'travel' : currentFeature;

      segments.push({
        start: position,
        end: next,
        kind: segKind,
        featureType: feature,
        layerIndex: currentLayer,
        extrusionLength: eLength,
      });

      if (isExtrusion) {
        totalExtrusionMm += eLength;
      }

      // Record layer metadata
      const existing = layerMap.get(currentLayer);
      if (existing) {
        existing.segmentCount++;
        existing.extrusionLengthMm += eLength;
        existing.zHeight = Math.max(existing.zHeight, next[2]);
      } else {
        layerMap.set(currentLayer, {
          zHeight: next[2],
          segmentCount: 1,
          extrusionLengthMm: eLength,
        });
      }

      position = next;
    }
  }

  const layers = Array.from(layerMap.entries()).map(([layerIndex, data]) => ({
    layerIndex,
    zHeight: data.zHeight,
    segmentCount: data.segmentCount,
    extrusionLengthMm: data.extrusionLengthMm,
  })).sort((a, b) => a.layerIndex - b.layerIndex);

  const maxZ = layers.length > 0 ? layers[layers.length - 1].zHeight : 0;

  return {
    segments,
    layers,
    totalLayers: layers.length > 0 ? layers.length : 1,
    maxZ,
    totalExtrusionMm,
  };
}

export interface ToolpathRendererProps {
  source: string;
  bedWidth: number;
  bedDepth: number;
  visible?: boolean;
  currentLayer?: number;
  showSingleLayer?: boolean;
  showTravel?: boolean;
  showOuterWall?: boolean;
  showInnerWall?: boolean;
  showInfill?: boolean;
  showSupport?: boolean;
  onGCodeParsed?: (data: ParsedGCodeData) => void;
}

export const ToolpathRenderer: React.FC<ToolpathRendererProps> = ({
  source,
  bedWidth,
  bedDepth,
  visible = true,
  currentLayer = Infinity,
  showSingleLayer = false,
  showTravel = true,
  showOuterWall = true,
  showInnerWall = true,
  showInfill = true,
  showSupport = true,
  onGCodeParsed,
}) => {
  const parsedData = useMemo(() => {
    const data = parseGCodeToolpaths(source);
    if (onGCodeParsed) {
      onGCodeParsed(data);
    }
    return data;
  }, [source, onGCodeParsed]);

  const centeredSegments = useMemo(() => {
    const { segments } = parsedData;
    if (segments.length === 0) return segments;

    const points = segments.flatMap((s) => [s.start, s.end]);
    const minX = Math.min(...points.map((p) => p[0]));
    const maxX = Math.max(...points.map((p) => p[0]));
    const minY = Math.min(...points.map((p) => p[1]));
    const maxY = Math.max(...points.map((p) => p[1]));

    const shouldCenter =
      minX >= -0.001 &&
      minY >= -0.001 &&
      maxX <= bedWidth + 0.001 &&
      maxY <= bedDepth + 0.001 &&
      (maxX > bedWidth * 0.6 || maxY > bedDepth * 0.6);

    if (!shouldCenter) return segments;

    return segments.map((seg) => ({
      ...seg,
      start: [seg.start[0] - bedWidth / 2, seg.start[1] - bedDepth / 2, seg.start[2]] as [number, number, number],
      end: [seg.end[0] - bedWidth / 2, seg.end[1] - bedDepth / 2, seg.end[2]] as [number, number, number],
    }));
  }, [parsedData, bedWidth, bedDepth]);

  // Filter segments by layer and feature visibility
  const filteredSegments = useMemo(() => {
    return centeredSegments.filter((seg) => {
      // Layer filter
      if (showSingleLayer) {
        if (seg.layerIndex !== currentLayer) return false;
      } else {
        if (seg.layerIndex > currentLayer) return false;
      }

      // Feature filter
      if (seg.kind === 'travel' && !showTravel) return false;
      if (seg.featureType === 'outer_wall' && !showOuterWall) return false;
      if (seg.featureType === 'inner_wall' && !showInnerWall) return false;
      if (['infill', 'solid_infill', 'skirt'].includes(seg.featureType) && !showInfill) return false;
      if (seg.featureType === 'support' && !showSupport) return false;

      return true;
    });
  }, [centeredSegments, currentLayer, showSingleLayer, showTravel, showOuterWall, showInnerWall, showInfill, showSupport]);

  // Group geometries by feature type for color distinction
  const featureGeometries = useMemo(() => {
    const travelCoords: number[] = [];
    const outerWallCoords: number[] = [];
    const innerWallCoords: number[] = [];
    const infillCoords: number[] = [];
    const solidInfillCoords: number[] = [];
    const supportCoords: number[] = [];
    const skirtCoords: number[] = [];

    for (const seg of filteredSegments) {
      const coords = seg.featureType === 'travel' ? travelCoords :
        seg.featureType === 'outer_wall' ? outerWallCoords :
        seg.featureType === 'inner_wall' ? innerWallCoords :
        seg.featureType === 'solid_infill' ? solidInfillCoords :
        seg.featureType === 'support' ? supportCoords :
        seg.featureType === 'skirt' ? skirtCoords : infillCoords;

      coords.push(...seg.start, ...seg.end);
    }

    const createGeom = (coords: number[]) => {
      const geom = new THREE.BufferGeometry();
      if (coords.length > 0) {
        geom.setAttribute('position', new THREE.Float32BufferAttribute(coords, 3));
      }
      return geom;
    };

    return {
      travel: createGeom(travelCoords),
      outerWall: createGeom(outerWallCoords),
      innerWall: createGeom(innerWallCoords),
      infill: createGeom(infillCoords),
      solidInfill: createGeom(solidInfillCoords),
      support: createGeom(supportCoords),
      skirt: createGeom(skirtCoords),
    };
  }, [filteredSegments]);

  if (!visible || centeredSegments.length === 0) return null;

  return (
    <group name="GCodeToolpaths" renderOrder={3}>
      {/* Travel moves - Muted gray */}
      {showTravel && (
        <lineSegments frustumCulled={false} geometry={featureGeometries.travel}>
          <lineBasicMaterial color="#64748b" transparent opacity={0.35} depthWrite={false} />
        </lineSegments>
      )}
      {/* Outer perimeters - Bright Cyan */}
      <lineSegments frustumCulled={false} geometry={featureGeometries.outerWall}>
        <lineBasicMaterial color="#06b6d4" linewidth={2.5} depthWrite={false} />
      </lineSegments>
      {/* Inner perimeters - Deep Blue */}
      <lineSegments frustumCulled={false} geometry={featureGeometries.innerWall}>
        <lineBasicMaterial color="#3b82f6" linewidth={2} depthWrite={false} />
      </lineSegments>
      {/* Sparse Infill - Gold/Amber */}
      <lineSegments frustumCulled={false} geometry={featureGeometries.infill}>
        <lineBasicMaterial color="#f59e0b" linewidth={1.5} depthWrite={false} />
      </lineSegments>
      {/* Solid infill & Top/Bottom surfaces - Purple */}
      <lineSegments frustumCulled={false} geometry={featureGeometries.solidInfill}>
        <lineBasicMaterial color="#a855f7" linewidth={2} depthWrite={false} />
      </lineSegments>
      {/* Support structures - Emerald Green */}
      <lineSegments frustumCulled={false} geometry={featureGeometries.support}>
        <lineBasicMaterial color="#10b981" linewidth={1.5} depthWrite={false} />
      </lineSegments>
      {/* Skirt / Brim - Coral */}
      <lineSegments frustumCulled={false} geometry={featureGeometries.skirt}>
        <lineBasicMaterial color="#f43f5e" linewidth={1.5} depthWrite={false} />
      </lineSegments>
    </group>
  );
};
