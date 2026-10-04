# Outlaw Forge - Desktop Development Launcher Script
# Starts Python FastAPI backend sidecar on ephemeral/clean port and launches frontend in desktop dev mode

$ErrorActionPreference = "Stop"

Write-Host "`n=== Outlaw Forge Desktop Dev Launcher ===" -ForegroundColor Cyan

# 1. Detect free port
$Port = 8000
$PortAvailable = $false
while (-not $PortAvailable -and $Port -le 8020) {
    try {
        $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $Port)
        $listener.Start()
        $listener.Stop()
        $PortAvailable = $true
    } catch {
        Write-Host "Port $Port is in use, trying next..." -ForegroundColor Yellow
        $Port++
    }
}

Write-Host "Starting Python FastAPI sidecar on 127.0.0.1:$Port..." -ForegroundColor Green
$env:NEXT_PUBLIC_API_URL = "http://127.0.0.1:$Port"
$env:OUTLAW_FORGE_PORT = "$Port"

# 2. Spawn backend in background
$backendProc = Start-Process -FilePath "python" -ArgumentList "apps/api/app/cli.py", "--port", "$Port", "--host", "127.0.0.1" -PassThru

# 3. Wait for health check
Write-Host "Waiting for backend health check at http://127.0.0.1:$Port/health..." -ForegroundColor Gray
$healthy = $false
for ($i = 0; $i -lt 30; $i++) {
    try {
        $resp = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/health" -Method Get -TimeoutSec 1
        if ($resp.status -eq "healthy") {
            $healthy = $true
            break
        }
    } catch {
        Start-Sleep -Milliseconds 250
    }
}

if ($healthy) {
    Write-Host "Backend is healthy! Launching Next.js frontend workbench..." -ForegroundColor Green
} else {
    Write-Host "Backend startup timeout, proceeding anyway..." -ForegroundColor Yellow
}

try {
    # 4. Start frontend
    npm run dev --workspace=apps/web
} finally {
    Write-Host "`nTerminating backend sidecar process (PID: $($backendProc.Id))..." -ForegroundColor Cyan
    if ($backendProc -and -not $backendProc.HasExited) {
        Stop-Process -Id $backendProc.Id -Force -ErrorAction SilentlyContinue
    }
    Write-Host "Desktop session closed cleanly." -ForegroundColor Green
}
