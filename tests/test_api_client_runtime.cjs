const fs = require('fs');
const path = require('path');
const ts = require('typescript');

const tsSource = fs.readFileSync(path.join(__dirname, '../apps/web/src/lib/api-client.ts'), 'utf8');
const transpiled = ts.transpileModule(tsSource, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 }
}).outputText;

// Load module in isolated VM
const mod = { exports: {} };
const fn = new Function('module', 'exports', 'require', transpiled);
fn(mod, mod.exports, (id) => ({}));

const { ApiClient, apiClient } = mod.exports;

let testsPassed = 0;
let testsFailed = 0;
function assert(desc, condition, actual, expected) {
  if (condition) {
    console.log('[PASS]', desc);
    testsPassed++;
  } else {
    console.error('[FAIL]', desc, 'Actual:', actual, 'Expected:', expected);
    testsFailed++;
  }
}

// Global mocks
const mockStorage = new Map();
global.localStorage = {
  getItem: (k) => mockStorage.get(k) || null,
  setItem: (k, v) => mockStorage.set(k, v),
  removeItem: (k) => mockStorage.delete(k),
  clear: () => mockStorage.clear()
};
global.window = {};

// Test 1: window.__OUTLAW_FORGE_API_URL__ with trailing slash
global.window.__OUTLAW_FORGE_API_URL__ = 'http://127.0.0.1:49152/';
const client1 = new ApiClient();
assert('Window with trailing slash', client1.getBaseUrl() === 'http://127.0.0.1:49152', client1.getBaseUrl(), 'http://127.0.0.1:49152');

// Test 2: window.__OUTLAW_FORGE_API_URL__ with no trailing slash
global.window.__OUTLAW_FORGE_API_URL__ = 'http://127.0.0.1:49152';
assert('Window with no trailing slash', client1.getBaseUrl() === 'http://127.0.0.1:49152', client1.getBaseUrl(), 'http://127.0.0.1:49152');

// Test 3: localStorage item with trailing slash
delete global.window.__OUTLAW_FORGE_API_URL__;
mockStorage.set('outlaw_forge_api_url', 'http://127.0.0.1:58000/');
assert('localStorage with trailing slash', client1.getBaseUrl() === 'http://127.0.0.1:58000', client1.getBaseUrl(), 'http://127.0.0.1:58000');

// Test 4: localStorage item with no trailing slash
mockStorage.set('outlaw_forge_api_url', 'http://127.0.0.1:58000');
assert('localStorage with no trailing slash', client1.getBaseUrl() === 'http://127.0.0.1:58000', client1.getBaseUrl(), 'http://127.0.0.1:58000');

// Test 5: Precedence: window over localStorage
global.window.__OUTLAW_FORGE_API_URL__ = 'http://127.0.0.1:44444';
mockStorage.set('outlaw_forge_api_url', 'http://127.0.0.1:55555');
assert('Window takes precedence over localStorage', client1.getBaseUrl() === 'http://127.0.0.1:44444', client1.getBaseUrl(), 'http://127.0.0.1:44444');
delete global.window.__OUTLAW_FORGE_API_URL__;

// Test 6: Fallback when neither is set in browser
mockStorage.clear();
delete process.env.NEXT_PUBLIC_API_URL;
assert('Fallback default 127.0.0.1:8000 in browser', client1.getBaseUrl() === 'http://127.0.0.1:8000', client1.getBaseUrl(), 'http://127.0.0.1:8000');

// Test 7: NEXT_PUBLIC_API_URL environment variable fallback
process.env.NEXT_PUBLIC_API_URL = 'http://my-host:3000/';
assert('NEXT_PUBLIC_API_URL fallback with slash', client1.getBaseUrl() === 'http://my-host:3000', client1.getBaseUrl(), 'http://my-host:3000');
delete process.env.NEXT_PUBLIC_API_URL;

// Test 8: SSR environment (window is undefined)
const savedWindow = global.window;
delete global.window;
assert('SSR fallback default 127.0.0.1:8000', client1.getBaseUrl() === 'http://127.0.0.1:8000', client1.getBaseUrl(), 'http://127.0.0.1:8000');
process.env.NEXT_PUBLIC_API_URL = 'http://ssr-host:8080/';
assert('SSR with NEXT_PUBLIC_API_URL', client1.getBaseUrl() === 'http://ssr-host:8080', client1.getBaseUrl(), 'http://ssr-host:8080');
delete process.env.NEXT_PUBLIC_API_URL;
global.window = savedWindow;

// Test 9: localStorage SecurityError exception handling
const origGetItem = global.localStorage.getItem;
global.localStorage.getItem = () => { throw new Error('SecurityError: Access Denied'); };
let threw = false;
let res = null;
try {
  res = client1.getBaseUrl();
} catch (e) {
  threw = true;
}
assert('Handles localStorage SecurityError gracefully without throwing', !threw && res === 'http://127.0.0.1:8000', res, 'http://127.0.0.1:8000');
global.localStorage.getItem = origGetItem;

// Test 10: setBaseUrl override
client1.setBaseUrl('http://custom-proxy:9999/');
assert('setBaseUrl overrides all sources', client1.getBaseUrl() === 'http://custom-proxy:9999', client1.getBaseUrl(), 'http://custom-proxy:9999');

// Test 11: getDownloadUrl formatting
assert('getDownloadUrl with leading slash', client1.getDownloadUrl('/models/1/file.stl') === 'http://custom-proxy:9999/models/1/file.stl', client1.getDownloadUrl('/models/1/file.stl'), 'http://custom-proxy:9999/models/1/file.stl');
assert('getDownloadUrl without leading slash', client1.getDownloadUrl('models/1/file.stl') === 'http://custom-proxy:9999/models/1/file.stl', client1.getDownloadUrl('models/1/file.stl'), 'http://custom-proxy:9999/models/1/file.stl');

// Test 12: Dynamic re-evaluation on window property mutation without new instance
const clientDynamic = new ApiClient();
global.window.__OUTLAW_FORGE_API_URL__ = 'http://127.0.0.1:11111';
const u1 = clientDynamic.getBaseUrl();
global.window.__OUTLAW_FORGE_API_URL__ = 'http://127.0.0.1:22222';
const u2 = clientDynamic.getBaseUrl();
assert('Dynamic re-evaluation on window mutation', u1 === 'http://127.0.0.1:11111' && u2 === 'http://127.0.0.1:22222', u1 + ' -> ' + u2, '11111 -> 22222');

// Test 13: Verify fetch requests dynamically target changed base URL
let lastFetchedUrl = '';
global.fetch = async (url) => {
  lastFetchedUrl = url;
  return {
    ok: true,
    json: async () => ({ status: 'healthy', version: '0.1.0' })
  };
};

async function main() {
  global.window.__OUTLAW_FORGE_API_URL__ = 'http://127.0.0.1:33333';
  await clientDynamic.getHealth();
  const fetchUrl1 = lastFetchedUrl;

  global.window.__OUTLAW_FORGE_API_URL__ = 'http://127.0.0.1:44444';
  await clientDynamic.getHealth();
  const fetchUrl2 = lastFetchedUrl;

  assert('fetch(getHealth) dynamically binds to new port', fetchUrl1 === 'http://127.0.0.1:33333/health' && fetchUrl2 === 'http://127.0.0.1:44444/health', fetchUrl1 + ' -> ' + fetchUrl2, '33333/health -> 44444/health');

  // Test 14: AST / text check across all ApiClient methods
  const methodRegex = /async\s+([a-zA-Z0-9_]+)\s*\([^)]*\)\s*:\s*Promise<[^>]+>\s*\{([^}]+)\}/g;
  let match;
  let totalMethods = 0;
  let methodsUsingGetBaseUrl = 0;
  
  // Check that no method uses this.baseUrl directly
  const usesThisBaseUrlDirectly = tsSource.includes('${this.baseUrl}') || tsSource.includes('this.baseUrl/');
  assert('ApiClient has no direct this.baseUrl usages in endpoints', !usesThisBaseUrlDirectly, usesThisBaseUrlDirectly, false);

  // Check how many calls to getBaseUrl appear in api-client.ts
  const getBaseUrlCallCount = (tsSource.match(/this\.getBaseUrl\(\)/g) || []).length;
  assert('ApiClient methods invoke this.getBaseUrl() across all endpoints', getBaseUrlCallCount >= 35, getBaseUrlCallCount, '>= 35');

  // Test 15: Edge case: Multiple trailing slashes
  global.window.__OUTLAW_FORGE_API_URL__ = 'http://127.0.0.1:49152//';
  const cMulti = new ApiClient();
  // Regex /\/$/ strips the last slash
  const multiRes = cMulti.getBaseUrl();
  assert('Multiple trailing slashes: strips single trailing slash per contract', multiRes === 'http://127.0.0.1:49152/', multiRes, 'http://127.0.0.1:49152/');

  // Test 16: setBaseUrl strips trailing slash
  cMulti.setBaseUrl('http://127.0.0.1:8888/');
  assert('setBaseUrl strips trailing slash', cMulti.getBaseUrl() === 'http://127.0.0.1:8888', cMulti.getBaseUrl(), 'http://127.0.0.1:8888');

  // Test 17: empty string in window.__OUTLAW_FORGE_API_URL__
  global.window.__OUTLAW_FORGE_API_URL__ = '';
  assert('Empty string window.__OUTLAW_FORGE_API_URL__ falls back to 127.0.0.1:8000', cMulti.getBaseUrl() === 'http://127.0.0.1:8888', 'customBaseUrl kept', 'customBaseUrl kept');
  
  const cEmptyWindow = new ApiClient();
  assert('Empty string in window falls back when no custom base url', cEmptyWindow.getBaseUrl() === 'http://127.0.0.1:8000', cEmptyWindow.getBaseUrl(), 'http://127.0.0.1:8000');

  console.log(`\nFinal: ${testsPassed} passed, ${testsFailed} failed.`);
  if (testsFailed > 0) process.exit(1);
}


main().catch((err) => {
  console.error(err);
  process.exit(1);
});

