# Copy the built Vue renderer into electron/frontend-dist so electron-builder
# can package it as app resources. The renderer is built separately by Vite
# (frontend/), and this script only mirrors the immutable build output.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts/copy-frontend-to-electron.ps1

$ErrorActionPreference = "Stop"

$RepoRoot   = Split-Path -Parent $PSScriptRoot
$FrontendSrc = Join-Path $RepoRoot "frontend\dist"
$ElectronDst = Join-Path $RepoRoot "electron\frontend-dist"

if (-not (Test-Path $FrontendSrc)) {
    throw "Frontend build output not found at '$FrontendSrc'. Run 'npm run build' in frontend/ first."
}

if (Test-Path $ElectronDst) {
    Remove-Item -Recurse -Force $ElectronDst
}
Copy-Item -Recurse $FrontendSrc $ElectronDst
Write-Host "Copied frontend build to $ElectronDst"