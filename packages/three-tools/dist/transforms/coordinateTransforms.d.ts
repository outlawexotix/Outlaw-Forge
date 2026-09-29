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
    dimensions: Vector3D;
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
export declare const MAT_SLICER_TO_THREE: THREE.Matrix4;
/**
 * Deterministic Inverse Transformation Matrix: Three.js Space (Y-up) -> Slicer Space (Z-up)
 * Applies a +90 deg (+PI/2 rad) rotation around the X-axis.
 */
export declare const MAT_THREE_TO_SLICER: THREE.Matrix4;
/**
 * Converts a point from Slicer Space (Z-up) to Three.js Space (Y-up).
 */
export declare function slicerToThreeVector(slicerPoint: Vector3D): THREE.Vector3;
/**
 * Converts a point from Three.js Space (Y-up) to Slicer Space (Z-up).
 */
export declare function threeToSlicerVector(threePoint: THREE.Vector3): Vector3D;
/**
 * Computes deterministic Axis-Aligned Bounding Box (AABB) in millimeters.
 */
export declare function computeExactAABB(geometry: THREE.BufferGeometry): BoundingBox3D;
/**
 * Centers geometry on the build plate in XY and aligns bottom to Z=0.
 * In Slicer Space:
 * - XY center is positioned at (bedWidth / 2, bedDepth / 2) or (0,0) if centered
 * - Z min is positioned at Z = 0
 */
export declare function centerGeometryOnBed(geometry: THREE.BufferGeometry, bedWidthMm?: number, bedDepthMm?: number, centerOrigin?: boolean): {
    offset: Vector3D;
    bounds: BoundingBox3D;
};
/**
 * Computes deterministic mesh metrics: vertex count, triangle count, surface area (cm²),
 * signed volume (cm³), and checks topological manifoldness (watertightness).
 */
export declare function computeMeshMetrics(geometry: THREE.BufferGeometry): MeshMetrics;
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
export declare function computeOverhangMetrics(geometry: THREE.BufferGeometry, thresholdDeg?: number): OverhangAnalysisResult;
//# sourceMappingURL=coordinateTransforms.d.ts.map