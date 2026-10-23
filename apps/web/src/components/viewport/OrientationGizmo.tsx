'use client';

import React from 'react';
import { GizmoHelper, GizmoViewport, GizmoViewcube } from '@react-three/drei';
import type { ThreeEvent } from '@react-three/fiber';
import type { PresetView } from '@shared/types/viewport';

interface OrientationGizmoProps {
  alignment?: 'top-right' | 'top-left' | 'bottom-right' | 'bottom-left';
  margin?: [number, number];
  mode?: 'viewcube' | 'axes' | 'both';
  onPresetView?: (view: PresetView) => void;
}

export const OrientationGizmo: React.FC<OrientationGizmoProps> = ({
  alignment = 'top-right',
  margin = [75, 75],
  mode = 'viewcube',
  onPresetView,
}) => {
  const handleViewcubeClick = (event: ThreeEvent<MouseEvent>): null => {
    if (!onPresetView) return null;

    // Faces are ordered to match the box geometry's +/- X, +/- Y, +/- Z faces.
    // Edge and corner meshes carry a non-zero position, which maps to the
    // viewport's standard isometric framing action.
    const position = event.object.position;
    if (position.lengthSq() > 0) {
      onPresetView('isometric');
      return null;
    }

    const faceViews: PresetView[] = ['right', 'left', 'top', 'bottom', 'front', 'back'];
    const view = faceViews[Math.floor((event.faceIndex ?? 0) / 2)];
    if (view) onPresetView(view);
    return null;
  };

  return (
    <GizmoHelper
      alignment={alignment}
      margin={margin}
      renderOrder={2}
    >
      {mode === 'viewcube' ? (
        <GizmoViewcube
          faces={['Right', 'Left', 'Top', 'Bottom', 'Front', 'Back']}
          color="#1e293b"
          hoverColor="#0284c7"
          textColor="#ffffff"
          strokeColor="#334155"
          opacity={0.95}
          onClick={handleViewcubeClick}
        />
      ) : (
        <GizmoViewport
          axisColors={['#ef4444', '#22c55e', '#38bdf8']}
          labels={['X', 'Y', 'Z']}
          labelColor="#ffffff"
          axisHeadScale={1}
        />
      )}
    </GizmoHelper>
  );
};
