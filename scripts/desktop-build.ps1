# Outlaw Forge: Desktop Packaging and Production Build Script
# Packages Next.js static export, PyInstaller FastAPI sidecar, and Tauri 2.0 desktop shell

param(
    [switch]$SkipFrontend,
    [switch]$SkipSidecar,
    [switch]$SkipTauri,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "=== Outlaw Forge Desktop Production Build ===" -ForegroundColor Cyan

# Dry run inspection
if ($DryRun) {
    Write-Host "[DryRun] Validating workspace paths and tool prerequisites..." -ForegroundColor Cyan

    # Validate workspace directories and specs
    $webDir = "apps/web"
    $specFile = "apps/api/outlaw_forge.spec"
    $tauriDir = "src-tauri"

    if (Test-Path $webDir) {
        Write-Host "  [OK] Frontend directory: $webDir" -ForegroundColor Green
    } else {
        Write-Host "  [MISSING] Frontend directory: $webDir" -ForegroundColor Red
    }

    if (Test-Path $specFile) {
        Write-Host "  [OK] PyInstaller specification: $specFile" -ForegroundColor Green
    } else {
        Write-Host "  [MISSING] PyInstaller specification: $specFile" -ForegroundColor Red
    }

    if (Test-Path $tauriDir) {
        Write-Host "  [OK] Tauri shell directory: $tauriDir" -ForegroundColor Green
    } else {
        Write-Host "  [MISSING] Tauri shell directory: $tauriDir" -ForegroundColor Red
    }

    # Detect toolchains
    $hasNode = Get-Command node -ErrorAction SilentlyContinue
    $hasNpm = Get-Command npm -ErrorAction SilentlyContinue
    $hasPyinstaller = (Get-Command pyinstaller -ErrorAction SilentlyContinue) -ne $null
    if (-not $hasPyinstaller) {
        try {
            $null = python -m PyInstaller --version 2>$null
            if ($LASTEXITCODE -eq 0) {
                $hasPyinstaller = $true
            }
        } catch {}
    }
    $hasCargo = Get-Command cargo -ErrorAction SilentlyContinue
    $hasTauri = Get-Command tauri -ErrorAction SilentlyContinue

    Write-Host "[DryRun] Toolchain status:" -ForegroundColor Cyan
    Write-Host "  Node.js: $(if ($hasNode) { 'Available' } else { 'Not found' })" -ForegroundColor Gray
    Write-Host "  npm: $(if ($hasNpm) { 'Available' } else { 'Not found' })" -ForegroundColor Gray
    Write-Host "  PyInstaller: $(if ($hasPyinstaller) { 'Available' } else { 'Not found on PATH' })" -ForegroundColor Gray
    Write-Host "  Cargo / Rust: $(if ($hasCargo) { 'Available' } else { 'Not found on PATH' })" -ForegroundColor Gray
    Write-Host "  Tauri CLI: $(if ($hasTauri) { 'Available' } else { 'Available via npx or absent' })" -ForegroundColor Gray

    Write-Host "[DryRun] Planned build actions:" -ForegroundColor Cyan
    Write-Host "  Step 1 (Frontend): $(if (-not $SkipFrontend) { 'npm run build --workspace=apps/web (output: export)' } else { 'Skipped' })" -ForegroundColor Gray
    Write-Host "  Step 2 (Sidecar):  $(if (-not $SkipSidecar) { 'PyInstaller build of apps/api/outlaw_forge.spec' } else { 'Skipped' })" -ForegroundColor Gray
    Write-Host "  Step 3 (Tauri):    $(if (-not $SkipTauri) { 'Tauri 2.0 native bundle build' } else { 'Skipped' })" -ForegroundColor Gray

    Write-Host "[DryRun] Build pipeline validation complete." -ForegroundColor Green
    exit 0
}

# Step 1: Export Next.js static distribution
if (-not $SkipFrontend) {
    Write-Host "`n[1/3] Building Next.js static export (apps/web/out)..." -ForegroundColor Yellow

    # Pre-clean stale export directory and build cache
    if (Test-Path "apps/web/out") {
        Write-Host "Cleaning stale export directory apps/web/out..." -ForegroundColor Gray
        Remove-Item -Recurse -Force "apps/web/out" -ErrorAction SilentlyContinue
    }
    if (Test-Path "apps/web/.next") {
        Write-Host "Cleaning stale build cache apps/web/.next..." -ForegroundColor Gray
        Remove-Item -Recurse -Force "apps/web/.next" -ErrorAction SilentlyContinue
    }

    $env:OUTPUT_EXPORT = "true"
    $env:TAURI_ENV_PLATFORM = "windows"
    npm run build --workspace=apps/web

    if ($LASTEXITCODE -ne 0) {
        Write-Error "Next.js static export failed with exit code $LASTEXITCODE"
        exit $LASTEXITCODE
    }

    if (Test-Path "apps/web/out/index.html") {
        Write-Host "Next.js static export successfully created at apps/web/out/index.html." -ForegroundColor Green
    } else {
        Write-Error "Next.js static export failed. apps/web/out/index.html not found."
        exit 1
    }
} else {
    Write-Host "`n[1/3] Skipping frontend static export (-SkipFrontend specified)." -ForegroundColor Yellow
}

# Step 2: Build PyInstaller sidecar binary if pyinstaller is installed
if (-not $SkipSidecar) {
    Write-Host "`n[2/3] Checking PyInstaller sidecar binary packaging..." -ForegroundColor Yellow
    $hasPyinstallerCmd = Get-Command pyinstaller -ErrorAction SilentlyContinue
    $hasPyinstaller = $hasPyinstallerCmd -ne $null

    if (-not $hasPyinstaller) {
        try {
            $null = python -m PyInstaller --version 2>$null
            if ($LASTEXITCODE -eq 0) {
                $hasPyinstaller = $true
            }
        } catch {}
    }

    if ($hasPyinstaller) {
        Write-Host "PyInstaller found. Bundling Python FastAPI geometry engine..." -ForegroundColor Gray
        if ($hasPyinstallerCmd) {
            pyinstaller --noconfirm --clean apps/api/outlaw_forge.spec
        } else {
            python -m PyInstaller --noconfirm --clean apps/api/outlaw_forge.spec
        }

        if ($LASTEXITCODE -ne 0) {
            Write-Error "PyInstaller build failed with exit code $LASTEXITCODE"
            exit $LASTEXITCODE
        }

        # Stage binary to src-tauri/binaries/
        $binDir = "src-tauri/binaries"
        if (-not (Test-Path $binDir)) {
            New-Item -ItemType Directory -Force -Path $binDir | Out-Null
        }

        $candidates = @(
            "dist/outlaw-forge-api/outlaw-forge-api.exe",
            "dist/outlaw_forge_sidecar/outlaw_forge_sidecar.exe",
            "dist/outlaw-forge-api.exe",
            "dist/outlaw_forge_sidecar.exe",
            "apps/api/dist/outlaw-forge-api/outlaw-forge-api.exe"
        )
        $builtExe = $null
        foreach ($cand in $candidates) {
            if (Test-Path $cand) {
                $builtExe = $cand
                break
            }
        }
        if (-not $builtExe -and (Test-Path "dist")) {
            $found = Get-ChildItem -Path "dist" -Filter "*.exe" -Recurse -File -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($found) {
                $builtExe = $found.FullName
            }
        }

        if ($builtExe) {
            Copy-Item -Path $builtExe -Destination "$binDir/outlaw_forge_sidecar.exe" -Force
            Copy-Item -Path $builtExe -Destination "$binDir/outlaw_forge_sidecar-x86_64-pc-windows-msvc.exe" -Force
            Write-Host "Sidecar binary staged successfully to $binDir." -ForegroundColor Green
        } else {
            Write-Host "Warning: PyInstaller finished, but executable was not found in dist." -ForegroundColor Yellow
        }
    } else {
        Write-Host "Notice: PyInstaller not detected on PATH or Python environment." -ForegroundColor Yellow
        Write-Host "Skipping binary bundling (Python runtime will be used in development)." -ForegroundColor Gray
    }
} else {
    Write-Host "`n[2/3] Skipping sidecar binary packaging (-SkipSidecar specified)." -ForegroundColor Yellow
}

# Step 3: Check Tauri CLI and build native bundle
if (-not $SkipTauri) {
    Write-Host "`n[3/3] Checking Tauri 2.0 desktop shell packaging..." -ForegroundColor Yellow
    $hasCargo = Get-Command cargo -ErrorAction SilentlyContinue
    $hasTauriCli = Get-Command tauri -ErrorAction SilentlyContinue

    if ($hasCargo) {
        Write-Host "Cargo found. Packaging Tauri 2.0 desktop shell..." -ForegroundColor Green
        if ($hasTauriCli) {
            tauri build
        } else {
            npx @tauri-apps/cli build
        }

        if ($LASTEXITCODE -ne 0) {
            Write-Error "Tauri build failed with exit code $LASTEXITCODE"
            exit $LASTEXITCODE
        }

        Write-Host "Tauri build completed successfully." -ForegroundColor Green
    } else {
        Write-Host "Notice: Cargo / Rust toolchain not found on PATH." -ForegroundColor Yellow
        Write-Host "Desktop shell sources in src-tauri/ are configured and ready." -ForegroundColor Gray
        Write-Host "To compile native Windows installers (NSIS/MSI), install Rust via https://rustup.rs and rerun this script." -ForegroundColor Gray
    }
} else {
    Write-Host "`n[3/3] Skipping Tauri shell packaging (-SkipTauri specified)." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=== Desktop Build Pipeline Complete ===" -ForegroundColor Green
