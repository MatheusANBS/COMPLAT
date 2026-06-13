param(
    [switch]$NoGlobalCommands
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvPath = Join-Path $ProjectRoot ".venv"
$PythonExe = Join-Path $VenvPath "Scripts\python.exe"
$ScriptsPath = Join-Path $VenvPath "Scripts"

Write-Host "COMPLAT setup" -ForegroundColor Cyan
Write-Host "Project: $ProjectRoot"

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python was not found in PATH. Install Python 3.11+ and run this script again."
}

if (-not (Test-Path $PythonExe)) {
    Write-Host "Creating virtual environment..." -ForegroundColor Cyan
    python -m venv $VenvPath
}

Write-Host "Upgrading pip..." -ForegroundColor Cyan
& $PythonExe -m pip install --upgrade pip

Write-Host "Installing requirements..." -ForegroundColor Cyan
& $PythonExe -m pip install -r (Join-Path $ProjectRoot "requirements.txt")

Write-Host "Installing COMPLAT in editable mode..." -ForegroundColor Cyan
& $PythonExe -m pip install -e "$ProjectRoot[dev]"

$ComplatCmd = Join-Path $ProjectRoot "complat.cmd"
$ComplatUiCmd = Join-Path $ProjectRoot "complat-ui.cmd"

Set-Content -Path $ComplatCmd -Encoding ASCII -Value @"
@echo off
"%~dp0.venv\Scripts\complat.exe" %*
"@

Set-Content -Path $ComplatUiCmd -Encoding ASCII -Value @"
@echo off
"%~dp0.venv\Scripts\complat-ui.exe" %*
"@

if (-not $NoGlobalCommands) {
    $CurrentUserPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $PathParts = $CurrentUserPath -split ";" | Where-Object { $_ }

    if ($PathParts -notcontains $ProjectRoot) {
        $NewPath = @($PathParts + $ProjectRoot) -join ";"
        [Environment]::SetEnvironmentVariable("Path", $NewPath, "User")
        $env:Path = "$env:Path;$ProjectRoot"
        Write-Host "Added project root to your user PATH. Open a new terminal to use complat-ui globally." -ForegroundColor Green
    } else {
        Write-Host "Project root is already in your user PATH." -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "Setup complete." -ForegroundColor Green
Write-Host "Run the desktop app with:" -ForegroundColor Cyan
Write-Host "  .\complat-ui"
Write-Host ""
Write-Host "Run the CLI with:" -ForegroundColor Cyan
Write-Host "  .\complat --help"
Write-Host ""
Write-Host "Global terminal commands are configured by default." -ForegroundColor Cyan
Write-Host "Open a new terminal and run:"
Write-Host "  complat-ui"
Write-Host ""
Write-Host "To skip PATH updates in the future:" -ForegroundColor Cyan
Write-Host "  .\setup.ps1 -NoGlobalCommands"
