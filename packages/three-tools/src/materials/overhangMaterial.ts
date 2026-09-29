import * as THREE from 'three';

/**
 * Custom GLSL Shader Material for 3D Print Overhang Inspection.
 *
 * In Slicer Space (Z-up):
 * - Faces pointing upward (Nz >= 0) are rendered in neutral CAD cyan-grey with specular highlights.
 * - Faces pointing downward (Nz < 0) with slope > 45 degrees are highlighted in amber/red.
 * - Critical overhangs (Nz < -0.7071 / 45 deg) are rendered in bright safety red (#ef4444).
 * - Moderate overhangs (-0.7071 <= Nz < 0.0) are rendered in warning amber (#f59e0b).
 */
export function createOverhangInspectionMaterial(options?: {
  thresholdDeg?: number;
  wireframe?: boolean;
}): THREE.ShaderMaterial {
  const thresholdDeg = options?.thresholdDeg ?? 45.0;
  const criticalCos = -Math.cos((thresholdDeg * Math.PI) / 180.0);

  const vertexShader = `
    varying vec3 vNormal;
    varying vec3 vWorldPosition;
    varying vec3 vModelNormal;

    void main() {
      // Pass local model normal (in Slicer space Z-up)
      vModelNormal = normal;
      vNormal = normalize(normalMatrix * normal);
      vec4 worldPos = modelMatrix * vec4(position, 1.0);
      vWorldPosition = worldPos.xyz;
      gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
    }
  `;

  const fragmentShader = `
    uniform vec3 uBaseColor;
    uniform vec3 uWarningColor;
    uniform vec3 uCriticalColor;
    uniform float uCriticalCos;

    varying vec3 vNormal;
    varying vec3 vWorldPosition;
    varying vec3 vModelNormal;

    void main() {
      vec3 norm = normalize(vNormal);
      vec3 modelNorm = normalize(vModelNormal);

      // Light vectors for CAD shading
      vec3 lightDir1 = normalize(vec3(0.5, 0.8, 1.0));
      vec3 lightDir2 = normalize(vec3(-0.6, -0.4, 0.5));
      
      float diff1 = max(dot(norm, lightDir1), 0.0);
      float diff2 = max(dot(norm, lightDir2), 0.0) * 0.35;
      float lighting = 0.35 + diff1 * 0.55 + diff2;

      // In Slicer space, Z is the vertical UP axis
      float nz = modelNorm.z;

      vec3 surfaceColor = uBaseColor;

      if (nz < 0.0) {
        // Downward facing surface
        if (nz < uCriticalCos) {
          // Critical overhang requiring support (> 45 deg) -> Red
          surfaceColor = uCriticalColor;
        } else {
          // Moderate overhang (0 - 45 deg) -> Amber warning
          float t = smoothstep(0.0, uCriticalCos, nz);
          surfaceColor = mix(uWarningColor, uCriticalColor, t);
        }
      }

      vec3 finalColor = surfaceColor * lighting;
      gl_FragColor = vec4(finalColor, 1.0);
    }
  `;

  return new THREE.ShaderMaterial({
    vertexShader,
    fragmentShader,
    uniforms: {
      uBaseColor: { value: new THREE.Color('#38bdf8') },
      uWarningColor: { value: new THREE.Color('#f59e0b') },
      uCriticalColor: { value: new THREE.Color('#ef4444') },
      uCriticalCos: { value: criticalCos },
    },
    wireframe: options?.wireframe ?? false,
    side: THREE.DoubleSide,
  });
}
