import * as THREE from 'three';

export interface OrcaCrossSectionOptions {
  planePoint?: [number, number, number];
  planeNormal?: [number, number, number];
  baseColor?: string;
  cutColor?: string;
  wireframe?: boolean;
}

/**
 * Procedural OrcaSlicer Interactive Planar Cross-Section Material.
 * Uses hardware GLSL clipping to discard fragments above the active slice plane
 * and highlights cross-sectional boundaries with contrasting CAD color.
 */
export function createOrcaCrossSectionMaterial(options: OrcaCrossSectionOptions = {}): THREE.ShaderMaterial {
  const {
    planePoint = [0, 0, 20],
    planeNormal = [0, 0, 1],
    baseColor = '#38bdf8',
    cutColor = '#f43f5e',
    wireframe = false,
  } = options;

  const vertexShader = `
    varying vec3 vNormal;
    varying vec3 vWorldPosition;
    varying vec3 vModelPosition;

    void main() {
      vModelPosition = position;
      vNormal = normalize(normalMatrix * normal);
      vec4 worldPos = modelMatrix * vec4(position, 1.0);
      vWorldPosition = worldPos.xyz;
      gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
    }
  `;

  const fragmentShader = `
    uniform vec3 uBaseColor;
    uniform vec3 uCutColor;
    uniform vec3 uPlanePoint;
    uniform vec3 uPlaneNormal;

    varying vec3 vNormal;
    varying vec3 vWorldPosition;
    varying vec3 vModelPosition;

    void main() {
      // Hardware plane clipping test in slicer coordinate space
      // Distance = dot(P - PlaneOrigin, PlaneNormal)
      vec3 toPoint = vModelPosition - uPlanePoint;
      float dist = dot(toPoint, normalize(uPlaneNormal));

      if (dist > 0.0) {
        discard; // Discard cut geometry
      }

      vec3 norm = normalize(vNormal);

      // Studio CAD lighting
      vec3 light1 = normalize(vec3(0.5, 0.8, 1.0));
      vec3 light2 = normalize(vec3(-0.6, -0.4, 0.5));
      float diff1 = max(dot(norm, light1), 0.0);
      float diff2 = max(dot(norm, light2), 0.0) * 0.35;
      float lighting = 0.4 + diff1 * 0.5 + diff2;

      // Highlight proximity to cut plane (within 0.8mm edge)
      float edgeDist = abs(dist);
      vec3 color = uBaseColor;
      if (edgeDist < 0.8) {
        float edgeT = smoothstep(0.8, 0.0, edgeDist);
        color = mix(uBaseColor, uCutColor, edgeT * 0.9);
      }

      gl_FragColor = vec4(color * lighting, 1.0);
    }
  `;

  return new THREE.ShaderMaterial({
    vertexShader,
    fragmentShader,
    uniforms: {
      uBaseColor: { value: new THREE.Color(baseColor) },
      uCutColor: { value: new THREE.Color(cutColor) },
      uPlanePoint: { value: new THREE.Vector3(...planePoint) },
      uPlaneNormal: { value: new THREE.Vector3(...planeNormal) },
    },
    wireframe,
    side: THREE.DoubleSide,
  });
}
