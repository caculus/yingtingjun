# Download ECDICT SQLite into models/ecdict.db for local EN→ZH lookup.
$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Models = Join-Path $Root "models"
$Dest = Join-Path $Models "ecdict.db"
$Url = if ($env:ECDICT_SQLITE_URL) {
    $env:ECDICT_SQLITE_URL
} else {
    "https://github.com/skywind3000/ECDICT/releases/download/1.0.28/ecdict-sqlite-28.zip"
}

if (Test-Path $Dest) {
    Write-Host "Already exists: $Dest"
    Write-Host "Remove it first to re-download."
    exit 0
}

New-Item -ItemType Directory -Force -Path $Models | Out-Null
$Tmp = Join-Path $env:TEMP ("ecdict." + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $Tmp | Out-Null
try {
    $Zip = Join-Path $Tmp "ecdict-sqlite.zip"
    Write-Host "Downloading ECDICT SQLite (large, ~200MB zip) ..."
    Write-Host "  $Url"
    Invoke-WebRequest -Uri $Url -OutFile $Zip -UseBasicParsing

    $OutDir = Join-Path $Tmp "out"
    Expand-Archive -Path $Zip -DestinationPath $OutDir -Force

    $Db = Get-ChildItem -Path $OutDir -Recurse -File |
        Where-Object { $_.Extension -in ".db", ".sqlite", ".sqlite3" } |
        Select-Object -First 1
    if (-not $Db) {
        Write-Host "No .db found inside zip. Contents:" -ForegroundColor Red
        Get-ChildItem -Path $OutDir -Recurse -File | Select-Object -First 40 | ForEach-Object { Write-Host $_.FullName }
        exit 1
    }

    Copy-Item $Db.FullName $Dest
    $Mb = [math]::Round((Get-Item $Dest).Length / 1MB, 1)
    Write-Host "Installed: $Dest"
    Write-Host "Size: $Mb MB"
    Write-Host "Done. Restart serve_player.py to use ECDICT-first dictionary lookup."
}
finally {
    Remove-Item -Recurse -Force $Tmp -ErrorAction SilentlyContinue
}
