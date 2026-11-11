#Requires -Version 5.1
<#
.SYNOPSIS
  Build Damai Ticket Assistant for Windows (onedir) with PyInstaller + Playwright Chromium.

.DESCRIPTION
  Intended for GitHub Actions windows-latest (or a real Windows machine).
  Do NOT run this on Debian/Linux and expect a working Windows EXE.

  Product boundary: monitor / reminder only — no auto-purchase / 抢票.
#>

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root

Write-Host "=== Damai Ticket Assistant Windows build ==="
Write-Host "Root: $Root"
Write-Host "Python: $(python --version 2>&1)"

$Venv = Join-Path $Root ".venv-win"
if (-not (Test-Path $Venv)) {
  Write-Host "Creating venv at $Venv"
  python -m venv $Venv
}

$Py = Join-Path $Venv "Scripts\python.exe"
$Pip = Join-Path $Venv "Scripts\pip.exe"
$Playwright = Join-Path $Venv "Scripts\playwright.exe"
$PyInstaller = Join-Path $Venv "Scripts\pyinstaller.exe"

& $Py -m pip install --upgrade pip
& $Pip install -r (Join-Path $Root "requirements.txt")
& $Pip install "pyinstaller==6.22.3"

# Stage Playwright browsers next to the future dist folder
$DistDir = Join-Path $Root "dist\DamaiTicketAssistant"
$BrowsersDir = Join-Path $Root "build\ms-playwright"
New-Item -ItemType Directory -Force -Path $BrowsersDir | Out-Null
$env:PLAYWRIGHT_BROWSERS_PATH = $BrowsersDir

Write-Host "Installing Playwright Chromium into $BrowsersDir"
& $Py -m playwright install chromium
# On some runners system deps helper exists:
try {
  & $Py -m playwright install-deps chromium
} catch {
  Write-Host "playwright install-deps skipped/failed (often OK on windows-latest): $_"
}

Write-Host "Running PyInstaller (onedir)..."
if (Test-Path (Join-Path $Root "dist")) {
  Remove-Item -Recurse -Force (Join-Path $Root "dist")
}
& $Py -m PyInstaller --noconfirm --clean (Join-Path $Root "DamaiTicketAssistant.spec")

if (-not (Test-Path $DistDir)) {
  throw "Build failed: missing dist folder $DistDir"
}

$Exe = Join-Path $DistDir "DamaiTicketAssistant.exe"
if (-not (Test-Path $Exe)) {
  throw "Build failed: missing EXE $Exe"
}

# schema.sql must land in the onedir payload. v0.11.0 omitted it and frozen
# DB init raised "schema file missing" / "Failed to execute script 'run_app'".
$SchemaPacked = Join-Path $DistDir "_internal\app\storage\schema.sql"
if (-not (Test-Path -LiteralPath $SchemaPacked)) {
  throw "Build failed: schema.sql was not packed at $SchemaPacked"
}
Write-Host "packed schema.sql OK: $SchemaPacked"

# Copy browsers beside the app so PLAYWRIGHT_BROWSERS_PATH can resolve next to EXE
$DistBrowsers = Join-Path $DistDir "ms-playwright"
Write-Host "Copying Playwright browsers to $DistBrowsers"
if (Test-Path $DistBrowsers) {
  Remove-Item -Recurse -Force $DistBrowsers
}
Copy-Item -Recurse -Force $BrowsersDir $DistBrowsers

# Sizes
function Get-DirSizeMB([string]$Path) {
  if (-not (Test-Path $Path)) { return 0 }
  $bytes = (Get-ChildItem -Recurse -Force $Path -ErrorAction SilentlyContinue |
    Measure-Object -Property Length -Sum).Sum
  if (-not $bytes) { return 0 }
  return [math]::Round($bytes / 1MB, 2)
}

$exeSize = [math]::Round((Get-Item $Exe).Length / 1MB, 2)
$distSize = Get-DirSizeMB $DistDir
$browserSize = Get-DirSizeMB $DistBrowsers

# DB init, then a second launch against the same user database (restart).
# Fail the job if either run exits non-zero. This is a real Windows EXE smoke,
# not a substitute for an interactive GUI click-through.
function Invoke-ListTasksSmoke([string]$Label) {
  Write-Host "EXE smoke ${Label}: DamaiTicketAssistant.exe --list-tasks"
  $logDir = Join-Path $Root "build\exe-smoke"
  New-Item -ItemType Directory -Force -Path $logDir | Out-Null
  $outLog = Join-Path $logDir "$Label.stdout.txt"
  $errLog = Join-Path $logDir "$Label.stderr.txt"
  if (Test-Path $outLog) { Remove-Item -Force $outLog }
  if (Test-Path $errLog) { Remove-Item -Force $errLog }
  $proc = Start-Process -FilePath $Exe -ArgumentList "--list-tasks" -Wait -PassThru `
    -WorkingDirectory $DistDir `
    -RedirectStandardOutput $outLog -RedirectStandardError $errLog
  $code = $proc.ExitCode
  Write-Host "EXE smoke ${Label} exit code: $code"
  if (Test-Path $outLog) {
    Get-Content -Path $outLog -ErrorAction SilentlyContinue | Select-Object -First 40 | ForEach-Object {
      Write-Host "stdout: $_"
    }
  }
  if (Test-Path $errLog) {
    Get-Content -Path $errLog -ErrorAction SilentlyContinue | Select-Object -First 40 | ForEach-Object {
      Write-Host "stderr: $_"
    }
  }
  if ($code -ne 0) {
    throw "DamaiTicketAssistant.exe --list-tasks failed on $Label run (exit $code)"
  }
}

Invoke-ListTasksSmoke "first"
Invoke-ListTasksSmoke "second"
Write-Host "EXE smoke OK"

Write-Host "=== Build OK ==="
Write-Host "EXE:  $Exe ($exeSize MB)"
Write-Host "Dist: $DistDir ($distSize MB total)"
Write-Host "Browsers: $DistBrowsers ($browserSize MB)"

# Marker for CI
$OkFile = Join-Path $DistDir "BUILD_OK.txt"
@(
  "DamaiTicketAssistant Windows build OK"
  "exe_mb=$exeSize"
  "dist_mb=$distSize"
  "browsers_mb=$browserSize"
  "generated=$(Get-Date -Format o)"
) | Set-Content -Path $OkFile -Encoding UTF8

Write-Host "Wrote $OkFile"
exit 0
