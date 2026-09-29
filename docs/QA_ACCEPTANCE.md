# Outlaw Forge: QA Acceptance Matrix & Verification Protocol

## 1. System Overview & QA Objectives

Outlaw Forge maintains strict contract parity, determinism, and high reliability across the frontend, backend, and geometry processing layers.

The Quality Assurance and Verification suite ensures:
1. **API Contract Parity**: Strict adherence to Pydantic models in Python and TypeScript interfaces in `shared/types/api.ts`.
2. **Deterministic Response Schemas**: All responses return standardized payloads with zero schema drift.
3. **High Performance & Low Latency**: Health check and metadata probes must respond within the defined latency budgets.
4. **CORS & Security Compliance**: Accurate access headers and disallowed method rejection (405 Method Not Allowed).

---

## 2. Test Verification Matrix

| Test Suite / Harness | Location | Target Scope | Execution Command |
| :--- | :--- | :--- | :--- |
| **Backend Unit & Contract Tests** | `backend/tests/test_health.py` | Pytest + httpx Async & Sync clients testing `/health`, `/api/v1/health`, `/`, CORS, schema validation | `pytest backend/tests` |
| **Standalone Smoke Test Harness** | `tests/verify_health.py` | Independent blackbox HTTP smoke verification of running instances | `python tests/verify_health.py --base-url http://127.0.0.1:8000` |
| **Frontend Unit & Component Tests** | `frontend/src/__tests__/` | Vitest / Jest testing UI components, state stores, and viewport interactions | `npm test` (in `frontend/`) |

---

## 3. Schema & API Contract Specification

### 3.1 Health Status Contract (`/health` and `/api/v1/health`)

| Field | Type | Allowed Values / Format | Description |
| :--- | :--- | :--- | :--- |
| `status` | `string` (enum) | `"healthy"`, `"degraded"`, `"unhealthy"` | Overall health status of backend |
| `version` | `string` | Semver format (e.g. `"0.1.0"`) | Application version |
| `app_name` | `string` | `"Outlaw Forge"` | System name |
| `environment` | `string` | `"development"`, `"staging"`, `"production"`, `"test"` | Active runtime environment |
| `services.database` | `string` (enum) | `"connected"`, `"disconnected"` | Database connection state |
| `services.mesh_engine` | `string` (enum) | `"ready"`, `"unavailable"` | Computational geometry engine state |
| `system.platform` | `string` | Non-empty OS platform string | Host OS and architecture details |
| `system.python_version` | `string` | Semver python runtime version | Python version running the server |
| `timestamp` | `string` | ISO 8601 UTC timestamp format | Server timestamp of response |

### 3.2 Root Discovery Contract (`/`)

| Field | Type | Expected Value / Content |
| :--- | :--- | :--- |
| `message` | `string` | Contains `"Outlaw Forge"` |
| `version` | `string` | Current semver string |
| `docs_url` | `string` | `"/api/v1/docs"` |
| `health_url` | `string` | `"/health"` |

---

## 4. Acceptance Thresholds & Quality Gates

| Metric | Acceptance Threshold | Failure Action |
| :--- | :--- | :--- |
| **Automated Test Pass Rate** | **100%** (0 failing tests) | Block PR / deployment |
| **Health Probe Latency** | **< 100 ms** (P99) | Performance profiling |
| **API Contract Validation** | 100% field & enum conformity | Schema audit & fix |
| **CORS Policy** | Allowed origins receive `Access-Control-Allow-Origin` | CORS middleware configuration review |
| **Unsupported Methods** | Returns `405 Method Not Allowed` | Routing inspection |

---

## 5. Execution Guide

### 5.1 Running Backend Pytest Suites
```bash
# From project root
cd d:/Outlaw-Forge/backend
pytest -v tests/
```

### 5.2 Running Standalone Smoke Test Harness
```bash
# Against local running backend
python d:/Outlaw-Forge/tests/verify_health.py --base-url http://127.0.0.1:8000 --timeout 5.0
```

### 5.3 Running Frontend Unit Tests
```bash
# From frontend workspace
cd d:/Outlaw-Forge/frontend
npm test
```

---

## 6. Failure Triage & Diagnostic Playbook

1. **Connection Refused on `verify_health.py`**:
   - Ensure the backend service is running (`python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`).
   - Check if port 8000 is occupied by another process.
2. **Schema Field Mismatch**:
   - Verify that changes in `backend/app/models/health.py` are synchronized with `shared/types/api.ts`.
3. **CORS Header Missing**:
   - Check `BACKEND_CORS_ORIGINS` in `backend/app/core/config.py` to ensure request origin is included.
