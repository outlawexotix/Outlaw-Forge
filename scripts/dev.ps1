# Outlaw Forge - Dev Startup Script (PowerShell)
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host " Starting Outlaw Forge Monorepo (Dev) " -ForegroundColor Yellow
Write-Host "==========================================" -ForegroundColor Cyan

# Start Backend
Write-Host "`n[1/2] Starting FastAPI Backend on http://127.0.0.1:8000..." -ForegroundColor Green
$backendProcess = Start-Process -FilePath "python" -ArgumentList "-m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload" -WorkingDirectory "apps/api" -PassThru

# Start Frontend
Write-Host "[2/2] Starting Next.js Frontend on http://localhost:3000..." -ForegroundColor Green
$frontendProcess = Start-Process -FilePath "npm" -ArgumentList "run dev --prefix apps/web" -PassThru

Write-Host "`nBoth services launched. Press Ctrl+C in this shell or stop processes to exit.`n" -ForegroundColor Cyan
Write-Host "Backend PID : $($backendProcess.Id)" -ForegroundColor Gray
Write-Host "Frontend PID: $($frontendProcess.Id)" -ForegroundColor Gray
