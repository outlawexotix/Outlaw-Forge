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
export declare function createOverhangInspectionMaterial(options?: {
    thresholdDeg?: number;
    wireframe?: boolean;
}): THREE.ShaderMaterial;
//# sourceMappingURL=overhangMaterial.d.ts.map