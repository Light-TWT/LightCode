# Manual verification harness for the LightCode Windows installer.
#
# This script is NOT automated end-to-end: installing a signed-unsigned NSIS
# package and upgrading it requires a clean Windows account and explicit user
# confirmation of the uninstall/upgrade prompt. It documents and drives the
# steps so a human can verify install -> register -> chat -> relaunch ->
# upgrade -> persistence.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts/test-desktop-install.ps1
#
# Environment:
#   LIGHTCODE_INSTALLER   path to the NSIS installer .exe (default: electron/release/LightCode Setup 0.1.0.exe)
#   LIGHTCODE_INSTALL_DIR target install directory for a local (non-elevated) check

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$Installer = $env:LIGHTCODE_INSTALLER
if (-not $Installer) {
    $Installer = Join-Path $RepoRoot "electron\release\LightCode Setup 0.1.0.exe"
}
if (-not (Test-Path $Installer)) {
    throw "Installer not found: $Installer"
}

$InstallDir = $env:LIGHTCODE_INSTALL_DIR
if (-not $InstallDir) {
    $InstallDir = Join-Path $env:TEMP "lightcode-desk-install"
}

Write-Host "Installer : $Installer"
Write-Host "InstallDir: $InstallDir"
Write-Host ""
Write-Host "Manual checklist (run each step, confirm, then continue):"
Write-Host ""
Write-Host "1. Install"
Write-Host "   - Run the installer, choose '$InstallDir', complete install."
Write-Host "   - Confirm 'LightCode' launches and the warm-paper homepage appears."
Write-Host ""
Write-Host "2. Register a workspace"
Write-Host "   - Use the folder picker to select a real project folder."
Write-Host "   - Confirm the folder is kept in the picker and the composer enables."
Write-Host ""
Write-Host "3. First message"
Write-Host "   - Send a message; confirm a chat session is created and you navigate into it."
Write-Host ""
Write-Host "4. Close and relaunch"
Write-Host "   - Quit the app fully, relaunch."
Write-Host "   - Confirm the registered workspace and past session still exist (SQLite persistence)."
Write-Host ""
Write-Host "5. (Optional) Upgrade"
Write-Host "   - Build a second installer (v2), run it over the existing install."
Write-Host "   - Confirm app resources are replaced while user data (sessions/workspaces) survive."
Write-Host ""
Write-Host "6. Uninstall"
Write-Host "   - Confirm uninstall removes app resources and does NOT silently delete user data."
Write-Host "   - User data lives under electron userData (app.getPath('userData')), outside install dir."
Write-Host ""
Write-Host "Data location note: mutable user data (SQLite, skills, credentials) is stored under"
Write-Host "the OS user-data directory, NOT inside the install directory. Uninstall does not"
Write-Host "remove it automatically."
Write-Host ""
Write-Host "Installer exists. Ready for manual verification."