# Launches the Golf Swing Analyzer desktop app (Electron UI + Python backend).
# The Electron main process starts/stops the backend itself; this script just
# sets app mode, makes sure the UI is built, and opens the window.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Definition
$frontend = Join-Path $root 'frontend'
Set-Location $frontend

# Build the UI once if it hasn't been built yet (first run after setup).
if (-not (Test-Path (Join-Path $frontend 'dist\index.html'))) {
    & npm run build
}

$env:GOLF_SIM_APP = '1'
$electron = Join-Path $frontend 'node_modules\.bin\electron.cmd'
& $electron .
