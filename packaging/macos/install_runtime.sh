#!/bin/bash
# Download runtime not shipped in the slim .app (visible in Terminal):
#   1) CPython standalone arm64 (python-build-standalone)
#   2) ECDICT SQLite → models/ecdict.db
#   3) pip packages from bundled requirements.txt (mlx-whisper / torch / …)
#   4) SpeechBrain ECAPA → models/spkrec-ecapa-voxceleb
set -euo pipefail

RESOURCES="${YTJ_APP_RESOURCES:-$(cd "$(dirname "$0")" && pwd)}"
SUPPORT="${YTJ_SUPPORT:-$HOME/Library/Application Support/Yingtingjun}"
APP_DIR="$RESOURCES/app"
REQ="$RESOURCES/requirements.txt"
REQ_YT="$RESOURCES/requirements-youtube.txt"
PY_DIR="$SUPPORT/python"
PY="$PY_DIR/bin/python3"
MARKER="$PY_DIR/.deps-ok"
YTDLP_MARKER="$PY_DIR/.youtube-deps-ok"
MODELS="$SUPPORT/models"
ECDICT="$MODELS/ecdict.db"
ECAPA_DIR="$MODELS/spkrec-ecapa-voxceleb"
ECAPA_CKPT="$ECAPA_DIR/embedding_model.ckpt"
LOG="$SUPPORT/install-runtime.log"
PYTHON_TAG="${YTJ_PYTHON_STANDALONE_TAG:-20260814}"
PYTHON_VERSION="${YTJ_PYTHON_VERSION:-3.12.14}"
PYTHON_URL="${YTJ_PYTHON_STANDALONE_URL:-https://github.com/astral-sh/python-build-standalone/releases/download/${PYTHON_TAG}/cpython-${PYTHON_VERSION}+${PYTHON_TAG}-aarch64-apple-darwin-install_only_stripped.tar.gz}"
ECDICT_URL="${ECDICT_SQLITE_URL:-https://github.com/skywind3000/ECDICT/releases/download/1.0.28/ecdict-sqlite-28.zip}"

mkdir -p "$SUPPORT"
touch "$LOG"
exec > >(tee -a "$LOG") 2>&1

progress() {
  printf '\n==== %3d%%  %s ====\n' "$1" "$2"
}

die() {
  echo "FAILED: $*" >&2
  echo "Log: $LOG" >&2
  exit 1
}

download() {
  echo "  $1"
  curl -L --fail --progress-bar -o "$2" "$1" || die "download failed: $1"
}

python_deps_ok() {
  [[ -x "$PY" ]] || return 1
  PYTHONPATH="$APP_DIR" "$PY" -c "
import mlx_whisper, numpy, torch, transformers
from speechbrain.inference.speaker import EncoderClassifier
print('ok')
" >/dev/null 2>&1
}

req_hash() {
  shasum -a 256 "$REQ" | awk '{print $1}'
}

install_python() {
  if [[ -x "$PY" ]]; then
    echo "Python already present: $PY"
    return 0
  fi
  progress 8 "下載 Python ${PYTHON_VERSION}（Apple Silicon）"
  local tmp tgz
  tmp="$(mktemp -d "${TMPDIR:-/tmp}/ytj-python.XXXXXX")"
  tgz="$tmp/python-standalone.tar.gz"
  echo "Downloading CPython standalone arm64 …"
  download "$PYTHON_URL" "$tgz"
  progress 16 "解壓 Python"
  tar -xzf "$tgz" -C "$tmp"
  if [[ ! -x "$tmp/python/bin/python3" ]]; then
    rm -rf "$tmp"
    die "python3 missing after extract"
  fi
  rm -rf "$PY_DIR"
  mv "$tmp/python" "$PY_DIR"
  rm -rf "$tmp"
  xattr -dr com.apple.quarantine "$PY_DIR" 2>/dev/null || true
  [[ -x "$PY" ]] || die "python3 missing: $PY"
  echo "Python ready: $PY"
}

ensure_pip() {
  progress 20 "安裝 pip"
  if ! "$PY" -m pip --version >/dev/null 2>&1; then
    "$PY" -m ensurepip --upgrade || die "ensurepip failed"
  fi
  "$PY" -m pip install --upgrade pip setuptools wheel || die "pip bootstrap failed"
}

install_ecdict() {
  if [[ -f "$ECDICT" ]]; then
    echo "ECDICT already present: $ECDICT"
    return 0
  fi
  progress 32 "下載英中詞典 ECDICT"
  mkdir -p "$MODELS"
  local tmp zip db
  tmp="$(mktemp -d "${TMPDIR:-/tmp}/ytj-ecdict.XXXXXX")"
  zip="$tmp/ecdict-sqlite.zip"
  echo "Downloading ECDICT SQLite (~200 MB zip) …"
  download "$ECDICT_URL" "$zip"
  progress 42 "解壓詞典"
  mkdir -p "$tmp/out"
  unzip -q -o "$zip" -d "$tmp/out"
  db="$(find "$tmp/out" -type f \( -name '*.db' -o -name '*.sqlite' -o -name '*.sqlite3' \) | head -n 1 || true)"
  if [[ -z "$db" ]]; then
    rm -rf "$tmp"
    die "No .db found inside ECDICT zip"
  fi
  cp "$db" "$ECDICT"
  rm -rf "$tmp"
  echo "Installed: $ECDICT ($(du -h "$ECDICT" | awk '{print $1}'))"
}

install_packages() {
  local hash
  hash="$(req_hash)"
  if [[ -f "$MARKER" ]] && grep -q "$hash" "$MARKER" && python_deps_ok; then
    echo "Python packages already installed."
    return 0
  fi
  [[ -f "$REQ" ]] || die "missing $REQ"
  progress 55 "安裝 Python 套件（torch / MLX，較久）"
  echo "Python: $PY"
  "$PY" -m pip --version >/dev/null || die "pip is not available"
  progress 62 "pip install -r requirements.txt"
  PYTHONPATH="$APP_DIR" "$PY" -m pip install -r "$REQ" || die "pip install failed"
  if ! python_deps_ok; then
    PYTHONPATH="$APP_DIR" "$PY" -c "
import mlx_whisper, numpy, torch, transformers
from speechbrain.inference.speaker import EncoderClassifier
print('ok')
" || true
    die "Packages installed but import check failed."
  fi
  echo "ok $hash $(date -u +%Y-%m-%dT%H:%M:%SZ)" >"$MARKER"
  echo "Python packages ready."
}

ytdlp_ok() {
  [[ -x "$PY_DIR/bin/yt-dlp" ]] && "$PY_DIR/bin/yt-dlp" --version >/dev/null 2>&1 && return 0
  "$PY" -m yt_dlp --version >/dev/null 2>&1
}

install_youtube_tools() {
  local hash
  [[ -f "$REQ_YT" ]] || {
    echo "Skipping yt-dlp (missing $REQ_YT)."
    return 0
  }
  hash="$(shasum -a 256 "$REQ_YT" | awk '{print $1}')"
  if [[ -f "$YTDLP_MARKER" ]] && grep -q "$hash" "$YTDLP_MARKER" && ytdlp_ok; then
    echo "yt-dlp already installed."
    return 0
  fi
  progress 72 "安裝 YouTube 匯入（yt-dlp）"
  PYTHONPATH="$APP_DIR" "$PY" -m pip install -r "$REQ_YT" || die "yt-dlp install failed"
  ytdlp_ok || die "yt-dlp installed but not runnable"
  echo "ok $hash $(date -u +%Y-%m-%dT%H:%M:%SZ)" >"$YTDLP_MARKER"
  echo "yt-dlp ready."
}

install_ecapa() {
  if [[ -f "$ECAPA_CKPT" ]]; then
    echo "ECAPA already present: $ECAPA_DIR"
    return 0
  fi
  progress 88 "下載 ECAPA 話者模型"
  mkdir -p "$ECAPA_DIR"
  export YTJ_MODELS_DIR="$MODELS"
  export HF_HOME="$MODELS"
  export YTJ_ECAPA_DIR="$ECAPA_DIR"
  PYTHONPATH="$APP_DIR" "$PY" -c "
from pathlib import Path
import os
from torchaudio_compat import prepare_torchaudio_for_speechbrain
prepare_torchaudio_for_speechbrain()
from speechbrain.inference.speaker import EncoderClassifier
savedir = Path(os.environ['YTJ_ECAPA_DIR'])
EncoderClassifier.from_hparams(
    source='speechbrain/spkrec-ecapa-voxceleb',
    savedir=str(savedir),
    run_opts={'device': 'cpu'},
)
print('ecapa-ok')
" || die "ECAPA download failed"
  [[ -f "$ECAPA_CKPT" ]] || die "ECAPA checkpoint missing: $ECAPA_CKPT"
  echo "Installed: $ECAPA_DIR"
}

progress 2 "開始下載執行階段（需連網）"
echo "App resources: $RESOURCES"
echo "Install dir:   $SUPPORT"
echo "Log:           $LOG"
install_python
ensure_pip
install_ecdict
install_packages
install_youtube_tools
install_ecapa
progress 100 "完成"
echo
echo "All runtime extras ready."
echo "Log: $LOG"
