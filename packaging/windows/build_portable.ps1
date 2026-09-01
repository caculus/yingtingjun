# Build dist\Yingtingjun portable folder (launch contract) and optionally Inno Setup exe.
# Slim payload: app + launcher + bootstrap. Downloaded at install / first launch:
#   CPython embed-amd64, pip wheels, ffmpeg essentials, ECDICT, ECAPA.
#   powershell -ExecutionPolicy Bypass -File packaging\windows\build_portable.ps1
#   powershell -ExecutionPolicy Bypass -File packaging\windows\build_portable.ps1 -SkipInstaller
param(
    [switch]$SkipInstaller
)

$ErrorActionPreference = "Stop"
$Repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$DistRoot = Join-Path $Repo "dist"
$Dist = Join-Path $DistRoot "Yingtingjun"
$AppDir = Join-Path $Dist "app"

function Write-Step([string]$msg) {
    Write-Host "`n== $msg ==" -ForegroundColor Cyan
}

Write-Step "Clean $Dist"
if (Test-Path $Dist) {
    Remove-Item -Recurse -Force $Dist
}
New-Item -ItemType Directory -Force -Path $AppDir | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $Dist "data") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $Dist "bin") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $Dist "models") | Out-Null

Write-Step "Copy application (no Python / ffmpeg / models)"
$appFiles = @(
    "transcribe.py",
    "serve_player.py",
    "stem_utils.py",
    "asr_backend.py",
    "audio_convert.py",
    "audio_resample.py",
    "platform_runtime.py",
    "progress_log.py",
    "torchaudio_compat.py"
)
foreach ($name in $appFiles) {
    Copy-Item (Join-Path $Repo $name) (Join-Path $AppDir $name)
}
Copy-Item -Recurse (Join-Path $Repo "player") (Join-Path $AppDir "player")
Copy-Item -Recurse (Join-Path $Repo "yt_decoder") (Join-Path $AppDir "yt_decoder")
Copy-Item (Join-Path $Repo "requirements-youtube.txt") (Join-Path $Dist "requirements-youtube.txt")
Copy-Item (Join-Path $PSScriptRoot "Yingtingjun.bat") (Join-Path $Dist "Yingtingjun.bat")
# PowerShell 5.1 needs a UTF-8 BOM to parse Chinese strings; Copy-Item may drop it.
$ps1Src = Join-Path $PSScriptRoot "Install-PythonDeps.ps1"
$ps1Dst = Join-Path $Dist "Install-PythonDeps.ps1"
$utf8Bom = New-Object System.Text.UTF8Encoding $true
[System.IO.File]::WriteAllText($ps1Dst, [System.IO.File]::ReadAllText($ps1Src), $utf8Bom)

if (-not (Test-Path (Join-Path $AppDir "serve_player.py"))) {
    throw "app\serve_player.py missing"
}

Write-Step "Portable folder ready (Python downloaded at install)"
Write-Host $Dist

if ($SkipInstaller) {
    Write-Host "Skip Inno Setup (-SkipInstaller)."
    exit 0
}

function Find-ISCC {
    $paths = @(
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles}\Inno Setup 6\ISCC.exe",
        "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
    )
    foreach ($p in $paths) {
        if (Test-Path $p) { return $p }
    }
    $cmd = Get-Command iscc.exe -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    return $null
}

Write-Step "Inno Setup"
$iscc = Find-ISCC
if (-not $iscc) {
    Write-Host "ISCC.exe not found. Installing JRSoftware.InnoSetup via winget ..."
    winget install --id JRSoftware.InnoSetup -e --accept-package-agreements --accept-source-agreements
    $iscc = Find-ISCC
}
if (-not $iscc) {
    throw "Inno Setup compiler not found after install. Open packaging\windows\yingtingjun.iss in Inno Setup."
}
$iss = Join-Path $PSScriptRoot "yingtingjun.iss"
& $iscc $iss
if ($LASTEXITCODE -ne 0) {
    throw "ISCC failed"
}
Write-Host "Installer: $(Join-Path $DistRoot 'Yingtingjun-Setup-x64.exe')"
