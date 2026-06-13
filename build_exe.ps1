param(
    [switch]$Clean
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$EntryPoint = Join-Path $ProjectRoot "src\complat\presentation\pyside_app.py"
$IconPath = Join-Path $ProjectRoot "complat.ico"
$AssetsPath = Join-Path $ProjectRoot "src\complat\assets"
$DistPath = Join-Path $ProjectRoot "dist"
$BuildPath = Join-Path $ProjectRoot "build"

if (-not (Test-Path $VenvPython)) {
    Write-Host "Virtual environment not found. Running setup first..." -ForegroundColor Cyan
    & (Join-Path $ProjectRoot "setup.ps1") -NoGlobalCommands
}

if ($Clean) {
    Write-Host "Cleaning previous build output..." -ForegroundColor Cyan
    if (Test-Path $DistPath) { Remove-Item -LiteralPath $DistPath -Recurse -Force }
    if (Test-Path $BuildPath) { Remove-Item -LiteralPath $BuildPath -Recurse -Force }
}

Write-Host "Installing build dependencies..." -ForegroundColor Cyan
& $VenvPython -m pip install -e "$ProjectRoot[build]"

Write-Host "Building COMPLAT executable..." -ForegroundColor Cyan
& $VenvPython -m PyInstaller `
    --noconfirm `
    --clean `
    --onedir `
    --windowed `
    --name COMPLAT `
    --icon "$IconPath" `
    --paths (Join-Path $ProjectRoot "src") `
    --add-data "$AssetsPath;complat/assets" `
    --exclude-module pytest `
    --exclude-module unittest `
    --exclude-module tkinter `
    --exclude-module numpy `
    --exclude-module pandas `
    --exclude-module matplotlib `
    --exclude-module IPython `
    "$EntryPoint"

$ExePath = Join-Path $ProjectRoot "dist\COMPLAT\COMPLAT.exe"
if (-not (Test-Path $ExePath)) {
    throw "Build finished but executable was not found: $ExePath"
}

Write-Host ""
Write-Host "Build complete." -ForegroundColor Green
Write-Host "Executable:" -ForegroundColor Cyan
Write-Host "  $ExePath"
Write-Host ""
Write-Host "For fastest startup, distribute the whole folder:" -ForegroundColor Cyan
Write-Host "  $ProjectRoot\dist\COMPLAT"
