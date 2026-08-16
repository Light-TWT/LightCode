# Build the LightCode desktop sidecar with PyInstaller.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts/build-sidecar.ps1
#
# Requirements:
#   * A Python environment with PyInstaller, FastAPI, Uvicorn and python-multipart
#     installed (e.g. the project's miniconda env).
#   * The build only clears generated build output under backend/build/ and
#     backend/dist/; it never touches source or the DB.
#
# The resulting single-file executable is written to the ignored directory
# electron/resources/sidecar/.

$ErrorActionPreference = "Stop"

# Resolve paths relative to the repository root ($PSScriptRoot = scripts/).
$RepoRoot = Split-Path -Parent $PSScriptRoot
$BackendDir = Join-Path $RepoRoot "backend"
$OutDir     = Join-Path $RepoRoot "electron\resources\sidecar"

# Allow overriding the Python interpreter. Defaults to the python on PATH.
$Py = $env:LIGHTCODE_PYTHON
if (-not $Py) {
    $Py = (Get-Command python -ErrorAction SilentlyContinue).Source
}
if (-not (Test-Path $Py)) {
    throw "Python interpreter not found. Set LIGHTCODE_PYTHON to a Python with PyInstaller installed."
}

Write-Host "Using Python: $Py"

# Clear only generated build output (never source or user data).
$BuildOut = @(
    (Join-Path $BackendDir "build"),
    (Join-Path $BackendDir "dist")
)
foreach ($d in $BuildOut) {
    if (Test-Path $d) {
        Remove-Item -Recurse -Force $d
    }
}

# Clear the previous sidecar artifact (ignored directory).
if (Test-Path $OutDir) {
    Remove-Item -Recurse -Force $OutDir
}
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

Push-Location $BackendDir
try {
    & $Py -m PyInstaller --clean --noconfirm --distpath dist pyinstaller.spec
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed with exit code $LASTEXITCODE"
    }
}
finally {
    Pop-Location
}

$Artifact = Join-Path $BackendDir "dist\lightcode-sidecar.exe"
if (-not (Test-Path $Artifact)) {
    throw "Expected sidecar executable not found after build: $Artifact"
}

Copy-Item $Artifact $OutDir
Write-Host "Sidecar built: $Artifact"
Write-Host "Copied to:     $(Join-Path $OutDir 'lightcode-sidecar.exe')"
