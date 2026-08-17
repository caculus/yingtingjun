# Install 英聽君 Windows deps into the active .venv (CPU).
#   powershell -ExecutionPolicy Bypass -File scripts\install_windows.ps1
$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root

Write-Host "== Python environment ==" -ForegroundColor Cyan
$info = python -c "import platform,struct,sys; print(sys.version); print(sys.executable); print(platform.machine()); print(struct.calcsize('P')*8)"
Write-Host $info
$machine = (python -c "import platform; print(platform.machine())").Trim()
$isArm = $machine -match "ARM64|aarch64"

if ($isArm) {
    Write-Host "`nWARNING: You are using ARM64 Python." -ForegroundColor Yellow
    Write-Host "Strongly recommended: python.org Windows installer (64-bit / AMD64), not ARM64." -ForegroundColor Yellow
    Write-Host "  Delete .venv and recreate with: py -3.12-64 -m venv .venv" -ForegroundColor Yellow
}

Write-Host "`n== Upgrade pip ==" -ForegroundColor Cyan
python -m pip install --upgrade pip setuptools wheel

Write-Host "`n== Install torch (PyTorch CPU index) ==" -ForegroundColor Cyan
python -m pip install torch==2.9.1 --index-url https://download.pytorch.org/whl/cpu

# torchaudio is optional: resample uses torch fallback; ECAPA uses numpy tensors.
# Broken torchaudio on Windows pops a modal DLL dialog (torch_library_impl) and blocks ECAPA.
Write-Host "`n== Skip torchaudio (optional; avoids Windows DLL mismatch) ==" -ForegroundColor Yellow
$prevEap = $ErrorActionPreference
$ErrorActionPreference = "SilentlyContinue"
python -m pip uninstall -y torchaudio | Out-Null
$ErrorActionPreference = $prevEap

Write-Host "`n== Install speechbrain without pulling torchaudio ==" -ForegroundColor Cyan
python -m pip install hyperpyyaml joblib scipy tqdm huggingface_hub packaging pyyaml
python -m pip install speechbrain==1.1.0 --no-deps

Write-Host "`n== Install remaining requirements-windows.txt ==" -ForegroundColor Cyan
python -m pip install faster-whisper==1.1.1 soundfile==0.13.1 numpy==2.2.6 scikit-learn==1.6.1 transformers==4.57.6 sentencepiece==0.2.2 sacremoses==0.1.1

Write-Host "`n== Verify ==" -ForegroundColor Cyan
python -c @"
import importlib.util
import torch, numpy
print('torch', torch.__version__, 'cuda?', torch.cuda.is_available())
print('numpy', numpy.__version__)
print('torchaudio', 'installed' if importlib.util.find_spec('torchaudio') else 'no (OK)')
import faster_whisper
from torchaudio_compat import prepare_torchaudio_for_speechbrain
prepare_torchaudio_for_speechbrain()
from speechbrain.inference.speaker import EncoderClassifier
print('faster-whisper', faster_whisper.__version__)
print('speechbrain EncoderClassifier OK')
print('ok')
"@

Write-Host "`nDone. Next: winget install Gyan.FFmpeg (if needed), then python transcribe.py your.m4a" -ForegroundColor Green
