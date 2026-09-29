# Outlaw Forge - Test Orchestrator (PowerShell)
param(
    [switch]$BackendOnly,
    [switch]$FrontendOnly,
    [switch]$SmokeOnly
)

$ErrorActionPreference = "Stop"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host " Running Outlaw Forge Test Verification  " -ForegroundColor Yellow
Write-Host "==========================================" -ForegroundColor Cyan

if (-not $FrontendOnly) {
    Write-Host "`n[1/3] Executing Backend Pytest Suite..." -ForegroundColor Green
    python -m pytest apps/api/tests -v
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Backend tests failed!" -ForegroundColor Red
        exit 1
    }
}

if (-not $BackendOnly -and -not $SmokeOnly) {
    Write-Host "`n[2/3] Executing Frontend Build and Type Verification..." -ForegroundColor Green
    npm run build --prefix apps/web
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Frontend build verification failed!" -ForegroundColor Red
        exit 1
    }
}

if (-not $BackendOnly -and -not $FrontendOnly) {
    Write-Host "`n[3/3] Executing Health Contract Smoke Test..." -ForegroundColor Green
    python tests/verify_health.py
}

Write-Host "`nAll tests completed successfully!" -ForegroundColor Green
