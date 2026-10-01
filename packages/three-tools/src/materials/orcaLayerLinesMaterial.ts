import * as THREE from 'three';

export interface OrcaLayerLinesOptions {
  layerHeightMm?: number;
  baseColor?: string;
  lineContrast?: number;
  wireframe?: boolean;
}

/**
 * Procedural OrcaSlicer Layer Lines Visualization Material.
 * Renders microscopic horizontal layer line banding in Slicer space Z coordinates
 * to preview FDM layer deposition in real time without CPU re-meshing.
 */
export function createOrcaLayerLinesMaterial(options: OrcaLayerLinesOptions = {}): THREE.ShaderMaterial {
  const {
    layerHeightMm = 0.20,
    baseColor = '#38bdf8',
    lineContrast = 0.35,
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
    uniform float uLayerHeight;
    uniform float uContrast;

    varying vec3 vNormal;
    varying vec3 vWorldPosition;
    varying vec3 vModelPosition;

    void main() {
      vec3 norm = normalize(vNormal);

      // Studio 3-point CAD lighting
      vec3 light1 = normalize(vec3(0.6, 0.8, 0.9));
      vec3 light2 = normalize(vec3(-0.7, -0.3, 0.6));
      vec3 light3 = normalize(vec3(0.0, -1.0, 0.2));

      float diff1 = max(dot(norm, light1), 0.0);
      float diff2 = max(dot(norm, light2), 0.0) * 0.4;
      float diff3 = max(dot(norm, light3), 0.0) * 0.15;
      float lighting = 0.35 + diff1 * 0.55 + diff2 + diff3;

      // Specular highlight for plastic/PLA appearance
      vec3 viewDir = normalize(-vWorldPosition);
      vec3 halfDir = normalize(light1 + viewDir);
      float spec = pow(max(dot(norm, halfDir), 0.0), 32.0) * 0.25;

      // Procedural layer line calculation based on vertical Z coordinate in mm
      // vModelPosition.z is the height above bed in Slicer space
      float zPos = vModelPosition.z;
      float layerPhase = fract(zPos / uLayerHeight);

      // Smooth sine modulation for layer line ribbing/creases
      float layerBand = sin(layerPhase * 3.14159265 * 2.0) * 0.5 + 0.5;
      layerBand = pow(layerBand, 1.8);

      // Darken grooved layer boundaries
      float shade = 1.0 - (layerBand * uContrast);

      vec3 finalColor = (uBaseColor * shade * lighting) + vec3(spec);

      gl_FragColor = vec4(finalColor, 1.0);
    }
  `;

  return new THREE.ShaderMaterial({
    vertexShader,
    fragmentShader,
    uniforms: {
      uBaseColor: { value: new THREE.Color(baseColor) },
      uLayerHeight: { value: Math.max(0.04, layerHeightMm) },
      uContrast: { value: lineContrast },
    },
    wireframe,
    side: THREE.DoubleSide,
  });
}
