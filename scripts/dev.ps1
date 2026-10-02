# Outlaw Forge - Dev Startup Script (PowerShell)
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host " Starting Outlaw Forge Monorepo (Dev) " -ForegroundColor Yellow
Write-Host "==========================================" -ForegroundColor Cyan

# Start Backend. A stale process can answer /health while hanging on database
# routes, so probe the project route before deciding whether the default port is usable.
$backendPort = 8000
try {
    $probe = Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:8000/projects" -TimeoutSec 2
    if ($probe.StatusCode -ne 200) { throw "API project route returned $($probe.StatusCode)" }
} catch {
    $backendPort = 8003
    Write-Host "`n[1/2] Port 8000 is unavailable; using clean API port 8003." -ForegroundColor Yellow
}

Write-Host "`n[1/2] Starting FastAPI Backend on http://127.0.0.1:$backendPort..." -ForegroundColor Green
$backendProcess = Start-Process -FilePath "python" -ArgumentList "-m uvicorn app.main:app --host 127.0.0.1 --port $backendPort --reload" -WorkingDirectory "apps/api" -PassThru

# Start Frontend
Write-Host "[2/2] Starting Next.js Frontend on http://localhost:3000..." -ForegroundColor Green
$npmCommand = if ($IsWindows) { "npm.cmd" } else { "npm" }
$env:NEXT_PUBLIC_API_URL = "http://127.0.0.1:$backendPort"
$frontendProcess = Start-Process -FilePath $npmCommand -ArgumentList "run dev --prefix apps/web" -PassThru

Write-Host "`nBoth services launched. Press Ctrl+C in this shell or stop processes to exit.`n" -ForegroundColor Cyan
Write-Host "Backend PID : $($backendProcess.Id)" -ForegroundColor Gray
Write-Host "Frontend PID: $($frontendProcess.Id)" -ForegroundColor Gray
Write-Host "API URL     : $env:NEXT_PUBLIC_API_URL" -ForegroundColor Gray
