import * as THREE from 'three';

export type PlateTextureType = 'textured_pei' | 'smooth_pei' | 'cool_plate' | 'engineering_plate';

export interface OrcaBedMaterialOptions {
  plateType?: PlateTextureType;
  bedWidth?: number;
  bedDepth?: number;
  majorGridMm?: number;
  minorGridMm?: number;
  showExclusionZone?: boolean;
}

/**
 * Procedural OrcaSlicer PEI Build Plate Shader Material.
 * Renders textured powder coat, millimeter CAD grid, printable margins,
 * and Bambu/Orca nozzle wipe exclusion zone in real-time GLSL.
 */
export function createOrcaBedMaterial(options: OrcaBedMaterialOptions = {}): THREE.ShaderMaterial {
  const {
    plateType = 'textured_pei',
    bedWidth = 256,
    bedDepth = 256,
    majorGridMm = 10.0,
    minorGridMm = 1.0,
    showExclusionZone = true,
  } = options;

  // Color palettes for different OrcaSlicer bed sheets
  const platePalettes: Record<PlateTextureType, { base: string; secondary: string; roughness: number; metalness: number }> = {
    textured_pei: {
      base: '#b89438',       // Gold/Amber powder coat
      secondary: '#8a6b1c',
      roughness: 0.85,
      metalness: 0.35,
    },
    smooth_pei: {
      base: '#1a1d24',       // Satin Black PEI
      secondary: '#111318',
      roughness: 0.45,
      metalness: 0.1,
    },
    cool_plate: {
      base: '#334155',       // Cool Sheet Slate
      secondary: '#1e293b',
      roughness: 0.6,
      metalness: 0.05,
    },
    engineering_plate: {
      base: '#1c222d',       // Engineering High-Temp Carbon
      secondary: '#0f131a',
      roughness: 0.7,
      metalness: 0.2,
    },
  };

  const palette = platePalettes[plateType] || platePalettes.textured_pei;

  const vertexShader = `
    varying vec2 vUv;
    varying vec3 vWorldPos;
    varying vec3 vNormal;

    void main() {
      vUv = uv;
      vNormal = normalize(normalMatrix * normal);
      vec4 worldPos = modelMatrix * vec4(position, 1.0);
      vWorldPos = worldPos.xyz;
      gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
    }
  `;

  const fragmentShader = `
    uniform vec3 uBaseColor;
    uniform vec3 uSecondaryColor;
    uniform vec2 uBedDimensions;
    uniform float uMajorGrid;
    uniform float uMinorGrid;
    uniform bool uShowExclusion;
    uniform int uPlateType; // 0: textured_pei, 1: smooth_pei, 2: cool, 3: eng

    varying vec2 vUv;
    varying vec3 vWorldPos;
    varying vec3 vNormal;

    // Pseudo-random hash for procedural noise
    float hash(vec2 p) {
      return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453123);
    }

    // High frequency procedural micro-grain noise for PEI texture
    float peiNoise(vec2 p) {
      vec2 i = floor(p);
      vec2 f = fract(p);
      f = f * f * (3.0 - 2.0 * f);
      float a = hash(i);
      float b = hash(i + vec2(1.0, 0.0));
      float c = hash(i + vec2(0.0, 1.0));
      float d = hash(i + vec2(1.0, 1.0));
      return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
    }

    void main() {
      // Slicer coords in millimeters from center (-W/2 to +W/2, -D/2 to +D/2)
      vec2 coordMm = (vUv - 0.5) * uBedDimensions;

      // 1. Base Plate Texture & Grain
      float grain = peiNoise(coordMm * 4.0) * 0.5 + peiNoise(coordMm * 12.0) * 0.5;
      vec3 bedColor = mix(uSecondaryColor, uBaseColor, grain * 0.4 + 0.6);

      // 2. Anti-aliased Millimeter Grid Lines
      // Minor Grid (1mm)
      vec2 minorGridPos = abs(fract(coordMm / uMinorGrid - 0.5) - 0.5) / fwidth(coordMm / uMinorGrid);
      float minorLine = 1.0 - min(min(minorGridPos.x, minorGridPos.y), 1.0);

      // Major Grid (10mm)
      vec2 majorGridPos = abs(fract(coordMm / uMajorGrid - 0.5) - 0.5) / fwidth(coordMm / uMajorGrid);
      float majorLine = 1.0 - min(min(majorGridPos.x, majorGridPos.y), 1.0);

      // 50mm Accent Grid
      vec2 accentGridPos = abs(fract(coordMm / (uMajorGrid * 5.0) - 0.5) - 0.5) / fwidth(coordMm / (uMajorGrid * 5.0));
      float accentLine = 1.0 - min(min(accentGridPos.x, accentGridPos.y), 1.0);

      // Blend grid lines
      vec3 gridMinorColor = mix(bedColor, vec3(0.15, 0.2, 0.28), 0.35);
      vec3 gridMajorColor = mix(bedColor, vec3(0.7, 0.8, 0.95), 0.45);
      vec3 gridAccentColor = mix(bedColor, vec3(0.9, 0.95, 1.0), 0.7);

      bedColor = mix(bedColor, gridMinorColor, minorLine * 0.35);
      bedColor = mix(bedColor, gridMajorColor, majorLine * 0.65);
      bedColor = mix(bedColor, gridAccentColor, accentLine * 0.85);

      // 3. Printable Border Boundary
      float borderDistX = (uBedDimensions.x * 0.5) - abs(coordMm.x);
      float borderDistY = (uBedDimensions.y * 0.5) - abs(coordMm.y);
      float minBorder = min(borderDistX, borderDistY);
      if (minBorder < 1.2 && minBorder > 0.0) {
        bedColor = mix(bedColor, vec3(0.06, 0.75, 0.95), 0.85); // Cyan boundary line
      }

      // 4. Bambu/OrcaSlicer Wipe Nozzle Exclusion Zone (Top-Left corner)
      // Size: 28mm width x 28mm height at top-left edge
      if (uShowExclusion) {
        float exMinX = -uBedDimensions.x * 0.5 + 2.0;
        float exMaxX = exMinX + 26.0;
        float exMaxY = uBedDimensions.y * 0.5 - 2.0;
        float exMinY = exMaxY - 26.0;

        if (coordMm.x >= exMinX && coordMm.x <= exMaxX && coordMm.y >= exMinY && coordMm.y <= exMaxY) {
          // Yellow-Black diagonal hazard warning stripes
          float stripe = fract((coordMm.x + coordMm.y) * 0.15);
          vec3 hazardYellow = vec3(0.95, 0.75, 0.05);
          vec3 hazardDark = vec3(0.12, 0.12, 0.14);
          vec3 stripeColor = stripe > 0.5 ? hazardYellow : hazardDark;

          // Boundary border around exclusion zone
          float dEdge = min(
            min(abs(coordMm.x - exMinX), abs(coordMm.x - exMaxX)),
            min(abs(coordMm.y - exMinY), abs(coordMm.y - exMaxY))
          );
          if (dEdge < 0.8) {
            stripeColor = vec3(1.0, 0.2, 0.2); // Red border
          }

          bedColor = mix(bedColor, stripeColor, 0.85);
        }
      }

      // Lighting simulation
      vec3 lightDir = normalize(vec3(0.4, 0.8, 0.9));
      float diff = max(dot(vNormal, lightDir), 0.0) * 0.4 + 0.6;
      vec3 finalColor = bedColor * diff;

      gl_FragColor = vec4(finalColor, 1.0);
    }
  `;

  let typeId = 0;
  if (plateType === 'smooth_pei') typeId = 1;
  else if (plateType === 'cool_plate') typeId = 2;
  else if (plateType === 'engineering_plate') typeId = 3;

  return new THREE.ShaderMaterial({
    vertexShader,
    fragmentShader,
    uniforms: {
      uBaseColor: { value: new THREE.Color(palette.base) },
      uSecondaryColor: { value: new THREE.Color(palette.secondary) },
      uBedDimensions: { value: new THREE.Vector2(bedWidth, bedDepth) },
      uMajorGrid: { value: majorGridMm },
      uMinorGrid: { value: minorGridMm },
      uShowExclusion: { value: showExclusionZone },
      uPlateType: { value: typeId },
    },
    side: THREE.FrontSide,
  });
}
