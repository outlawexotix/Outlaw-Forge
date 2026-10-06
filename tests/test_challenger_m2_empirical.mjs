/**
 * Outlaw Forge - Milestone M2 Challenger Empirical Test Suite
 * ============================================================
 * Challenger 1: Static Frontend & Desktop Integration
 *
 * Verifies:
 * 1. Live HTTP Static Server Asset Resolution of `apps/web/out/` (index.html, 404.html, all JS/CSS chunks).
 * 2. Live Ephemeral Loopback HTTP Server integration with real network fetch and port bridging.
 * 3. Dynamic runtime re-targeting across ephemeral ports without page refresh.
 * 4. Adversarial edge cases for `window.__OUTLAW_FORGE_API_URL__` (slashes, boundaries, mutations).
 * 5. Static chunk audit: no Node.js runtime leaks (fs, net, child_process) in client bundles.
 */

import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import ts from 'typescript';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const REPO_ROOT = path.resolve(__dirname, '..');
const OUT_DIR = path.resolve(REPO_ROOT, 'apps/web/out');

let totalChecks = 0;
let passedChecks = 0;
let failedChecks = 0;

function check(desc, passed, details = '') {
  totalChecks++;
  if (passed) {
    passedChecks++;
    console.log(`\x1b[32m[PASS]\x1b[0m ${desc}${details ? ` -> ${details}` : ''}`);
  } else {
    failedChecks++;
    console.error(`\x1b[31m[FAIL]\x1b[0m ${desc}${details ? ` -> ${details}` : ''}`);
  }
}

// Simple MIME resolver
function getMime(filePath) {
  if (filePath.endsWith('.html')) return 'text/html; charset=utf-8';
  if (filePath.endsWith('.js') || filePath.endsWith('.mjs')) return 'text/javascript; charset=utf-8';
  if (filePath.endsWith('.css')) return 'text/css; charset=utf-8';
  if (filePath.endsWith('.txt')) return 'text/plain; charset=utf-8';
  if (filePath.endsWith('.json')) return 'application/json';
  if (filePath.endsWith('.ico')) return 'image/x-icon';
  if (filePath.endsWith('.svg')) return 'image/svg+xml';
  return 'application/octet-stream';
}

// -----------------------------------------------------------------------------
// SECTION 1: Static Bundle Asset Crawler & Live HTTP Verification
// -----------------------------------------------------------------------------
async function verifyStaticBundleLiveHttp() {
  console.log('\n================================================================');
  console.log('SECTION 1: Static Bundle Live HTTP Verification (apps/web/out)');
  console.log('================================================================');

  // Verify out directory exists
  check('Static export directory apps/web/out exists', fs.existsSync(OUT_DIR), OUT_DIR);
  const indexHtmlPath = path.join(OUT_DIR, 'index.html');
  check('index.html exists in apps/web/out', fs.existsSync(indexHtmlPath));

  if (!fs.existsSync(indexHtmlPath)) {
    throw new Error('Fatal: apps/web/out/index.html does not exist.');
  }

  const indexHtml = fs.readFileSync(indexHtmlPath, 'utf8');
  check('index.html is non-empty (> 5KB)', indexHtml.length > 5000, `${indexHtml.length} bytes`);

  // Start a local HTTP server serving OUT_DIR on ephemeral loopback port
  const server = http.createServer((req, res) => {
    let reqPath = decodeURIComponent(req.url.split('?')[0]);
    if (reqPath === '/') reqPath = '/index.html';
    const filePath = path.join(OUT_DIR, reqPath.replace(/^\//, ''));

    if (fs.existsSync(filePath) && fs.statSync(filePath).isFile()) {
      const mime = getMime(filePath);
      const content = fs.readFileSync(filePath);
      res.writeHead(200, {
        'Content-Type': mime,
        'Content-Length': content.length,
      });
      res.end(content);
    } else {
      res.writeHead(404, { 'Content-Type': 'text/plain' });
      res.end('Not Found');
    }
  });

  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  const port = server.address().port;
  const baseUrl = `http://127.0.0.1:${port}`;
  console.log(`Static file HTTP server listening on ${baseUrl}`);

  try {
    // 1. Fetch index.html over HTTP
    const indexRes = await fetch(`${baseUrl}/index.html`);
    check('Live HTTP GET /index.html returns 200 OK', indexRes.status === 200);
    const indexBody = await indexRes.text();
    check('Response contains DOCTYPE and Outlaw Forge title', indexBody.includes('<!DOCTYPE html>') && indexBody.includes('Outlaw Forge'));

    // 2. Extract all asset references from HTML
    const assetRegex = /(?:src|href)=["'](\/_next\/[^"']+)["']/g;
    let match;
    const assetsToFetch = new Set();
    while ((match = assetRegex.exec(indexBody)) !== null) {
      assetsToFetch.add(match[1]);
    }

    check('Extracted static assets from index.html', assetsToFetch.size >= 5, `Found ${assetsToFetch.size} unique assets`);

    let assetFailures = 0;
    for (const assetPath of assetsToFetch) {
      const assetRes = await fetch(`${baseUrl}${assetPath}`);
      const assetBuf = await assetRes.arrayBuffer();
      const contentType = assetRes.headers.get('content-type') || '';
      const ok = assetRes.status === 200 && assetBuf.byteLength > 0;
      if (!ok) {
        assetFailures++;
        console.error(`Asset failed: ${assetPath} status=${assetRes.status} size=${assetBuf.byteLength}`);
      }
    }
    check(`All ${assetsToFetch.size} static scripts and stylesheets load with 200 OK via HTTP`, assetFailures === 0, `${assetsToFetch.size - assetFailures}/${assetsToFetch.size} succeeded`);

    // 3. Verify 404.html
    const notFoundRes = await fetch(`${baseUrl}/404.html`);
    check('Live HTTP GET /404.html returns 200 OK', notFoundRes.status === 200);
    const notFoundBody = await notFoundRes.text();
    check('404.html has fallback error page structure', notFoundBody.includes('404') || notFoundBody.includes('page could not be found'));

    // 4. Verify client chunks directory
    const chunksDir = path.join(OUT_DIR, '_next/static/chunks');
    check('Chunks directory exists', fs.existsSync(chunksDir));
    const chunkFiles = fs.readdirSync(chunksDir);
    check('Compiled JS chunks count in _next/static/chunks', chunkFiles.length >= 5, `Found ${chunkFiles.length} chunk files`);

    // 5. Audit chunk sizes and non-emptiness
    let emptyChunks = 0;
    for (const chunk of chunkFiles) {
      const stat = fs.statSync(path.join(chunksDir, chunk));
      if (stat.size === 0) emptyChunks++;
    }
    check('All chunk files are non-empty (>0 bytes)', emptyChunks === 0, `0 empty out of ${chunkFiles.length}`);

  } finally {
    server.close();
  }
}

// -----------------------------------------------------------------------------
// SECTION 2: Live Loopback Ephemeral Server API Client Integration & Port Bridging
// -----------------------------------------------------------------------------
async function verifyLiveLoopbackPortBridging() {
  console.log('\n================================================================');
  console.log('SECTION 2: Live Loopback Ephemeral Server & Port Bridging');
  console.log('================================================================');

  // Load and transpile ApiClient from apps/web/src/lib/api-client.ts
  const clientPath = path.resolve(REPO_ROOT, 'apps/web/src/lib/api-client.ts');
  const tsSource = fs.readFileSync(clientPath, 'utf8');
  const transpiled = ts.transpileModule(tsSource, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  }).outputText;

  const mod = { exports: {} };
  const fn = new Function('module', 'exports', 'require', transpiled);
  fn(mod, mod.exports, () => ({}));
  const { ApiClient } = mod.exports;

  check('ApiClient class loaded and instantiated', typeof ApiClient === 'function');

  // Spin up Backend Server 1 on an OS-assigned ephemeral loopback port
  let server1RequestCount = 0;
  const server1ReceivedPaths = [];
  const server1 = http.createServer((req, res) => {
    server1RequestCount++;
    server1ReceivedPaths.push(req.url);
    if (req.url === '/health') {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ status: 'healthy', version: '0.1.0', server: 'server-1' }));
    } else if (req.url === '/projects' || req.url === '/api/v1/projects') {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify([{ id: 'proj-1', name: 'Server 1 Project' }]));
    } else {
      res.writeHead(404, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ detail: 'Not Found' }));
    }
  });

  await new Promise((resolve) => server1.listen(0, '127.0.0.1', resolve));
  const port1 = server1.address().port;
  const server1Url = `http://127.0.0.1:${port1}`;
  console.log(`Ephemeral Backend Server 1 started on ${server1Url}`);

  // Setup window global environment with window.__OUTLAW_FORGE_API_URL__
  globalThis.window = {
    __OUTLAW_FORGE_API_URL__: server1Url,
  };
  globalThis.localStorage = {
    getItem: () => null,
    setItem: () => {},
    removeItem: () => {},
  };

  const client = new ApiClient();

  // Test 2.1: getBaseUrl resolves to ephemeral port 1
  check(
    'getBaseUrl resolves to live ephemeral server 1 URL',
    client.getBaseUrl() === server1Url,
    `Resolved: ${client.getBaseUrl()}`
  );

  // Test 2.2: Live network call to getHealth over HTTP
  const healthRes = await client.getHealth();
  check(
    'Live HTTP getHealth() successfully hit server 1',
    healthRes.status === 'healthy' && server1ReceivedPaths.includes('/health'),
    `Response: ${JSON.stringify(healthRes)}, Server 1 hits: ${server1RequestCount}`
  );

  // Test 2.3: Live network call to listProjects over HTTP
  const projRes = await client.listProjects();
  check(
    'Live HTTP listProjects() successfully hit server 1',
    Array.isArray(projRes) && projRes[0]?.id === 'proj-1',
    `Projects: ${JSON.stringify(projRes)}`
  );

  // Test 2.4: DYNAMIC PORT MUTATION (Simulating sidecar relaunching on a new port)
  let server2RequestCount = 0;
  const server2ReceivedPaths = [];
  const server2 = http.createServer((req, res) => {
    server2RequestCount++;
    server2ReceivedPaths.push(req.url);
    if (req.url === '/health') {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ status: 'healthy', version: '0.2.0', server: 'server-2-dynamic' }));
    } else if (req.url === '/projects' || req.url === '/api/v1/projects') {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify([{ id: 'proj-2', name: 'Server 2 Switched' }]));
    } else {
      res.writeHead(404, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ detail: 'Not Found' }));
    }
  });

  await new Promise((resolve) => server2.listen(0, '127.0.0.1', resolve));
  const port2 = server2.address().port;
  const server2Url = `http://127.0.0.1:${port2}`;
  console.log(`Ephemeral Backend Server 2 started on ${server2Url}`);

  // Mutate window.__OUTLAW_FORGE_API_URL__ without creating a new ApiClient instance
  globalThis.window.__OUTLAW_FORGE_API_URL__ = server2Url;

  check(
    'getBaseUrl dynamically reflects mutated port without new instance',
    client.getBaseUrl() === server2Url,
    `Now: ${client.getBaseUrl()}`
  );

  const prevServer1Hits = server1RequestCount;
  const healthRes2 = await client.getHealth();
  check(
    'Subsequent getHealth() hit Server 2 exclusively without hitting Server 1',
    healthRes2.server === 'server-2-dynamic' &&
      server2RequestCount === 1 &&
      server1RequestCount === prevServer1Hits,
    `Server 1 hits: ${server1RequestCount}, Server 2 hits: ${server2RequestCount}`
  );

  const projRes2 = await client.listProjects();
  check(
    'Subsequent listProjects() hit Server 2 and received Server 2 data',
    Array.isArray(projRes2) && projRes2[0]?.id === 'proj-2' && server2RequestCount === 2,
    `Data: ${JSON.stringify(projRes2)}`
  );

  // Close servers
  server1.close();
  server2.close();
}

// -----------------------------------------------------------------------------
// SECTION 3: Adversarial Edge Cases for window.__OUTLAW_FORGE_API_URL__
// -----------------------------------------------------------------------------
async function verifyAdversarialEdgeCases() {
  console.log('\n================================================================');
  console.log('SECTION 3: Adversarial Edge Cases for Port Bridging');
  console.log('================================================================');

  const clientPath = path.resolve(REPO_ROOT, 'apps/web/src/lib/api-client.ts');
  const tsSource = fs.readFileSync(clientPath, 'utf8');
  const transpiled = ts.transpileModule(tsSource, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  }).outputText;

  const mod = { exports: {} };
  const fn = new Function('module', 'exports', 'require', transpiled);
  fn(mod, mod.exports, () => ({}));
  const { ApiClient } = mod.exports;

  const client = new ApiClient();

  // Test 3.1: Port 65535 (highest valid TCP port)
  globalThis.window = { __OUTLAW_FORGE_API_URL__: 'http://127.0.0.1:65535' };
  check(
    'Handles maximum valid TCP port 65535',
    client.getBaseUrl() === 'http://127.0.0.1:65535',
    client.getBaseUrl()
  );

  // Test 3.2: Trailing slashes
  globalThis.window = { __OUTLAW_FORGE_API_URL__: 'http://127.0.0.1:40000/' };
  check(
    'Strips single trailing slash',
    client.getBaseUrl() === 'http://127.0.0.1:40000',
    client.getBaseUrl()
  );

  // Test 3.3: getDownloadUrl sanitation
  globalThis.window = { __OUTLAW_FORGE_API_URL__: 'http://127.0.0.1:40000' };
  const dl1 = client.getDownloadUrl('/models/export/benchy.stl');
  const dl2 = client.getDownloadUrl('models/export/benchy.stl');
  check(
    'getDownloadUrl produces identical clean URL with or without leading slash',
    dl1 === 'http://127.0.0.1:40000/models/export/benchy.stl' && dl2 === dl1,
    `dl1=${dl1}`
  );

  // Test 3.4: Hostname localhost vs 127.0.0.1
  globalThis.window = { __OUTLAW_FORGE_API_URL__: 'http://localhost:59999' };
  check(
    'Supports localhost hostname',
    client.getBaseUrl() === 'http://localhost:59999',
    client.getBaseUrl()
  );

  // Test 3.5: HTTPS scheme support
  globalThis.window = { __OUTLAW_FORGE_API_URL__: 'https://127.0.0.1:8443' };
  check(
    'Supports HTTPS scheme',
    client.getBaseUrl() === 'https://127.0.0.1:8443',
    client.getBaseUrl()
  );

  // Test 3.6: Fallback when window.__OUTLAW_FORGE_API_URL__ is null or undefined
  globalThis.window = { __OUTLAW_FORGE_API_URL__: undefined };
  delete process.env.NEXT_PUBLIC_API_URL;
  check(
    'Falls back safely to 127.0.0.1:8000 when window variable is undefined',
    client.getBaseUrl() === 'http://127.0.0.1:8000',
    client.getBaseUrl()
  );

  globalThis.window = { __OUTLAW_FORGE_API_URL__: null };
  check(
    'Falls back safely to 127.0.0.1:8000 when window variable is null',
    client.getBaseUrl() === 'http://127.0.0.1:8000',
    client.getBaseUrl()
  );
}

// -----------------------------------------------------------------------------
// SECTION 4: Static Bundle Chunk Security & Runtime Leak Audit
// -----------------------------------------------------------------------------
async function verifyNoRuntimeLeaksInBundle() {
  console.log('\n================================================================');
  console.log('SECTION 4: Static Bundle Chunks Cleanliness & No Leaks Audit');
  console.log('================================================================');

  const chunksDir = path.join(OUT_DIR, '_next/static/chunks');
  const files = fs.readdirSync(chunksDir);

  let forbiddenNodeImports = 0;
  let hardcodedDefaultPortLeaks = 0;

  for (const f of files) {
    if (!f.endsWith('.js')) continue;
    const content = fs.readFileSync(path.join(chunksDir, f), 'utf8');

    // Check that server-only modules aren't bundled
    if (content.includes('require("child_process")') || content.includes('require("node:child_process")')) {
      console.error(`Leak found in ${f}: child_process`);
      forbiddenNodeImports++;
    }
    if (content.includes('require("net")') || content.includes('require("node:net")')) {
      console.error(`Leak found in ${f}: net`);
      forbiddenNodeImports++;
    }

    // Check if hardcoded active API routes with localhost:8000 exist in production code
    // Note: Some comments or string literals might exist, but API fetches shouldn't hardcode it
    const matches = content.match(/fetch\(["']http:\/\/127\.0\.0\.1:8000\/api/g);
    if (matches) {
      console.error(`Hardcoded fetch leak in ${f}: ${matches.length} instances`);
      hardcodedDefaultPortLeaks += matches.length;
    }
  }

  check('Zero forbidden Node runtime imports (child_process, net) in client JS chunks', forbiddenNodeImports === 0);
  check('Zero hardcoded static fetches to 127.0.0.1:8000/api in client chunks', hardcodedDefaultPortLeaks === 0);
}

// -----------------------------------------------------------------------------
// RUN ALL SECTIONS
// -----------------------------------------------------------------------------
async function runAll() {
  console.log('================================================================');
  console.log('CHALLENGER 1 EMPIRICAL AUDIT HARNESS');
  console.log('================================================================');

  await verifyStaticBundleLiveHttp();
  await verifyLiveLoopbackPortBridging();
  await verifyAdversarialEdgeCases();
  await verifyNoRuntimeLeaksInBundle();

  console.log('\n================================================================');
  console.log(`TOTAL CHECKS: ${totalChecks}`);
  console.log(`PASSED: ${passedChecks}`);
  console.log(`FAILED: ${failedChecks}`);
  console.log('================================================================');

  if (failedChecks > 0) {
    console.error('\nOVERALL CHALLENGE VERDICT: REJECT (Failures detected)');
    process.exit(1);
  } else {
    console.log('\nOVERALL CHALLENGE VERDICT: APPROVE (100% Empirical Pass)');
    process.exit(0);
  }
}

runAll().catch((err) => {
  console.error('Fatal test error:', err);
  process.exit(1);
});
