import React from 'react';

export const SceneLights: React.FC = () => {
  return (
    <group name="StudioLighting">
      {/* Ambient soft fill */}
      <ambientLight intensity={0.65} color="#ffffff" />

      {/* Primary Key Directional Light */}
      <directionalLight
        position={[250, 400, 300]}
        intensity={1.2}
        castShadow
        shadow-mapSize-width={2048}
        shadow-mapSize-height={2048}
        shadow-camera-near={10}
        shadow-camera-far={1000}
        shadow-camera-left={-250}
        shadow-camera-right={250}
        shadow-camera-top={250}
        shadow-camera-bottom={-250}
        shadow-bias={-0.0001}
      />

      {/* Secondary Fill Directional Light */}
      <directionalLight
        position={[-200, 200, -200]}
        intensity={0.4}
        color="#94a3b8"
      />

      {/* Subtle Bottom Ground Fill */}
      <hemisphereLight
        args={['#ffffff', '#1e293b', 0.4]}
      />
    </group>
  );
};
