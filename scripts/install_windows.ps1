# Install 英聽君 Windows deps into .venv (CPU torch).
# Usage (from repo root, after creating .venv and activating it):
#   powershell -ExecutionPolicy Bypass -File scripts\install_windows.ps1
$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root

Write-Host "== Python environment ==" -ForegroundColor Cyan
python -c "import platform,struct,sys; print('exe:', sys.executable); print('version:', sys.version); print('machine:', platform.machine()); print('platform:', platform.platform()); print('bits:', struct.calcsize('P')*8)"

Write-Host "`n== Upgrade pip ==" -ForegroundColor Cyan
python -m pip install --upgrade pip setuptools wheel

Write-Host "`n== Install torch/torchaudio (PyTorch CPU index) ==" -ForegroundColor Cyan
python -m pip install torch==2.9.1 torchaudio==2.9.1 --index-url https://download.pytorch.org/whl/cpu

Write-Host "`n== Install remaining requirements-windows.txt ==" -ForegroundColor Cyan
python -m pip install -r requirements-windows.txt

Write-Host "`n== Verify ==" -ForegroundColor Cyan
python -c "import torch,torchaudio,faster_whisper,numpy; print('torch', torch.__version__, 'cuda?', torch.cuda.is_available()); print('numpy', numpy.__version__); print('ok')"

Write-Host "`nDone. Next: winget install Gyan.FFmpeg  (if needed), then python transcribe.py your.m4a" -ForegroundColor Green
