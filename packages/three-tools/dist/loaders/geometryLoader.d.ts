import * as THREE from 'three';
export type SupportedFormat = 'stl' | 'obj' | 'gltf' | 'glb' | '3mf';
/**
 * Detects format from filename or content header
 */
export declare function detectFormat(filename: string): SupportedFormat;
/**
 * Merges all mesh geometries from a Three.js Group or Object3D hierarchy into a single BufferGeometry.
 */
export declare function mergeObject3DGeometries(root: THREE.Object3D): THREE.BufferGeometry;
/**
 * Parses raw ArrayBuffer into a Three.js BufferGeometry deterministically.
 */
export declare function parseMeshBuffer(buffer: ArrayBuffer, filename: string): Promise<THREE.BufferGeometry>;
/**
 * Loads a mesh from a remote URL (e.g. /models/{id}/file or API download url)
 */
export declare function loadMeshFromUrl(url: string, filename?: string, signal?: AbortSignal): Promise<THREE.BufferGeometry>;
//# sourceMappingURL=geometryLoader.d.ts.map