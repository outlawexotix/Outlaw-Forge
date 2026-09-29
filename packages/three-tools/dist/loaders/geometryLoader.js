import * as THREE from 'three';
import { STLLoader, OBJLoader, GLTFLoader } from 'three-stdlib';
/**
 * Detects format from filename or content header
 */
export function detectFormat(filename) {
    const ext = filename.split('.').pop()?.toLowerCase() || '';
    if (ext === 'stl')
        return 'stl';
    if (ext === 'obj')
        return 'obj';
    if (ext === 'glb')
        return 'glb';
    if (ext === 'gltf')
        return 'gltf';
    if (ext === '3mf')
        return '3mf';
    return 'stl';
}
/**
 * Merges all mesh geometries from a Three.js Group or Object3D hierarchy into a single BufferGeometry.
 */
export function mergeObject3DGeometries(root) {
    const geometries = [];
    root.traverse((child) => {
        if (child.isMesh) {
            const mesh = child;
            if (mesh.geometry) {
                const clonedGeom = mesh.geometry.clone();
                clonedGeom.applyMatrix4(mesh.matrixWorld);
                geometries.push(clonedGeom);
            }
        }
    });
    if (geometries.length === 0) {
        return new THREE.BufferGeometry();
    }
    if (geometries.length === 1) {
        return geometries[0];
    }
    // Expand indexed geometries while merging so each output triangle has the
    // correct vertex order. Copying only position attributes would reinterpret
    // an indexed mesh's unique vertices as triangles and corrupt the geometry.
    let totalVertices = 0;
    for (const geom of geometries) {
        const pos = geom.getAttribute('position');
        if (pos)
            totalVertices += geom.getIndex()?.count ?? pos.count;
    }
    const combinedPositions = new Float32Array(totalVertices * 3);
    let offset = 0;
    for (const geom of geometries) {
        const pos = geom.getAttribute('position');
        if (pos) {
            const index = geom.getIndex();
            if (index) {
                for (let i = 0; i < index.count; i += 1) {
                    const vertexIndex = index.getX(i);
                    combinedPositions[offset++] = pos.getX(vertexIndex);
                    combinedPositions[offset++] = pos.getY(vertexIndex);
                    combinedPositions[offset++] = pos.getZ(vertexIndex);
                }
            }
            else {
                const array = pos.array;
                combinedPositions.set(array, offset);
                offset += array.length;
            }
        }
    }
    const merged = new THREE.BufferGeometry();
    merged.setAttribute('position', new THREE.BufferAttribute(combinedPositions, 3));
    merged.computeVertexNormals();
    merged.computeBoundingBox();
    return merged;
}
/**
 * Parses raw ArrayBuffer into a Three.js BufferGeometry deterministically.
 */
export async function parseMeshBuffer(buffer, filename) {
    const format = detectFormat(filename);
    switch (format) {
        case 'stl': {
            const loader = new STLLoader();
            const geometry = loader.parse(buffer);
            if (!geometry.getAttribute('normal')) {
                geometry.computeVertexNormals();
            }
            geometry.computeBoundingBox();
            return geometry;
        }
        case 'obj': {
            const loader = new OBJLoader();
            const textDecoder = new TextDecoder();
            const text = textDecoder.decode(buffer);
            const group = loader.parse(text);
            group.updateMatrixWorld(true);
            return mergeObject3DGeometries(group);
        }
        case 'glb':
        case 'gltf': {
            const loader = new GLTFLoader();
            return new Promise((resolve, reject) => {
                loader.parse(buffer, '', (gltf) => {
                    gltf.scene.updateMatrixWorld(true);
                    const merged = mergeObject3DGeometries(gltf.scene);
                    resolve(merged);
                }, (error) => {
                    reject(new Error(`Failed to parse GLTF/GLB: ${error}`));
                });
            });
        }
        default:
            throw new Error(`Unsupported mesh format: .${format}`);
    }
}
/**
 * Loads a mesh from a remote URL (e.g. /models/{id}/file or API download url)
 */
export async function loadMeshFromUrl(url, filename = 'model.stl', signal) {
    const response = await fetch(url, { signal });
    if (!response.ok) {
        throw new Error(`Failed to fetch model from ${url}: ${response.status} ${response.statusText}`);
    }
    const buffer = await response.arrayBuffer();
    return parseMeshBuffer(buffer, filename);
}
//# sourceMappingURL=geometryLoader.js.map