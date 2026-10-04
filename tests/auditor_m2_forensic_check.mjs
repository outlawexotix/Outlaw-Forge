/**
 * Independent Forensic Verification Harness by teamwork_preview_auditor_m2_1
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');

let totalTests = 0;
let passedTests = 0;
let failedTests = 0;

function assert(condition, message) {
  totalTests++;
  if (condition) {
    passedTests++;
    console.log(`[PASS] ${message}`);
  } else {
    failedTests++;
    console.error(`[FAIL] ${message}`);
  }
}

async function runAudit() {
  console.log('--- 1. AUDIT next.config.mjs ---');
  const nextConfigPath = path.resolve(ROOT, 'apps/web/next.config.mjs');
  const nextConfigContent = fs.readFileSync(nextConfigPath, 'utf8');

  // Verify next.config.mjs logic without relying on external cache
  assert(nextConfigContent.includes("process.env.OUTPUT_EXPORT === 'true'"), 'Checks OUTPUT_EXPORT');
  assert(nextConfigContent.includes("process.env.STATIC_EXPORT === 'true'"), 'Checks STATIC_EXPORT');
  assert(nextConfigContent.includes("process.env.TAURI_ENV_PLATFORM !== undefined"), 'Checks TAURI_ENV_PLATFORM');
  assert(nextConfigContent.includes("output: 'export'"), 'Sets output: export');
  assert(nextConfigContent.includes("unoptimized: true"), 'Disables image optimization for static export');

  // Dynamically test next.config.mjs export in different env conditions
  // Condition A: Standard web (no static export env)
  delete process.env.OUTPUT_EXPORT;
  delete process.env.STATIC_EXPORT;
  delete process.env.TAURI_ENV_PLATFORM;
  const modWeb = await import(`file://${nextConfigPath.replace(/\\/g, '/')}?t=${Date.now()}_web`);
  const configWeb = modWeb.default;
  assert(configWeb.output === undefined, 'Web mode: output is undefined (standard Next.js server)');
  assert(typeof configWeb.rewrites === 'function', 'Web mode: rewrites is a function');
  const rewritesList = await configWeb.rewrites();
  assert(Array.isArray(rewritesList) && rewritesList.length === 5, `Web mode: rewrites has 5 routes (found ${rewritesList.length})`);

  // Condition B: Static export mode (OUTPUT_EXPORT=true)
  process.env.OUTPUT_EXPORT = 'true';
  const modExport = await import(`file://${nextConfigPath.replace(/\\/g, '/')}?t=${Date.now()}_export`);
  const configExport = modExport.default;
  assert(configExport.output === 'export', 'Export mode: output is "export"');
  assert(configExport.rewrites === undefined, 'Export mode: rewrites is undefined (no conflict)');
  assert(configExport.images?.unoptimized === true, 'Export mode: images.unoptimized is true');
  delete process.env.OUTPUT_EXPORT;

  // Condition C: Tauri platform export mode (TAURI_ENV_PLATFORM=windows)
  process.env.TAURI_ENV_PLATFORM = 'windows';
  const modTauri = await import(`file://${nextConfigPath.replace(/\\/g, '/')}?t=${Date.now()}_tauri`);
  const configTauri = modTauri.default;
  assert(configTauri.output === 'export', 'Tauri mode: output is "export"');
  assert(configTauri.rewrites === undefined, 'Tauri mode: rewrites is undefined');
  delete process.env.TAURI_ENV_PLATFORM;

  console.log('\n--- 2. AUDIT api-client.ts ---');
  const apiClientPath = path.resolve(ROOT, 'apps/web/src/lib/api-client.ts');
  const apiClientContent = fs.readFileSync(apiClientPath, 'utf8');

  // Check that this.baseUrl is never called directly for fetches
  const leakedThisBaseUrl = (apiClientContent.match(/\$\{this\.baseUrl\}/g) || []).length;
  assert(leakedThisBaseUrl === 0, `No remaining \${this.baseUrl} calls (found: ${leakedThisBaseUrl})`);

  const dynamicCallsCount = (apiClientContent.match(/\$\{this\.getBaseUrl\(\)\}/g) || []).length;
  assert(dynamicCallsCount >= 34, `All API methods use \${this.getBaseUrl()} (found: ${dynamicCallsCount})`);

  // Check Window interface augmentation
  assert(apiClientContent.includes('interface Window {'), 'Declares Window interface augmentation');
  assert(apiClientContent.includes('__OUTLAW_FORGE_API_URL__?: string'), 'Declares __OUTLAW_FORGE_API_URL__ property');

  // Check getBaseUrl resolution priority
  assert(apiClientContent.includes('if (this.customBaseUrl)'), 'Checks customBaseUrl first');
  assert(apiClientContent.includes('window.__OUTLAW_FORGE_API_URL__'), 'Checks window.__OUTLAW_FORGE_API_URL__ second');
  assert(apiClientContent.includes('localStorage.getItem("outlaw_forge_api_url")'), 'Checks localStorage third');
  assert(apiClientContent.includes('process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000"'), 'Falls back to env or 127.0.0.1:8000');

  // Check getDownloadUrl
  assert(apiClientContent.includes('getDownloadUrl(relativePath: string)'), 'Implements getDownloadUrl');

  console.log('\n--- 3. AUDIT native-dialog.ts ---');
  const nativeDialogPath = path.resolve(ROOT, 'apps/web/src/lib/native-dialog.ts');
  const nativeDialogContent = fs.readFileSync(nativeDialogPath, 'utf8');

  assert(nativeDialogContent.includes('export function isTauri()'), 'Exports isTauri()');
  assert(nativeDialogContent.includes('export async function openNativeFileDialog'), 'Exports openNativeFileDialog');
  assert(nativeDialogContent.includes('export async function saveNativeFileDialog'), 'Exports saveNativeFileDialog');
  assert(nativeDialogContent.includes('export function openBrowserFileDialog'), 'Exports openBrowserFileDialog');
  assert(nativeDialogContent.includes('export function downloadInBrowser'), 'Exports downloadInBrowser');
  assert(nativeDialogContent.includes('export async function saveFileWithFallback'), 'Exports saveFileWithFallback');

  // Test dynamic import safety
  assert(nativeDialogContent.includes("new Function('specifier', 'return import(specifier)')"), 'Uses dynamic runtime import to prevent bundler resolution failure');

  console.log('\n--- 4. AUDIT ModelRenderer.tsx & Inspector.tsx & page.tsx ---');
  const modelRendererPath = path.resolve(ROOT, 'apps/web/src/components/viewport/ModelRenderer.tsx');
  const modelRendererContent = fs.readFileSync(modelRendererPath, 'utf8');
  assert(modelRendererContent.includes('apiClient.getBaseUrl()'), 'ModelRenderer uses apiClient.getBaseUrl()');
  assert(!modelRendererContent.includes("process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'"), 'ModelRenderer removed hardcoded localhost:8000 fallback');

  const inspectorPath = path.resolve(ROOT, 'apps/web/src/components/layout/Inspector.tsx');
  const inspectorContent = fs.readFileSync(inspectorPath, 'utf8');
  assert(!inspectorContent.includes('http://localhost:8000'), 'Inspector has no hardcoded http://localhost:8000');
  assert(inspectorContent.includes('apiClient.getDownloadUrl(exportDownloadUrl)'), 'Inspector uses apiClient.getDownloadUrl for model export');
  assert(inspectorContent.includes('apiClient.getDownloadUrl(export3MFResult.download_url)'), 'Inspector uses apiClient.getDownloadUrl for 3MF container');

  const pagePath = path.resolve(ROOT, 'apps/web/src/app/page.tsx');
  const pageContent = fs.readFileSync(pagePath, 'utf8');
  assert(pageContent.includes('handleModelImport'), 'page.tsx implements handleModelImport');
  assert(pageContent.includes('apiClient.importModel(activeProject.id, file)'), 'page.tsx calls apiClient.importModel');
  assert(pageContent.includes('onDropFile={(file) => handleModelImport(file)}'), 'page.tsx connects onDropFile to handleModelImport');

  console.log('\n--- 5. SCAN FOR HARDCODED API URLS IN FRONTEND COMPONENTS ---');
  const componentsDir = path.resolve(ROOT, 'apps/web/src/components');
  let hardcodedMatches = [];
  function scanDir(dir) {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const fullPath = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        scanDir(fullPath);
      } else if (entry.isFile() && (entry.name.endsWith('.tsx') || entry.name.endsWith('.ts'))) {
        const text = fs.readFileSync(fullPath, 'utf8');
        const lines = text.split('\n');
        lines.forEach((line, idx) => {
          if (line.includes('http://localhost:8000') || line.includes('http://127.0.0.1:8000')) {
            hardcodedMatches.push({ file: fullPath, line: idx + 1, text: line.trim() });
          }
        });
      }
    }
  }
  scanDir(componentsDir);
  assert(hardcodedMatches.length === 0, `No hardcoded backend URLs in components (found ${hardcodedMatches.length})`);
  if (hardcodedMatches.length > 0) {
    console.error('Hardcoded matches:', hardcodedMatches);
  }

  console.log('\n--- 6. ANTI-SLOP CHECK: EM-DASHES & EN-DASHES ---');
  // AGENTS.md rule: "Never emit em-dashes (—) or separator en-dashes (–) in user-visible UI copy. Use hyphens -, colons, or clean phrasing."
  const filesToCheck = [
    modelRendererPath,
    inspectorPath,
    pagePath,
    nativeDialogPath,
    path.resolve(ROOT, 'apps/web/src/components/viewport/ViewportContainer.tsx'),
  ];
  let dashViolations = [];
  for (const f of filesToCheck) {
    const text = fs.readFileSync(f, 'utf8');
    const lines = text.split('\n');
    lines.forEach((line, idx) => {
      // Check for em-dash (—) or en-dash (–)
      if (line.includes('—') || line.includes('–')) {
        dashViolations.push({ file: path.basename(f), line: idx + 1, text: line.trim() });
      }
    });
  }
  // Note: some comments or existing code might have em-dashes, let's inspect any found
  console.log(`Dash scan in audited files found ${dashViolations.length} occurrences.`);
  dashViolations.forEach(v => console.log(`  [${v.file}:${v.line}] ${v.text}`));

  console.log(`\n========================================`);
  console.log(`AUDIT RESULTS: ${passedTests} passed, ${failedTests} failed out of ${totalTests} checks`);
  console.log(`========================================`);

  if (failedTests > 0) {
    process.exit(1);
  }
}

runAudit().catch(err => {
  console.error('Audit run failed with error:', err);
  process.exit(1);
});
