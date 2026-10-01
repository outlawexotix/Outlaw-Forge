'use client';

import React from 'react';
import { GizmoHelper, GizmoViewport, GizmoViewcube } from '@react-three/drei';

interface OrientationGizmoProps {
  alignment?: 'top-right' | 'top-left' | 'bottom-right' | 'bottom-left';
  margin?: [number, number];
  mode?: 'viewcube' | 'axes' | 'both';
}

export const OrientationGizmo: React.FC<OrientationGizmoProps> = ({
  alignment = 'top-right',
  margin = [75, 75],
  mode = 'viewcube',
}) => {
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
        />
      ) : (
        <GizmoViewport
          axisColors={['#ef4444', '#38bdf8', '#22c55e']}
          labels={['X', 'Z', 'Y']}
          labelColor="#ffffff"
          axisHeadScale={1}
        />
      )}
    </GizmoHelper>
  );
};
