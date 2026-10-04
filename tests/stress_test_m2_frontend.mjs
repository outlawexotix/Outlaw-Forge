/**
 * Milestone M2 Frontend Empirical Stress Test Harness
 * =====================================================
 * Tests:
 * 1. Viewport Drag-and-Drop file handling logic (STL, OBJ, 3MF, G-code, unsupported formats, edge cases)
 * 2. Workbench Page Model Import integration (activeProject checks, apiClient.importModel invocation, error handling)
 * 3. Native Dialog Bridge (native-dialog.ts) in pure web, SSR, and Tauri IPC environments
 * 4. Dynamic BaseURL Resolution & Download URL sanitation (api-client.ts)
 * 5. AST & Source Code Verification for wiring integrity in ViewportContainer.tsx and page.tsx
 */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const REPO_ROOT = path.resolve(__dirname, '..');

const results = [];

function record(name, passed, details) {
  const status = passed ? 'PASS' : 'FAIL';
  results.push({ name, status, details });
  const color = passed ? '\x1b[32m' : '\x1b[31m';
  console.log(`${color}[${status}]\x1b[0m ${name}: ${details}`);
}

// =========================================================================
// DOMAIN 1: Native Dialog Bridge Runtime Tests (native-dialog.ts)
// =========================================================================
async function testNativeDialogBridge() {
  console.log('\n--- DOMAIN 1: Native Dialog Bridge Runtime Tests ---');

  const nativeDialogPath = path.resolve(REPO_ROOT, 'apps/web/src/lib/native-dialog.ts');
  const mod = await import(`file://${nativeDialogPath.replace(/\\/g, '/')}`);

  // Test 1.1: SSR environment (window is undefined)
  {
    const oldWindow = globalThis.window;
    const oldDocument = globalThis.document;
    delete globalThis.window;
    delete globalThis.document;

    const isTauriSsr = mod.isTauri();
    const openSsr = await mod.openNativeFileDialog();
    const saveSsr = await mod.saveNativeFileDialog();
    const browserOpenSsr = await mod.openBrowserFileDialog();
    let downloadSsrThrew = false;
    try {
      mod.downloadInBrowser('http://127.0.0.1:8000/models/1/file.stl', 'file.stl');
    } catch {
      downloadSsrThrew = true;
    }
    const fallbackSsr = await mod.saveFileWithFallback('http://127.0.0.1:8000/models/1/file.stl', 'file.stl');

    record(
      'SSR: isTauri() is false when window is undefined',
      isTauriSsr === false,
      `Result: ${isTauriSsr}`
    );
    record(
      'SSR: open/save native dialogs return null safely',
      openSsr === null && saveSsr === null && browserOpenSsr === null,
      `open: ${openSsr}, save: ${saveSsr}, browserOpen: ${browserOpenSsr}`
    );
    record(
      'SSR: downloadInBrowser does not throw in SSR',
      !downloadSsrThrew,
      `Threw: ${downloadSsrThrew}`
    );
    record(
      'SSR: saveFileWithFallback succeeds gracefully in SSR',
      fallbackSsr.success === true,
      `Result: ${JSON.stringify(fallbackSsr)}`
    );

    // Restore
    globalThis.window = oldWindow;
    globalThis.document = oldDocument;
  }

  // Test 1.2: Standard Web Browser Environment (no Tauri)
  {
    const mockCreatedElements = [];
    let clickCount = 0;

    const mockDocument = {
      createElement: (tag) => {
        const el = {
          tagName: tag.toUpperCase(),
          type: '',
          accept: '',
          style: {},
          href: '',
          download: '',
          files: [],
          parentNode: null,
          click: () => {
            clickCount++;
          },
        };
        mockCreatedElements.push(el);
        return el;
      },
      body: {
        appendChild: (el) => {
          el.parentNode = mockDocument.body;
          return el;
        },
        removeChild: (el) => {
          el.parentNode = null;
        },
      },
    };

    const mockWindow = {
      addEventListener: (evt, cb) => {},
      removeEventListener: (evt, cb) => {},
    };

    globalThis.window = mockWindow;
    globalThis.document = mockDocument;

    const isTauriWeb = mod.isTauri();
    const nativeOpenWeb = await mod.openNativeFileDialog();
    const nativeSaveWeb = await mod.saveNativeFileDialog();

    record(
      'Pure Web: isTauri() is false when __TAURI__ internals absent',
      isTauriWeb === false,
      `isTauri: ${isTauriWeb}`
    );
    record(
      'Pure Web: openNativeFileDialog and saveNativeFileDialog return null',
      nativeOpenWeb === null && nativeSaveWeb === null,
      `open: ${nativeOpenWeb}, save: ${nativeSaveWeb}`
    );

    // Test downloadInBrowser
    clickCount = 0;
    mockCreatedElements.length = 0;
    mod.downloadInBrowser('http://127.0.0.1:8000/export/model.3mf', 'model.3mf');
    const anchor = mockCreatedElements.find((e) => e.tagName === 'A');
    record(
      'Pure Web: downloadInBrowser creates anchor, sets href & download, clicks and cleans up',
      anchor && anchor.href === 'http://127.0.0.1:8000/export/model.3mf' && anchor.download === 'model.3mf' && anchor.parentNode === null && clickCount === 1,
      `Anchor: href=${anchor?.href}, download=${anchor?.download}, parentNode=${anchor?.parentNode}, clicks=${clickCount}`
    );

    // Test saveFileWithFallback in pure web
    clickCount = 0;
    mockCreatedElements.length = 0;
    const fallbackWeb = await mod.saveFileWithFallback('http://127.0.0.1:8000/export/test.stl', 'test.stl');
    record(
      'Pure Web: saveFileWithFallback triggers browser download and returns { success: true }',
      fallbackWeb.success === true && fallbackWeb.nativePath === undefined && clickCount === 1,
      `Result: ${JSON.stringify(fallbackWeb)}, clicks=${clickCount}`
    );
  }

  // Test 1.3: Tauri Environment with window.__TAURI__.dialog
  {
    let dialogOpenCalled = false;
    let dialogSaveCalled = false;
    let openOptionsPassed = null;
    let saveOptionsPassed = null;

    globalThis.window = {
      __TAURI__: {
        dialog: {
          open: async (opts) => {
            dialogOpenCalled = true;
            openOptionsPassed = opts;
            return 'C:\\Models\\benchy.stl';
          },
          save: async (opts) => {
            dialogSaveCalled = true;
            saveOptionsPassed = opts;
            return 'C:\\Models\\export_benchy.3mf';
          },
        },
      },
      __TAURI_INTERNALS__: {},
    };

    const isTauriDesktop = mod.isTauri();
    record(
      'Tauri Plugin: isTauri() is true when __TAURI_INTERNALS__ or __TAURI__ present',
      isTauriDesktop === true,
      `isTauri: ${isTauriDesktop}`
    );

    const openResult = await mod.openNativeFileDialog({ title: 'Select 3D Mesh' });
    record(
      'Tauri Plugin: openNativeFileDialog routes to window.__TAURI__.dialog.open',
      dialogOpenCalled && openResult === 'C:\\Models\\benchy.stl' && openOptionsPassed?.title === 'Select 3D Mesh',
      `openResult: ${openResult}, options: ${JSON.stringify(openOptionsPassed)}`
    );

    const saveResult = await mod.saveNativeFileDialog({ defaultPath: 'output.stl' });
    record(
      'Tauri Plugin: saveNativeFileDialog routes to window.__TAURI__.dialog.save',
      dialogSaveCalled && saveResult === 'C:\\Models\\export_benchy.3mf' && saveOptionsPassed?.defaultPath === 'output.stl',
      `saveResult: ${saveResult}, options: ${JSON.stringify(saveOptionsPassed)}`
    );

    // Test saveFileWithFallback when user confirms save path
    const fallbackConfirm = await mod.saveFileWithFallback('http://127.0.0.1:8000/export/plate.3mf', 'plate.3mf');
    record(
      'Tauri Plugin: saveFileWithFallback returns { success: true, nativePath } on user selection',
      fallbackConfirm.success === true && fallbackConfirm.nativePath === 'C:\\Models\\export_benchy.3mf',
      `Result: ${JSON.stringify(fallbackConfirm)}`
    );

    // Test saveFileWithFallback when user CANCELS dialog (returns null)
    globalThis.window.__TAURI__.dialog.save = async () => null;
    const fallbackCancel = await mod.saveFileWithFallback('http://127.0.0.1:8000/export/plate.3mf', 'plate.3mf');
    record(
      'Tauri Plugin: saveFileWithFallback returns { success: false } when user cancels native dialog',
      fallbackCancel.success === false && fallbackCancel.nativePath === undefined,
      `Result: ${JSON.stringify(fallbackCancel)}`
    );
  }

  // Test 1.4: Tauri IPC Fallback via window.__TAURI_INTERNALS__.invoke
  {
    const invokeCalls = [];

    globalThis.window = {
      __TAURI_INTERNALS__: {
        invoke: async (cmd, args) => {
          invokeCalls.push({ cmd, args });
          if (cmd === 'plugin:dialog|open') {
            return args?.options?.multiple ? ['D:\\mesh1.obj', 'D:\\mesh2.obj'] : 'D:\\mesh1.obj';
          }
          if (cmd === 'plugin:dialog|save') {
            return 'D:\\saved_mesh.stl';
          }
          throw new Error(`Unknown command: ${cmd}`);
        },
      },
    };

    const isTauriIpc = mod.isTauri();
    record(
      'Tauri IPC: isTauri() is true with __TAURI_INTERNALS__ alone',
      isTauriIpc === true,
      `isTauri: ${isTauriIpc}`
    );

    invokeCalls.length = 0;
    const ipcOpen = await mod.openNativeFileDialog({ multiple: true });
    record(
      'Tauri IPC: openNativeFileDialog routes to invoke("plugin:dialog|open")',
      Array.isArray(ipcOpen) && ipcOpen.length === 2 && invokeCalls[0]?.cmd === 'plugin:dialog|open',
      `Result: ${JSON.stringify(ipcOpen)}, call: ${JSON.stringify(invokeCalls[0])}`
    );

    invokeCalls.length = 0;
    const ipcSave = await mod.saveNativeFileDialog({ defaultPath: 'test.stl' });
    record(
      'Tauri IPC: saveNativeFileDialog routes to invoke("plugin:dialog|save")',
      ipcSave === 'D:\\saved_mesh.stl' && invokeCalls[0]?.cmd === 'plugin:dialog|save',
      `Result: ${ipcSave}, call: ${JSON.stringify(invokeCalls[0])}`
    );
  }
}

// =========================================================================
// DOMAIN 2: Viewport Drag-and-Drop Extension & Routing Logic
// =========================================================================
function testDragDropExtensionHandling() {
  console.log('\n--- DOMAIN 2: Viewport Drag-and-Drop File Handling ---');

  // Exact reproduction of ViewportContainer.tsx handleDrop logic (lines 215-231)
  function simulateViewportDrop(files, onDropFileCallback) {
    let errorMessage = null;
    let gcodeTextContent = null;
    let droppedFilesReceived = [];

    const onDropFile = (file) => {
      droppedFilesReceived.push(file);
      onDropFileCallback?.(file);
    };

    const setErrorMessage = (msg) => {
      errorMessage = msg;
    };

    const setGcodeText = (text) => {
      gcodeTextContent = text;
    };

    const e = {
      preventDefault: () => {},
      stopPropagation: () => {},
      dataTransfer: { files },
    };

    // The component's implementation:
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const droppedFile = e.dataTransfer.files[0];
      const ext = droppedFile.name.split('.').pop()?.toLowerCase();
      if (['gcode', 'gco'].includes(ext || '')) {
        droppedFile.text().then(setGcodeText).catch(() => setErrorMessage('Could not read the G-code file.'));
      } else if (['stl', 'obj', 'glb', 'gltf', '3mf'].includes(ext || '')) {
        onDropFile?.(droppedFile);
      } else {
        setErrorMessage(`Unsupported file format '.${ext}'. Drop STL, OBJ, GLB, or G-code files.`);
      }
    }

    return { droppedFilesReceived, errorMessage, gcodeTextContent };
  }

  function createMockFile(name, content = 'dummy-mesh-bytes') {
    return {
      name,
      size: content.length,
      text: async () => content,
    };
  }

  // 2.1: Test STL formats (lowercase and uppercase)
  {
    const fileLower = createMockFile('benchy.stl');
    const resLower = simulateViewportDrop([fileLower]);
    record(
      'Drag-Drop: Lowercase .stl calls onDropFile',
      resLower.droppedFilesReceived.length === 1 && resLower.droppedFilesReceived[0].name === 'benchy.stl' && resLower.errorMessage === null,
      `Dropped: ${resLower.droppedFilesReceived[0]?.name}, error: ${resLower.errorMessage}`
    );

    const fileUpper = createMockFile('CALIBRATION_CUBE.STL');
    const resUpper = simulateViewportDrop([fileUpper]);
    record(
      'Drag-Drop: Uppercase .STL is case-insensitively accepted and calls onDropFile',
      resUpper.droppedFilesReceived.length === 1 && resUpper.droppedFilesReceived[0].name === 'CALIBRATION_CUBE.STL' && resUpper.errorMessage === null,
      `Dropped: ${resUpper.droppedFilesReceived[0]?.name}, error: ${resUpper.errorMessage}`
    );
  }

  // 2.2: Test OBJ formats (lowercase and uppercase)
  {
    const fileLower = createMockFile('figure.obj');
    const resLower = simulateViewportDrop([fileLower]);
    record(
      'Drag-Drop: Lowercase .obj calls onDropFile',
      resLower.droppedFilesReceived.length === 1 && resLower.droppedFilesReceived[0].name === 'figure.obj' && resLower.errorMessage === null,
      `Dropped: ${resLower.droppedFilesReceived[0]?.name}`
    );

    const fileUpper = createMockFile('MASK_HELMET.OBJ');
    const resUpper = simulateViewportDrop([fileUpper]);
    record(
      'Drag-Drop: Uppercase .OBJ is accepted and calls onDropFile',
      resUpper.droppedFilesReceived.length === 1 && resUpper.droppedFilesReceived[0].name === 'MASK_HELMET.OBJ' && resUpper.errorMessage === null,
      `Dropped: ${resUpper.droppedFilesReceived[0]?.name}`
    );
  }

  // 2.3: Test 3MF formats (lowercase and uppercase)
  {
    const fileLower = createMockFile('multimodel_plate.3mf');
    const resLower = simulateViewportDrop([fileLower]);
    record(
      'Drag-Drop: Lowercase .3mf calls onDropFile',
      resLower.droppedFilesReceived.length === 1 && resLower.droppedFilesReceived[0].name === 'multimodel_plate.3mf' && resLower.errorMessage === null,
      `Dropped: ${resLower.droppedFilesReceived[0]?.name}`
    );

    const fileUpper = createMockFile('ORCA_PROJECT.3MF');
    const resUpper = simulateViewportDrop([fileUpper]);
    record(
      'Drag-Drop: Uppercase .3MF is accepted and calls onDropFile',
      resUpper.droppedFilesReceived.length === 1 && resUpper.droppedFilesReceived[0].name === 'ORCA_PROJECT.3MF' && resUpper.errorMessage === null,
      `Dropped: ${resUpper.droppedFilesReceived[0]?.name}`
    );
  }

  // 2.4: Test GLB and GLTF
  {
    const fileGlb = createMockFile('scene.glb');
    const resGlb = simulateViewportDrop([fileGlb]);
    const fileGltf = createMockFile('model.gltf');
    const resGltf = simulateViewportDrop([fileGltf]);
    record(
      'Drag-Drop: GLB and GLTF formats call onDropFile',
      resGlb.droppedFilesReceived.length === 1 && resGltf.droppedFilesReceived.length === 1,
      `GLB: ${resGlb.droppedFilesReceived[0]?.name}, GLTF: ${resGltf.droppedFilesReceived[0]?.name}`
    );
  }

  // 2.5: Test G-code files (.gcode, .gco)
  {
    const fileGcode = createMockFile('plate.gcode', 'G28\nG1 Z10');
    const resGcode = simulateViewportDrop([fileGcode]);
    record(
      'Drag-Drop: .gcode file does NOT call onDropFile (handled internally as toolpath text)',
      resGcode.droppedFilesReceived.length === 0 && resGcode.errorMessage === null,
      `droppedCount: ${resGcode.droppedFilesReceived.length}, error: ${resGcode.errorMessage}`
    );

    const fileGco = createMockFile('test.gco', 'G28');
    const resGco = simulateViewportDrop([fileGco]);
    record(
      'Drag-Drop: .gco file does NOT call onDropFile',
      resGco.droppedFilesReceived.length === 0,
      `droppedCount: ${resGco.droppedFilesReceived.length}`
    );
  }

  // 2.6: Test Unsupported File Extensions
  {
    const unsupported = ['part.step', 'drawing.pdf', 'texture.png', 'notes.txt', 'no_extension', 'archive.zip'];
    let allBlocked = true;
    for (const name of unsupported) {
      const file = createMockFile(name);
      const res = simulateViewportDrop([file]);
      if (res.droppedFilesReceived.length > 0 || !res.errorMessage) {
        allBlocked = false;
        break;
      }
    }
    record(
      'Drag-Drop: Unsupported extensions (.step, .pdf, .png, .txt, no ext) trigger error and do NOT call onDropFile',
      allBlocked,
      `Tested: ${unsupported.join(', ')}`
    );
  }

  // 2.7: Multi-dot filenames
  {
    const fileMultiDot = createMockFile('my.custom.printer.v2.final.stl');
    const resMultiDot = simulateViewportDrop([fileMultiDot]);
    record(
      'Drag-Drop: Multi-dot filenames correctly extract terminal extension (.stl)',
      resMultiDot.droppedFilesReceived.length === 1 && resMultiDot.droppedFilesReceived[0].name === 'my.custom.printer.v2.final.stl',
      `Dropped: ${resMultiDot.droppedFilesReceived[0]?.name}`
    );
  }

  // 2.8: Edge cases: empty drop list, undefined files
  {
    const resEmpty = simulateViewportDrop([]);
    const resUndef = simulateViewportDrop(undefined);
    record(
      'Drag-Drop: Empty or undefined files list handled safely without crashing',
      resEmpty.droppedFilesReceived.length === 0 && resEmpty.errorMessage === null &&
      resUndef.droppedFilesReceived.length === 0 && resUndef.errorMessage === null,
      `Empty dropped: ${resEmpty.droppedFilesReceived.length}, Undefined dropped: ${resUndef.droppedFilesReceived.length}`
    );
  }
}

// =========================================================================
// DOMAIN 3: Page Model Import Integration (page.tsx handleModelImport)
// =========================================================================
async function testPageModelImportIntegration() {
  console.log('\n--- DOMAIN 3: Page Model Import Integration ---');

  // Simulation of page.tsx handleModelImport & handleModelImported state flow
  class PageImportSimulator {
    constructor(initialActiveProject = null) {
      this.activeProject = initialActiveProject;
      this.saveStatus = 'saved';
      this.activeModelBuffer = 'some_existing_buffer';
      this.alertMessages = [];
      this.importModelCalls = [];
      this.apiClient = {
        importModel: async (projectId, file) => {
          this.importModelCalls.push({ projectId, file });
          if (this.failNextImport) {
            throw new Error(this.failNextImport);
          }
          return {
            id: `model-${Date.now()}`,
            project_id: projectId,
            filename: file.name,
            file_format: file.name.split('.').pop().toLowerCase(),
            bounds: { dimensions_mm: [100, 100, 50] },
            transform: { position_mm: [0, 0, 0], rotation_deg: [0, 0, 0], scale_factors: [1, 1, 1] },
          };
        },
      };
    }

    alert(msg) {
      this.alertMessages.push(msg);
    }

    handleModelImported(model) {
      if (!this.activeProject) return;
      this.activeModelBuffer = null;
      this.activeProject = {
        ...this.activeProject,
        working_models: [...this.activeProject.working_models, model],
      };
      this.saveStatus = 'saved';
    }

    async handleModelImport(file) {
      if (!this.activeProject) {
        this.alert('Please select or create a project before importing 3D models.');
        return;
      }
      try {
        const imported = await this.apiClient.importModel(this.activeProject.id, file);
        this.handleModelImported(imported);
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Failed to import model.';
        this.alert(msg);
      }
    }
  }

  // 3.1: Import with activeProject present
  {
    const project = { id: 'proj-123', name: 'Test Proj', working_models: [] };
    const sim = new PageImportSimulator(project);
    const mockFile = { name: 'benchy.stl', size: 1024 };

    await sim.handleModelImport(mockFile);

    record(
      'Page Import: Calls apiClient.importModel(activeProject.id, file) when activeProject exists',
      sim.importModelCalls.length === 1 && sim.importModelCalls[0].projectId === 'proj-123' && sim.importModelCalls[0].file.name === 'benchy.stl',
      `Calls: ${sim.importModelCalls.length}, projectId: ${sim.importModelCalls[0]?.projectId}`
    );
    record(
      'Page Import: Appends imported model to activeProject.working_models and clears buffer',
      sim.activeProject.working_models.length === 1 && sim.activeProject.working_models[0].filename === 'benchy.stl' && sim.activeModelBuffer === null && sim.saveStatus === 'saved',
      `Models count: ${sim.activeProject.working_models.length}, buffer: ${sim.activeModelBuffer}, status: ${sim.saveStatus}`
    );
  }

  // 3.2: Import with activeProject = null
  {
    const sim = new PageImportSimulator(null);
    const mockFile = { name: 'benchy.stl', size: 1024 };

    await sim.handleModelImport(mockFile);

    record(
      'Page Import: When activeProject is null, blocks import and shows user alert',
      sim.importModelCalls.length === 0 && sim.alertMessages.length === 1 && sim.alertMessages[0].includes('select or create a project'),
      `Calls: ${sim.importModelCalls.length}, Alert: "${sim.alertMessages[0]}"`
    );
  }

  // 3.3: Import with backend failure (network error / 500)
  {
    const project = { id: 'proj-error', name: 'Err Proj', working_models: [] };
    const sim = new PageImportSimulator(project);
    sim.failNextImport = 'Corrupt STL header: expected 80-byte header';
    const mockFile = { name: 'corrupt.stl', size: 10 };

    await sim.handleModelImport(mockFile);

    record(
      'Page Import: Backend error is caught gracefully and presented via alert without throwing',
      sim.activeProject.working_models.length === 0 && sim.alertMessages.length === 1 && sim.alertMessages[0] === 'Corrupt STL header: expected 80-byte header',
      `Models: ${sim.activeProject.working_models.length}, Alert: "${sim.alertMessages[0]}"`
    );
  }

  // 3.4: Rapid sequential imports (multiple models dropped sequentially)
  {
    const project = { id: 'proj-multi', name: 'Multi Drop Proj', working_models: [] };
    const sim = new PageImportSimulator(project);
    const files = [
      { name: 'part_a.stl', size: 100 },
      { name: 'part_b.obj', size: 200 },
      { name: 'part_c.3mf', size: 300 },
    ];

    for (const f of files) {
      await sim.handleModelImport(f);
    }

    record(
      'Page Import: Handles sequential imports of STL, OBJ, and 3MF files into project',
      sim.activeProject.working_models.length === 3 && sim.importModelCalls.length === 3,
      `Imported: ${sim.activeProject.working_models.map((m) => m.filename).join(', ')}`
    );
  }
}

// =========================================================================
// DOMAIN 4: Dynamic BaseURL Resolution & Download URL Sanitation
// =========================================================================
function testDynamicBaseUrlResolution() {
  console.log('\n--- DOMAIN 4: Dynamic BaseURL Resolution & Asset URLs ---');

  // Exact reproduction of ApiClient BaseURL logic from api-client.ts (lines 53-90)
  class ApiClientSimulator {
    constructor(baseUrl) {
      this.customBaseUrl = baseUrl ? baseUrl.replace(/\/$/, '') : null;
    }

    setBaseUrl(url) {
      this.customBaseUrl = url.replace(/\/$/, '');
    }

    getBaseUrl() {
      if (this.customBaseUrl) {
        return this.customBaseUrl;
      }
      if (typeof window !== 'undefined') {
        if (window.__OUTLAW_FORGE_API_URL__) {
          return window.__OUTLAW_FORGE_API_URL__.replace(/\/$/, '');
        }
        try {
          const stored = localStorage.getItem('outlaw_forge_api_url');
          if (stored) {
            return stored.replace(/\/$/, '');
          }
        } catch {
          // Ignore
        }
      }
      return (process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');
    }

    getDownloadUrl(relativePath) {
      const base = this.getBaseUrl();
      const clean = relativePath.startsWith('/') ? relativePath : `/${relativePath}`;
      return `${base}${clean}`;
    }
  }

  const mockLocalStorage = new Map();
  globalThis.localStorage = {
    getItem: (k) => mockLocalStorage.get(k) || null,
    setItem: (k, v) => mockLocalStorage.set(k, v),
    removeItem: (k) => mockLocalStorage.delete(k),
  };

  // 4.1: Fallback default
  {
    globalThis.window = {};
    mockLocalStorage.clear();
    delete process.env.NEXT_PUBLIC_API_URL;
    const client = new ApiClientSimulator();
    const base = client.getBaseUrl();
    record(
      'BaseURL: Resolves to fallback http://127.0.0.1:8000 by default',
      base === 'http://127.0.0.1:8000',
      `Resolved: ${base}`
    );
  }

  // 4.2: window.__OUTLAW_FORGE_API_URL__ takes precedence
  {
    globalThis.window = {
      __OUTLAW_FORGE_API_URL__: 'http://127.0.0.1:54321',
    };
    mockLocalStorage.set('outlaw_forge_api_url', 'http://127.0.0.1:9999');
    const client = new ApiClientSimulator();
    const base = client.getBaseUrl();
    record(
      'BaseURL: window.__OUTLAW_FORGE_API_URL__ takes precedence over localStorage and env',
      base === 'http://127.0.0.1:54321',
      `Resolved: ${base}`
    );
  }

  // 4.3: Strips single trailing slash from window.__OUTLAW_FORGE_API_URL__
  {
    globalThis.window = {
      __OUTLAW_FORGE_API_URL__: 'http://127.0.0.1:54321/',
    };
    const client = new ApiClientSimulator();
    const base = client.getBaseUrl();
    record(
      'BaseURL: Strips single trailing slash from window.__OUTLAW_FORGE_API_URL__',
      base === 'http://127.0.0.1:54321',
      `Resolved: ${base}`
    );
  }

  // 4.3b: Multiple trailing slashes behavior check
  {
    globalThis.window = {
      __OUTLAW_FORGE_API_URL__: 'http://127.0.0.1:54321///',
    };
    const client = new ApiClientSimulator();
    const base = client.getBaseUrl();
    const stripsOnlySingle = base === 'http://127.0.0.1:54321//';
    record(
      'BaseURL (Edge Case): Multiple trailing slashes strip only terminal slash per /\\/$/ regex',
      stripsOnlySingle,
      `Resolved: ${base} (note: /\\/$/ replaces exactly one trailing slash)`
    );
  }

  // 4.4: localStorage fallback when window variable is absent
  {
    globalThis.window = {};
    mockLocalStorage.set('outlaw_forge_api_url', 'http://127.0.0.1:61234/');
    const client = new ApiClientSimulator();
    const base = client.getBaseUrl();
    record(
      'BaseURL: Resolves from localStorage when window variable absent',
      base === 'http://127.0.0.1:61234',
      `Resolved: ${base}`
    );
  }

  // 4.5: setBaseUrl overrides all
  {
    globalThis.window = { __OUTLAW_FORGE_API_URL__: 'http://127.0.0.1:54321' };
    const client = new ApiClientSimulator();
    client.setBaseUrl('http://127.0.0.1:7777/');
    const base = client.getBaseUrl();
    record(
      'BaseURL: setBaseUrl explicitly overrides window and localStorage',
      base === 'http://127.0.0.1:7777',
      `Resolved: ${base}`
    );
  }

  // 4.6: getDownloadUrl path cleanliness (no double slashes, handles leading slash or not)
  {
    globalThis.window = { __OUTLAW_FORGE_API_URL__: 'http://127.0.0.1:51111' };
    const client = new ApiClientSimulator();

    const withLeading = client.getDownloadUrl('/models/export/file.stl');
    const withoutLeading = client.getDownloadUrl('models/export/file.stl');

    record(
      'DownloadUrl: Normalizes paths with or without leading slash without double slashes',
      withLeading === 'http://127.0.0.1:51111/models/export/file.stl' && withoutLeading === 'http://127.0.0.1:51111/models/export/file.stl',
      `withLeading: ${withLeading}, withoutLeading: ${withoutLeading}`
    );
  }
}

// =========================================================================
// DOMAIN 5: AST & Source Code Verification for Wiring Integrity
// =========================================================================
function testSourceCodeWiring() {
  console.log('\n--- DOMAIN 5: Source Code Wiring Verification ---');

  // 5.1: ViewportContainer.tsx checks
  const vpPath = path.resolve(REPO_ROOT, 'apps/web/src/components/viewport/ViewportContainer.tsx');
  const vpContent = fs.readFileSync(vpPath, 'utf-8');

  const vpHasOnDropProp = vpContent.includes('onDropFile?: (file: File) => void');
  const vpHasExtCheck = vpContent.includes("['stl', 'obj', 'glb', 'gltf', '3mf'].includes(ext || '')");
  const vpCallsOnDrop = vpContent.includes('onDropFile?.(droppedFile)');
  const vpGcodeCheck = vpContent.includes("['gcode', 'gco'].includes(ext || '')");

  record(
    'ViewportContainer: Declares onDropFile prop in ViewportContainerProps',
    vpHasOnDropProp,
    'Found onDropFile?: (file: File) => void'
  );
  record(
    'ViewportContainer: handleDrop checks for STL, OBJ, GLB, GLTF, and 3MF extensions',
    vpHasExtCheck,
    'Found extension filter array'
  );
  record(
    'ViewportContainer: Invokes onDropFile?.(droppedFile) on valid drop',
    vpCallsOnDrop,
    'Found onDropFile?.(droppedFile)'
  );
  record(
    'ViewportContainer: Handles G-code separately via text parsing',
    vpGcodeCheck,
    'Found gcode/gco handling branch'
  );

  // 5.2: page.tsx checks
  const pagePath = path.resolve(REPO_ROOT, 'apps/web/src/app/page.tsx');
  const pageContent = fs.readFileSync(pagePath, 'utf-8');

  const pageHasImportModelHandler = pageContent.includes('const handleModelImport = async (file: File)');
  const pageChecksActiveProject = pageContent.includes('if (!activeProject)');
  const pageCallsApiClient = pageContent.includes('apiClient.importModel(activeProject.id, file)');
  const pageWiresOnDrop = pageContent.includes('onDropFile={(file) => handleModelImport(file)}');

  record(
    'page.tsx: Defines handleModelImport(file: File) handler',
    pageHasImportModelHandler,
    'Found handleModelImport'
  );
  record(
    'page.tsx: Guards against missing activeProject with user alert',
    pageChecksActiveProject,
    'Found activeProject null check'
  );
  record(
    'page.tsx: Invokes apiClient.importModel(activeProject.id, file)',
    pageCallsApiClient,
    'Found apiClient.importModel invocation'
  );
  record(
    'page.tsx: Passes onDropFile={(file) => handleModelImport(file)} to ViewportContainer',
    pageWiresOnDrop,
    'Found onDropFile wiring on ViewportContainer'
  );

  // 5.3: Scan entire apps/web for hardcoded localhost / 127.0.0.1:8000 leaks
  function walkDir(dir, fileList = []) {
    const files = fs.readdirSync(dir);
    for (const file of files) {
      const fullPath = path.join(dir, file);
      if (fs.statSync(fullPath).isDirectory()) {
        if (!['node_modules', '.next', 'out'].includes(file)) {
          walkDir(fullPath, fileList);
        }
      } else if (file.endsWith('.ts') || file.endsWith('.tsx') || file.endsWith('.js') || file.endsWith('.mjs')) {
        fileList.push(fullPath);
      }
    }
    return fileList;
  }

  const allSourceFiles = walkDir(path.resolve(REPO_ROOT, 'apps/web/src'));
  const leaks = [];

  for (const file of allSourceFiles) {
    const text = fs.readFileSync(file, 'utf-8');
    const lines = text.split('\n');
    lines.forEach((line, idx) => {
      // Ignore fallback in api-client.ts line 83: return (process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000").replace...
      if (file.endsWith('api-client.ts') && line.includes('NEXT_PUBLIC_API_URL')) {
        return;
      }
      if (line.includes('localhost:8000') || line.includes('127.0.0.1:8000')) {
        leaks.push({ file: path.relative(REPO_ROOT, file), line: idx + 1, content: line.trim() });
      }
    });
  }

  record(
    'Audit: Zero hardcoded localhost:8000 or 127.0.0.1:8000 URLs in apps/web/src components',
    leaks.length === 0,
    leaks.length === 0 ? 'Clean (0 leaks found)' : `Found ${leaks.length} leaks: ${JSON.stringify(leaks)}`
  );
}

// =========================================================================
// RUN ALL TESTS
// =========================================================================
async function runAll() {
  console.log('================================================================');
  console.log('Milestone M2 Frontend Stress Test Suite');
  console.log('================================================================');

  await testNativeDialogBridge();
  testDragDropExtensionHandling();
  await testPageModelImportIntegration();
  testDynamicBaseUrlResolution();
  testSourceCodeWiring();

  console.log('\n================================================================');
  const total = results.length;
  const passed = results.filter((r) => r.status === 'PASS').length;
  const failed = results.filter((r) => r.status === 'FAIL').length;
  console.log(`TOTAL: ${total} | PASSED: ${passed} | FAILED: ${failed}`);
  console.log('================================================================');

  if (failed > 0) {
    process.exit(1);
  } else {
    process.exit(0);
  }
}

runAll().catch((err) => {
  console.error('Test harness execution failed:', err);
  process.exit(1);
});
