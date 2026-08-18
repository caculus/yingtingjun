#!/usr/bin/env bash
# Install 英聽君 Linux deps into the active .venv (CPU).
#   bash scripts/install_linux.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "This script is for Linux. On macOS use requirements.txt; on Windows use install_windows.ps1." >&2
  exit 1
fi

echo "== Python environment =="
python -c "import platform,struct,sys; print(sys.version); print(sys.executable); print(platform.machine(), struct.calcsize('P')*8)"
machine="$(python -c "import platform; print(platform.machine())")"
if [[ "$machine" != "x86_64" && "$machine" != "aarch64" && "$machine" != "arm64" ]]; then
  echo
  echo "WARNING: packaged Linux installer supports x86_64 and aarch64. Dev install on $machine may still work if wheels exist." >&2
fi

echo
echo "== Upgrade pip =="
python -m pip install --upgrade pip setuptools wheel

echo
echo "== Install requirements-linux.txt (PyTorch CPU index) =="
python -m pip install -r "$ROOT/requirements-linux.txt"

echo
echo "== Verify =="
python -c "
import torch, numpy, torchaudio
import faster_whisper
from torchaudio_compat import prepare_torchaudio_for_speechbrain
print('torch', torch.__version__, 'cuda?', torch.cuda.is_available())
print('torchaudio', torchaudio.__version__)
print('numpy', numpy.__version__)
print('torchaudio mode', prepare_torchaudio_for_speechbrain())
from speechbrain.inference.speaker import EncoderClassifier  # noqa: F401
print('faster-whisper', faster_whisper.__version__)
print('speechbrain EncoderClassifier OK')
print('ok')
"

echo
echo "Done. Next: install ffmpeg if needed (Debian/Ubuntu: sudo apt install ffmpeg),"
echo "then python transcribe.py your.m4a"
