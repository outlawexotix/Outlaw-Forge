import React from 'react';
import { GizmoHelper, GizmoViewport } from '@react-three/drei';

interface OrientationGizmoProps {
  alignment?: 'top-right' | 'top-left' | 'bottom-right' | 'bottom-left';
  margin?: [number, number];
}

export const OrientationGizmo: React.FC<OrientationGizmoProps> = ({
  alignment = 'top-right',
  margin = [70, 70],
}) => {
  return (
    <GizmoHelper
      alignment={alignment}
      margin={margin}
      renderOrder={2}
    >
      <GizmoViewport
        axisColors={['#ef4444', '#38bdf8', '#22c55e']}
        labels={['X', 'Z', 'Y']}
        labelColor="#ffffff"
        axisHeadScale={1}
      />
    </GizmoHelper>
  );
};
