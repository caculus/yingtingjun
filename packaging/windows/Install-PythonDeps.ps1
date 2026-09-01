# Download everything not in the slim installer (visible progress in this window):
#   1) CPython embed-amd64 + pip
#   2) Gyan ffmpeg essentials → bin\ffmpeg.exe
#   3) ECDICT SQLite → models\ecdict.db
#   4) Python wheels (torch, faster-whisper, ...)
#   5) SpeechBrain ECAPA → models\spkrec-ecapa-voxceleb
$ErrorActionPreference = "Stop"
# Windows PowerShell 5.1 (Inno / Yingtingjun.bat) parses this file as ANSI unless UTF-8 BOM is present.
$Root = (Resolve-Path $PSScriptRoot).Path
$Log = Join-Path $Root "install-runtime.log"
try { Start-Transcript -Path $Log -Force | Out-Null } catch { }
try { $Host.UI.RawUI.WindowTitle = "英聽君 — 下載執行階段" } catch { }

$PyDir = Join-Path $Root "python"
$Py = Join-Path $PyDir "python.exe"
$Marker = Join-Path $PyDir ".deps-ok"
$YtMarker = Join-Path $PyDir ".youtube-deps-ok"
$YtReq = Join-Path $Root "requirements-youtube.txt"
$BinDir = Join-Path $Root "bin"
$Ffmpeg = Join-Path $BinDir "ffmpeg.exe"
$ModelsDir = Join-Path $Root "models"
$Ecdict = Join-Path $ModelsDir "ecdict.db"
$EcapaDir = Join-Path $ModelsDir "spkrec-ecapa-voxceleb"
$EcapaCkpt = Join-Path $EcapaDir "embedding_model.ckpt"

$PythonEmbedVersion = if ($env:YTJ_PYTHON_EMBED_VERSION) {
    $env:YTJ_PYTHON_EMBED_VERSION
} else {
    "3.13.15"
}
$PythonEmbedUrl = if ($env:YTJ_PYTHON_EMBED_URL) {
    $env:YTJ_PYTHON_EMBED_URL
} else {
    "https://www.python.org/ftp/python/$PythonEmbedVersion/python-$PythonEmbedVersion-embed-amd64.zip"
}
$FfmpegUrl = if ($env:YTJ_FFMPEG_URL) {
    $env:YTJ_FFMPEG_URL
} else {
    "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
}
$EcdictUrl = if ($env:ECDICT_SQLITE_URL) {
    $env:ECDICT_SQLITE_URL
} else {
    "https://github.com/skywind3000/ECDICT/releases/download/1.0.28/ecdict-sqlite-28.zip"
}

function Show-YtjProgress([int]$Percent, [string]$Status) {
    $Percent = [Math]::Max(0, [Math]::Min(100, $Percent))
    Write-Host ""
    Write-Host ("==== {0,3}%  {1} ====" -f $Percent, $Status) -ForegroundColor Cyan
    Write-Progress -Activity "英聽君 安裝" -Status $Status -PercentComplete $Percent
}

function Test-PythonDepsOk {
    if (-not (Test-Path $Py)) { return $false }
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    & $Py -c "import torch, faster_whisper, numpy, transformers; from torchaudio_compat import prepare_torchaudio_for_speechbrain; prepare_torchaudio_for_speechbrain(); from speechbrain.inference.speaker import EncoderClassifier; print('ok')"
    $code = $LASTEXITCODE
    $ErrorActionPreference = $prev
    return ($code -eq 0)
}

function Invoke-Download([string]$Url, [string]$Dest) {
    Write-Host "  $Url"
    $curl = Get-Command curl.exe -ErrorAction SilentlyContinue
    if ($curl) {
        & curl.exe -L --fail --progress-bar -o $Dest $Url
        if ($LASTEXITCODE -ne 0) { throw "download failed: $Url" }
        return
    }
    Invoke-WebRequest -Uri $Url -OutFile $Dest -UseBasicParsing
}

function Install-PythonEmbed {
    $needExtract = -not (Test-Path $Py)
    if (-not $needExtract) {
        Write-Host "Python already present: $Py" -ForegroundColor Green
    }
    else {
        Show-YtjProgress 8 "下載 Python $PythonEmbedVersion（AMD64 embed）"
        New-Item -ItemType Directory -Force -Path $PyDir | Out-Null
        $Tmp = Join-Path $env:TEMP ("ytj-python." + [guid]::NewGuid().ToString("N"))
        New-Item -ItemType Directory -Force -Path $Tmp | Out-Null
        try {
            $Zip = Join-Path $Tmp "python-embed-amd64.zip"
            Write-Host "Downloading CPython embed-amd64 (~12–16 MB) ..."
            Invoke-Download $PythonEmbedUrl $Zip
            Show-YtjProgress 14 "解壓 Python"
            Expand-Archive -Path $Zip -DestinationPath $PyDir -Force
        }
        finally {
            Remove-Item -Recurse -Force $Tmp -ErrorAction SilentlyContinue
        }
        if (-not (Test-Path $Py)) {
            throw "python.exe missing after embed extract: $Py"
        }
    }

    $pth = Get-ChildItem $PyDir -Filter "python*._pth" | Select-Object -First 1
    if (-not $pth) {
        throw "python*._pth not found in embed package"
    }
    $zipName = (Get-ChildItem $PyDir -Filter "python*.zip" | Select-Object -First 1).Name
    @"
$zipName
.

Lib\site-packages
..\app
import site
"@ | Set-Content -Path $pth.FullName -Encoding ascii

    Show-YtjProgress 18 "安裝 pip"
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    & $Py -m pip --version
    $pipOk = ($LASTEXITCODE -eq 0)
    $ErrorActionPreference = $prev
    if (-not $pipOk) {
        $getPip = Join-Path $env:TEMP "get-pip.py"
        Invoke-Download "https://bootstrap.pypa.io/get-pip.py" $getPip
        & $Py $getPip
        if ($LASTEXITCODE -ne 0) { throw "get-pip failed" }
    }
    & $Py -m pip install --upgrade pip setuptools wheel
    if ($LASTEXITCODE -ne 0) { throw "pip bootstrap failed" }
    Write-Host "Python ready: $Py"
}

function Install-FfmpegEssentials {
    if (Test-Path $Ffmpeg) {
        Write-Host "ffmpeg already present: $Ffmpeg" -ForegroundColor Green
        return
    }
    Show-YtjProgress 25 "下載 ffmpeg essentials"
    New-Item -ItemType Directory -Force -Path $BinDir | Out-Null
    $Tmp = Join-Path $env:TEMP ("ytj-ffmpeg." + [guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Force -Path $Tmp | Out-Null
    try {
        $Zip = Join-Path $Tmp "ffmpeg-essentials.zip"
        Write-Host "Downloading Gyan ffmpeg essentials (~107 MB zip) ..."
        Invoke-Download $FfmpegUrl $Zip
        Show-YtjProgress 32 "解壓 ffmpeg"
        $OutDir = Join-Path $Tmp "out"
        Expand-Archive -Path $Zip -DestinationPath $OutDir -Force
        $Src = Get-ChildItem -Path $OutDir -Recurse -File -Filter "ffmpeg.exe" | Select-Object -First 1
        if (-not $Src) {
            throw "ffmpeg.exe not found inside essentials zip"
        }
        Copy-Item $Src.FullName $Ffmpeg -Force
        $Mb = [math]::Round((Get-Item $Ffmpeg).Length / 1MB, 1)
        Write-Host "Installed: $Ffmpeg ($Mb MB)"
    }
    finally {
        Remove-Item -Recurse -Force $Tmp -ErrorAction SilentlyContinue
    }
}

function Install-Ecdict {
    if (Test-Path $Ecdict) {
        Write-Host "ECDICT already present: $Ecdict" -ForegroundColor Green
        return
    }
    Show-YtjProgress 40 "下載英中詞典 ECDICT"
    New-Item -ItemType Directory -Force -Path $ModelsDir | Out-Null
    $Tmp = Join-Path $env:TEMP ("ytj-ecdict." + [guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Force -Path $Tmp | Out-Null
    try {
        $Zip = Join-Path $Tmp "ecdict-sqlite.zip"
        Write-Host "Downloading ECDICT SQLite (~200 MB zip, ~800 MB unpacked) ..."
        Invoke-Download $EcdictUrl $Zip
        Show-YtjProgress 50 "解壓詞典"
        $OutDir = Join-Path $Tmp "out"
        Expand-Archive -Path $Zip -DestinationPath $OutDir -Force
        $Db = Get-ChildItem -Path $OutDir -Recurse -File |
            Where-Object { $_.Extension -in ".db", ".sqlite", ".sqlite3" } |
            Select-Object -First 1
        if (-not $Db) {
            throw "No .db found inside ECDICT zip"
        }
        Copy-Item $Db.FullName $Ecdict -Force
        $Mb = [math]::Round((Get-Item $Ecdict).Length / 1MB, 1)
        Write-Host "Installed: $Ecdict ($Mb MB)"
    }
    finally {
        Remove-Item -Recurse -Force $Tmp -ErrorAction SilentlyContinue
    }
}

function Install-PythonPackages {
    if ((Test-Path $Marker) -and (Test-PythonDepsOk)) {
        Write-Host "Python packages already installed." -ForegroundColor Green
        return
    }

    Show-YtjProgress 58 "安裝 Python 套件（torch 等，較久）"
    Write-Host "Python: $Py"

    & $Py -m pip --version
    if ($LASTEXITCODE -ne 0) {
        throw "pip is not available after Python embed setup."
    }

    Show-YtjProgress 62 "安裝 torch（PyTorch CPU）"
    & $Py -m pip install torch==2.9.1 --index-url https://download.pytorch.org/whl/cpu
    if ($LASTEXITCODE -ne 0) { throw "torch install failed" }

    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    & $Py -m pip uninstall -y torchaudio | Out-Null
    $ErrorActionPreference = $prevEap

    Show-YtjProgress 75 "安裝 speechbrain"
    & $Py -m pip install hyperpyyaml joblib scipy tqdm huggingface_hub packaging pyyaml
    if ($LASTEXITCODE -ne 0) { throw "speechbrain deps failed" }
    & $Py -m pip install speechbrain==1.1.0 --no-deps
    if ($LASTEXITCODE -ne 0) { throw "speechbrain install failed" }

    Show-YtjProgress 82 "安裝 faster-whisper / transformers"
    & $Py -m pip install faster-whisper==1.1.1 soundfile==0.13.1 numpy==2.2.6 scikit-learn==1.6.1 transformers==4.57.6 sentencepiece==0.2.2 sacremoses==0.1.1
    if ($LASTEXITCODE -ne 0) { throw "remaining requirements failed" }

    if (-not (Test-PythonDepsOk)) {
        throw "Packages installed but import check failed."
    }

    "ok $(Get-Date -Format o)" | Set-Content -Path $Marker -Encoding ascii
    Write-Host "Python packages ready." -ForegroundColor Green
}

function Test-YtdlpOk {
    $bin = Join-Path $PyDir "Scripts\yt-dlp.exe"
    if (Test-Path $bin) {
        & $bin --version | Out-Null
        return ($LASTEXITCODE -eq 0)
    }
    & $Py -m yt_dlp --version | Out-Null
    return ($LASTEXITCODE -eq 0)
}

function Install-YoutubeTools {
    if (-not (Test-Path $YtReq)) {
        Write-Host "Skipping yt-dlp (missing requirements-youtube.txt)."
        return
    }
    $hash = (Get-FileHash $YtReq -Algorithm SHA256).Hash
    if ((Test-Path $YtMarker) -and (Select-String -Path $YtMarker -Pattern $hash -Quiet) -and (Test-YtdlpOk)) {
        Write-Host "yt-dlp already installed." -ForegroundColor Green
        return
    }
    Show-YtjProgress 85 "安裝 YouTube 匯入（yt-dlp）"
    & $Py -m pip install -r $YtReq
    if ($LASTEXITCODE -ne 0) { throw "yt-dlp install failed" }
    if (-not (Test-YtdlpOk)) { throw "yt-dlp installed but not runnable" }
    "ok $hash $(Get-Date -Format o)" | Set-Content -Path $YtMarker -Encoding ascii
    Write-Host "yt-dlp ready." -ForegroundColor Green
}

function Install-Ecapa {
    if (Test-Path $EcapaCkpt) {
        Write-Host "ECAPA already present: $EcapaDir" -ForegroundColor Green
        return
    }
    Show-YtjProgress 90 "下載 ECAPA 話者模型"
    New-Item -ItemType Directory -Force -Path $EcapaDir | Out-Null
    $env:YTJ_MODELS_DIR = $ModelsDir
    $env:HF_HOME = $ModelsDir
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    & $Py -c @"
from pathlib import Path
from torchaudio_compat import prepare_torchaudio_for_speechbrain
prepare_torchaudio_for_speechbrain()
from speechbrain.inference.speaker import EncoderClassifier
savedir = Path(r'$EcapaDir')
EncoderClassifier.from_hparams(
    source='speechbrain/spkrec-ecapa-voxceleb',
    savedir=str(savedir),
    run_opts={'device': 'cpu'},
)
print('ecapa-ok')
"@
    $code = $LASTEXITCODE
    $ErrorActionPreference = $prev
    if ($code -ne 0 -or -not (Test-Path $EcapaCkpt)) {
        throw "ECAPA download failed"
    }
    Write-Host "Installed: $EcapaDir"
}

try {
    Show-YtjProgress 2 "開始下載執行階段（需連網）"
    Write-Host "安裝目錄: $Root"
    Install-PythonEmbed
    Install-FfmpegEssentials
    Install-Ecdict
    Install-PythonPackages
    Install-YoutubeTools
    Install-Ecapa
    Show-YtjProgress 100 "完成"
    Write-Progress -Activity "英聽君 安裝" -Completed
    Write-Host "`nAll runtime extras ready." -ForegroundColor Green
    Write-Host "Log: $Log"
}
catch {
    Write-Progress -Activity "英聽君 安裝" -Completed
    Write-Host "`nFAILED: $_" -ForegroundColor Red
    Write-Host "Log: $Log"
    throw
}
finally {
    try { Stop-Transcript | Out-Null } catch { }
}
