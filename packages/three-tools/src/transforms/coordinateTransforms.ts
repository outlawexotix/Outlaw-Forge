import * as THREE from 'three';

export interface Vector3D {
  x: number;
  y: number;
  z: number;
}

export interface BoundingBox3D {
  min: Vector3D;
  max: Vector3D;
  center: Vector3D;
  dimensions: Vector3D; // mm [X=width, Y=depth, Z=height]
}

export interface MeshMetrics {
  vertexCount: number;
  triangleCount: number;
  surfaceAreaCm2: number;
  volumeCm3: number;
  isWatertight: boolean;
  boundingBox: BoundingBox3D;
}

/**
 * Deterministic Transformation Matrix: Slicer Space (Z-up) -> Three.js Space (Y-up)
 * Applies a -90 deg (-PI/2 rad) rotation around the X-axis.
 * [ x_three ]   [ 1   0   0   0 ] [ x_slicer ]
 * [ y_three ] = [ 0   0   1   0 ] [ y_slicer ]
 * [ z_three ]   [ 0  -1   0   0 ] [ z_slicer ]
 * [    1    ]   [ 0   0   0   1 ] [    1     ]
 */
export const MAT_SLICER_TO_THREE = new THREE.Matrix4().set(
  1,  0,  0,  0,
  0,  0,  1,  0,
  0, -1,  0,  0,
  0,  0,  0,  1
);

/**
 * Deterministic Inverse Transformation Matrix: Three.js Space (Y-up) -> Slicer Space (Z-up)
 * Applies a +90 deg (+PI/2 rad) rotation around the X-axis.
 */
export const MAT_THREE_TO_SLICER = new THREE.Matrix4().set(
  1,  0,  0,  0,
  0,  0, -1,  0,
  0,  1,  0,  0,
  0,  0,  0,  1
);

/**
 * Converts a point from Slicer Space (Z-up) to Three.js Space (Y-up).
 */
export function slicerToThreeVector(slicerPoint: Vector3D): THREE.Vector3 {
  return new THREE.Vector3(slicerPoint.x, slicerPoint.z, -slicerPoint.y);
}

/**
 * Converts a point from Three.js Space (Y-up) to Slicer Space (Z-up).
 */
export function threeToSlicerVector(threePoint: THREE.Vector3): Vector3D {
  return {
    x: threePoint.x,
    y: -threePoint.z,
    z: threePoint.y,
  };
}

/**
 * Computes deterministic Axis-Aligned Bounding Box (AABB) in millimeters.
 */
export function computeExactAABB(geometry: THREE.BufferGeometry): BoundingBox3D {
  geometry.computeBoundingBox();
  const box = geometry.boundingBox || new THREE.Box3();

  const min: Vector3D = { x: box.min.x, y: box.min.y, z: box.min.z };
  const max: Vector3D = { x: box.max.x, y: box.max.y, z: box.max.z };

  const dimensions: Vector3D = {
    x: Math.abs(max.x - min.x),
    y: Math.abs(max.y - min.y),
    z: Math.abs(max.z - min.z),
  };

  const center: Vector3D = {
    x: (min.x + max.x) / 2,
    y: (min.y + max.y) / 2,
    z: (min.z + max.z) / 2,
  };

  return { min, max, center, dimensions };
}

/**
 * Centers geometry on the build plate in XY and aligns bottom to Z=0.
 * In Slicer Space:
 * - XY center is positioned at (bedWidth / 2, bedDepth / 2) or (0,0) if centered
 * - Z min is positioned at Z = 0
 */
export function centerGeometryOnBed(
  geometry: THREE.BufferGeometry,
  bedWidthMm: number = 256,
  bedDepthMm: number = 256,
  centerOrigin: boolean = false
): { offset: Vector3D; bounds: BoundingBox3D } {
  geometry.computeBoundingBox();
  const box = geometry.boundingBox || new THREE.Box3();

  const currentCenter = new THREE.Vector3();
  box.getCenter(currentCenter);

  // Calculate target center in XY
  const targetX = centerOrigin ? 0 : bedWidthMm / 2;
  const targetY = centerOrigin ? 0 : bedDepthMm / 2;
  const minZ = box.min.z;

  // Translate geometry so min Z = 0 and center XY matches bed target
  const deltaX = targetX - currentCenter.x;
  const deltaY = targetY - currentCenter.y;
  const deltaZ = -minZ;

  geometry.translate(deltaX, deltaY, deltaZ);
  geometry.computeBoundingBox();
  geometry.computeVertexNormals();

  const newBounds = computeExactAABB(geometry);

  return {
    offset: { x: deltaX, y: deltaY, z: deltaZ },
    bounds: newBounds,
  };
}

/**
 * Computes deterministic mesh metrics: vertex count, triangle count, surface area (cm²),
 * signed volume (cm³), and checks topological manifoldness (watertightness).
 */
export function computeMeshMetrics(geometry: THREE.BufferGeometry): MeshMetrics {
  const positionAttr = geometry.getAttribute('position');
  if (!positionAttr) {
    return {
      vertexCount: 0,
      triangleCount: 0,
      surfaceAreaCm2: 0,
      volumeCm3: 0,
      isWatertight: false,
      boundingBox: {
        min: { x: 0, y: 0, z: 0 },
        max: { x: 0, y: 0, z: 0 },
        center: { x: 0, y: 0, z: 0 },
        dimensions: { x: 0, y: 0, z: 0 },
      },
    };
  }

  const index = geometry.getIndex();
  const vertexCount = positionAttr.count;
  const expectedTriangleCount = Math.floor((index ? index.count : positionAttr.count) / 3);
  let triangleCount = 0;
  let invalidTriangleCount = 0;

  let totalAreaMm2 = 0;
  let totalSignedVolumeMm3 = 0;

  const p1 = new THREE.Vector3();
  const p2 = new THREE.Vector3();
  const p3 = new THREE.Vector3();
  const edge1 = new THREE.Vector3();
  const edge2 = new THREE.Vector3();
  const cross = new THREE.Vector3();

  // Map to track directed edges for manifold / watertightness checking
  // A watertight manifold mesh will have every undirected edge shared by exactly 2 triangles in opposite directions
  const edgeCountMap = new Map<string, number>();

  const addEdge = (vA: string, vB: string) => {
    // undirected canonical key
    const key = vA < vB ? `${vA}_${vB}` : `${vB}_${vA}`;
    edgeCountMap.set(key, (edgeCountMap.get(key) || 0) + 1);
  };

  const quantizeVec = (v: THREE.Vector3): string => {
    return `${Number(v.x).toFixed(4)},${Number(v.y).toFixed(4)},${Number(v.z).toFixed(4)}`;
  };

  const readVertex = (target: THREE.Vector3, vertexIndex: number): boolean => {
    if (!Number.isInteger(vertexIndex) || vertexIndex < 0 || vertexIndex >= positionAttr.count) {
      return false;
    }

    const x = Number(positionAttr.getX(vertexIndex));
    const y = Number(positionAttr.getY(vertexIndex));
    const z = Number(positionAttr.getZ(vertexIndex));
    if (![x, y, z].every(Number.isFinite)) {
      return false;
    }

    target.set(x, y, z);
    return true;
  };

  const processTriangle = (v1: THREE.Vector3, v2: THREE.Vector3, v3: THREE.Vector3) => {
    // 1. Surface Area
    edge1.subVectors(v2, v1);
    edge2.subVectors(v3, v1);
    cross.crossVectors(edge1, edge2);
    totalAreaMm2 += cross.length() * 0.5;

    // 2. Signed Volume via Divergence Theorem / Tetrahedral decomposition
    totalSignedVolumeMm3 += v1.dot(cross) / 6.0;

    // 3. Watertight edge tracking
    const k1 = quantizeVec(v1);
    const k2 = quantizeVec(v2);
    const k3 = quantizeVec(v3);
    addEdge(k1, k2);
    addEdge(k2, k3);
    addEdge(k3, k1);
  };

  if (index) {
    for (let i = 0; i < index.count; i += 3) {
      const valid =
        readVertex(p1, Number(index.getX(i))) &&
        readVertex(p2, Number(index.getX(i + 1))) &&
        readVertex(p3, Number(index.getX(i + 2)));
      if (!valid) {
        invalidTriangleCount += 1;
        continue;
      }
      processTriangle(p1, p2, p3);
      triangleCount += 1;
    }
  } else {
    for (let i = 0; i < expectedTriangleCount * 3; i += 3) {
      const valid = readVertex(p1, i) && readVertex(p2, i + 1) && readVertex(p3, i + 2);
      if (!valid) {
        invalidTriangleCount += 1;
        continue;
      }
      processTriangle(p1, p2, p3);
      triangleCount += 1;
    }
  }

  // Check watertightness: every edge must have an exact count of 2
  let isWatertight = triangleCount > 0 && invalidTriangleCount === 0;
  for (const count of edgeCountMap.values()) {
    if (count !== 2) {
      isWatertight = false;
      break;
    }
  }

  // 1 mm² = 0.01 cm²
  const surfaceAreaCm2 = Math.round((totalAreaMm2 * 0.01) * 100) / 100;
  // 1 mm³ = 0.001 cm³
  const volumeCm3 = Math.round((Math.abs(totalSignedVolumeMm3) * 0.001) * 100) / 100;

  const boundingBox = computeExactAABB(geometry);

  return {
    vertexCount,
    triangleCount,
    surfaceAreaCm2,
    volumeCm3,
    isWatertight,
    boundingBox,
  };
}

export interface OverhangAnalysisResult {
  totalAreaCm2: number;
  overhangAreaCm2: number;
  overhangPercentage: number;
  criticalThresholdDeg: number;
}

/**
 * Computes deterministic overhang surface area and percentage for 3D printability.
 * In Slicer Space (Z-up):
 * Faces with normal pointing downward (nz < 0) and angle with vertical > thresholdDeg
 * are flagged as requiring support structures.
 */
export function computeOverhangMetrics(
  geometry: THREE.BufferGeometry,
  thresholdDeg: number = 45
): OverhangAnalysisResult {
  const positionAttr = geometry.getAttribute('position');
  if (!positionAttr) {
    return {
      totalAreaCm2: 0,
      overhangAreaCm2: 0,
      overhangPercentage: 0,
      criticalThresholdDeg: thresholdDeg,
    };
  }

  const index = geometry.getIndex();
  let totalAreaMm2 = 0;
  let overhangAreaMm2 = 0;

  const criticalCos = -Math.cos((thresholdDeg * Math.PI) / 180.0);

  const p1 = new THREE.Vector3();
  const p2 = new THREE.Vector3();
  const p3 = new THREE.Vector3();
  const e1 = new THREE.Vector3();
  const e2 = new THREE.Vector3();
  const normal = new THREE.Vector3();

  const checkTriangle = (v1: THREE.Vector3, v2: THREE.Vector3, v3: THREE.Vector3) => {
    e1.subVectors(v2, v1);
    e2.subVectors(v3, v1);
    normal.crossVectors(e1, e2);
    const area = normal.length() * 0.5;
    totalAreaMm2 += area;

    normal.normalize();
    // nz is the Z component of face normal in Slicer Space (Z-up)
    // If nz < 0, it points downward. If nz <= criticalCos (e.g. <= -0.7071), angle is > 45 deg from vertical
    if (normal.z < -0.001 && normal.z <= criticalCos) {
      overhangAreaMm2 += area;
    }
  };

  if (index) {
    for (let i = 0; i < index.count; i += 3) {
      p1.fromBufferAttribute(positionAttr, index.getX(i));
      p2.fromBufferAttribute(positionAttr, index.getX(i + 1));
      p3.fromBufferAttribute(positionAttr, index.getX(i + 2));
      checkTriangle(p1, p2, p3);
    }
  } else {
    for (let i = 0; i < positionAttr.count; i += 3) {
      p1.fromBufferAttribute(positionAttr, i);
      p2.fromBufferAttribute(positionAttr, i + 1);
      p3.fromBufferAttribute(positionAttr, i + 2);
      checkTriangle(p1, p2, p3);
    }
  }

  const totalAreaCm2 = Math.round((totalAreaMm2 * 0.01) * 100) / 100;
  const overhangAreaCm2 = Math.round((overhangAreaMm2 * 0.01) * 100) / 100;
  const overhangPercentage = totalAreaMm2 > 0 ? Math.round((overhangAreaMm2 / totalAreaMm2) * 1000) / 10 : 0;

  return {
    totalAreaCm2,
    overhangAreaCm2,
    overhangPercentage,
    criticalThresholdDeg: thresholdDeg,
  };
}
