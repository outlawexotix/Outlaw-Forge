import * as THREE from 'three';

export interface InfillCrossSectionOptions {
  planePoint?: [number, number, number];
  planeNormal?: [number, number, number];
  pattern?: 'gyroid' | 'honeycomb' | 'rectilinear' | 'cubic';
  density?: number;
  unitCellSizeMm?: number;
  wallThicknessMm?: number;
  baseColor?: string;
  infillColor?: string;
  cutColor?: string;
  wireframe?: boolean;
}

/**
 * Procedural Infill Cross-Section Material.
 * Renders real-time procedural TPMS Gyroid, Honeycomb, Rectilinear, or Cubic infill patterns
 * on clipped cross-section surfaces and interior cavity cuts with hardware GLSL shader acceleration.
 */
export function createInfillCrossSectionMaterial(
  options: InfillCrossSectionOptions = {}
): THREE.ShaderMaterial {
  const {
    planePoint = [0, 0, 20],
    planeNormal = [0, 0, 1],
    pattern = 'gyroid',
    density = 0.2,
    unitCellSizeMm = 10.0,
    wallThicknessMm = 2.0,
    baseColor = '#38bdf8',
    infillColor = '#10b981',
    cutColor = '#f59e0b',
    wireframe = false,
  } = options;

  let patternId = 0; // 0: gyroid, 1: honeycomb, 2: rectilinear, 3: cubic
  if (pattern === 'honeycomb') patternId = 1;
  else if (pattern === 'rectilinear') patternId = 2;
  else if (pattern === 'cubic') patternId = 3;

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
    uniform vec3 uInfillColor;
    uniform vec3 uCutColor;
    uniform vec3 uPlanePoint;
    uniform vec3 uPlaneNormal;
    uniform int uPattern;
    uniform float uDensity;
    uniform float uCellSize;
    uniform float uWallThickness;

    varying vec3 vNormal;
    varying vec3 vWorldPosition;
    varying vec3 vModelPosition;

    #define PI 3.14159265359

    // Gyroid TPMS SDF function
    float gyroidSDF(vec3 p, float scale) {
      vec3 k = p * (2.0 * PI / max(1.0, scale));
      return sin(k.x)*cos(k.y) + sin(k.y)*cos(k.z) + sin(k.z)*cos(k.x);
    }

    void main() {
      // Discard cut geometry above clipping plane
      vec3 toPoint = vModelPosition - uPlanePoint;
      float dist = dot(toPoint, normalize(uPlaneNormal));
      if (dist > 0.0) {
        discard;
      }

      vec3 norm = normalize(vNormal);

      // CAD lighting
      vec3 light1 = normalize(vec3(0.5, 0.8, 1.0));
      vec3 light2 = normalize(vec3(-0.6, -0.4, 0.5));
      float diff1 = max(dot(norm, light1), 0.0);
      float diff2 = max(dot(norm, light2), 0.0) * 0.35;
      float lighting = 0.45 + diff1 * 0.45 + diff2;

      vec3 finalColor = uBaseColor;
      float edgeDist = abs(dist);

      if (edgeDist < 1.2) {
        // We are on or directly adjacent to the cross-section slice plane
        vec3 p = vModelPosition;
        float infillHit = 0.0;

        if (uPattern == 0) {
          // Gyroid TPMS
          float g = gyroidSDF(p, uCellSize);
          float threshold = 0.1 + 1.2 * uDensity;
          if (abs(g) < threshold) {
            infillHit = 1.0;
          }
        } else if (uPattern == 1) {
          // Honeycomb (Hexagonal)
          float s = max(1.0, uCellSize);
          vec2 hCoord = p.xy / s;
          vec2 q = abs(mod(hCoord + 0.5, 1.0) - 0.5);
          float hexD = max(q.x * 0.866025 + q.y * 0.5, q.y);
          if (hexD > (0.5 * (1.0 - uDensity * 0.5))) {
            infillHit = 1.0;
          }
        } else if (uPattern == 2) {
          // Rectilinear 2D Grid
          float s = max(1.0, uCellSize);
          vec2 gCoord = mod(abs(p.xy), s);
          float ribThick = s * uDensity * 0.5;
          if (gCoord.x < ribThick || gCoord.y < ribThick) {
            infillHit = 1.0;
          }
        } else if (uPattern == 3) {
          // Cubic 3D Volumetric Slabs
          float s = max(1.0, uCellSize);
          vec3 cCoord = mod(abs(p), s);
          float slabThick = s * (1.0 - pow(1.0 - uDensity, 0.333333));
          if (cCoord.x < slabThick || cCoord.y < slabThick || cCoord.z < slabThick) {
            infillHit = 1.0;
          }
        }

        if (infillHit > 0.5) {
          finalColor = mix(uInfillColor, uCutColor, 0.3);
        } else {
          finalColor = mix(uBaseColor, uCutColor, 0.7);
        }
      }

      gl_FragColor = vec4(finalColor * lighting, 1.0);
    }
  `;

  return new THREE.ShaderMaterial({
    vertexShader,
    fragmentShader,
    uniforms: {
      uBaseColor: { value: new THREE.Color(baseColor) },
      uInfillColor: { value: new THREE.Color(infillColor) },
      uCutColor: { value: new THREE.Color(cutColor) },
      uPlanePoint: { value: new THREE.Vector3(...planePoint) },
      uPlaneNormal: { value: new THREE.Vector3(...planeNormal) },
      uPattern: { value: patternId },
      uDensity: { value: density },
      uCellSize: { value: unitCellSizeMm },
      uWallThickness: { value: wallThicknessMm },
    },
    wireframe,
    side: THREE.DoubleSide,
  });
}
