# Outlaw Forge: Desktop Development Launcher Script
# Starts Python FastAPI backend sidecar on ephemeral port and launches frontend in desktop dev mode

param(
    [int]$Port = 0,
    [switch]$BackendOnly,
    [switch]$SkipBackend,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "=== Outlaw Forge Desktop Dev Launcher ===" -ForegroundColor Cyan

# 1. Ephemeral or specified port discovery
if ($Port -eq 0) {
    try {
        $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
        $listener.Start()
        $Port = $listener.LocalEndpoint.Port
        $listener.Stop()
    } catch {
        Write-Error "Failed to allocate ephemeral local port: $_"
        exit 1
    }
}

# Set environment variables for runtime synchronization
$env:OUTLAW_FORGE_PORT = "$Port"
$env:NEXT_PUBLIC_API_URL = "http://127.0.0.1:$Port"
$env:TAURI_ENV_PLATFORM = "windows"

# Dry run inspection
if ($DryRun) {
    Write-Host "[DryRun] Port allocated: $Port" -ForegroundColor Cyan
    Write-Host "[DryRun] Environment variables configured:" -ForegroundColor Cyan
    Write-Host "  OUTLAW_FORGE_PORT = $env:OUTLAW_FORGE_PORT" -ForegroundColor Gray
    Write-Host "  NEXT_PUBLIC_API_URL = $env:NEXT_PUBLIC_API_URL" -ForegroundColor Gray
    Write-Host "  TAURI_ENV_PLATFORM = $env:TAURI_ENV_PLATFORM" -ForegroundColor Gray

    if (-not $SkipBackend) {
        Write-Host "[DryRun] Backend command: python apps/api/app/cli.py --port $Port --host 127.0.0.1" -ForegroundColor Cyan
        Write-Host "[DryRun] Health check polling target: http://127.0.0.1:$Port/health (up to 30 attempts, 250ms interval)" -ForegroundColor Cyan
    } else {
        Write-Host "[DryRun] Backend execution skipped (-SkipBackend set)" -ForegroundColor Yellow
    }

    if ($BackendOnly) {
        Write-Host "[DryRun] Standalone backend mode: awaiting termination signal" -ForegroundColor Cyan
    } else {
        Write-Host "[DryRun] Frontend command: npm run dev --workspace=apps/web" -ForegroundColor Cyan
    }

    Write-Host "[DryRun] Desktop dev launcher validation complete." -ForegroundColor Green
    exit 0
}

$backendProc = $null

try {
    # 2. Spawn backend process
    if (-not $SkipBackend) {
        Write-Host "Starting Python FastAPI sidecar on 127.0.0.1:$Port..." -ForegroundColor Green
        $backendProc = Start-Process -FilePath "python" -ArgumentList "apps/api/app/cli.py", "--port", "$Port", "--host", "127.0.0.1" -PassThru

        # 3. Active health check polling
        Write-Host "Polling backend health check at http://127.0.0.1:$Port/health..." -ForegroundColor Gray
        $healthy = $false
        for ($i = 0; $i -lt 30; $i++) {
            if ($backendProc.HasExited) {
                Write-Error "Backend process exited unexpectedly with code $($backendProc.ExitCode)"
                break
            }

            try {
                $resp = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/health" -Method Get -TimeoutSec 1 -ErrorAction SilentlyContinue
                if ($resp -and $resp.status -eq "healthy") {
                    $healthy = $true
                    break
                }
            } catch {
                # Service still initializing
            }

            Start-Sleep -Milliseconds 250
        }

        if ($healthy) {
            Write-Host "Backend is healthy on port $Port." -ForegroundColor Green
        } else {
            Write-Host "Warning: Backend did not respond healthy within timeout, continuing..." -ForegroundColor Yellow
        }
    }

    # 4. Mode dispatch: BackendOnly or Full Workbench
    if ($BackendOnly) {
        Write-Host "Backend running in standalone mode on port $Port." -ForegroundColor Cyan
        Write-Host "Press Enter or Ctrl+C to terminate..." -ForegroundColor Cyan
        try {
            [void][System.Console]::ReadLine()
        } catch {
            while ($true) {
                Start-Sleep -Seconds 1
            }
        }
    } else {
        Write-Host "Launching Next.js frontend workbench..." -ForegroundColor Green
        $hasCargo = Get-Command cargo -ErrorAction SilentlyContinue
        $hasTauri = Get-Command tauri -ErrorAction SilentlyContinue
        if ($hasCargo -and $hasTauri) {
            npx @tauri-apps/cli dev
        } else {
            npm run dev --workspace=apps/web
        }
    }
} finally {
    if ($backendProc) {
        Write-Host ""
        Write-Host "Terminating backend sidecar process (PID: $($backendProc.Id))..." -ForegroundColor Cyan
        if (-not $backendProc.HasExited) {
            Get-CimInstance Win32_Process -Filter "ParentProcessId = $($backendProc.Id)" -ErrorAction SilentlyContinue | ForEach-Object {
                Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
            }
            Stop-Process -Id $backendProc.Id -Force -ErrorAction SilentlyContinue
        }
    }
    Write-Host "Desktop session closed cleanly." -ForegroundColor Green
}
