#!/bin/bash
# Download runtime not shipped in the slim tarball (visible in the terminal):
#   1) CPython standalone (python-build-standalone; x86_64 or aarch64)
#   2) static ffmpeg if not already on PATH
#   3) ECDICT SQLite → models/ecdict.db
#   4) pip packages from bundled requirements-linux.txt (faster-whisper / torch)
#   5) SpeechBrain ECAPA → models/spkrec-ecapa-voxceleb
set -euo pipefail

RESOURCES="${YTJ_APP_RESOURCES:-$(cd "$(dirname "$0")" && pwd)}"
# shellcheck source=arch.sh
source "$RESOURCES/arch.sh"
ARCH="$(ytj_require_linux_arch)" || {
  echo "FAILED: unsupported CPU $(uname -m). Need x86_64 or aarch64." >&2
  exit 1
}

SUPPORT="${YTJ_SUPPORT:-${XDG_DATA_HOME:-$HOME/.local/share}/yingtingjun}"
APP_DIR="$RESOURCES/app"
REQ="$RESOURCES/requirements-linux.txt"
REQ_YT="$RESOURCES/requirements-youtube.txt"
PY_DIR="$SUPPORT/python"
PY="$PY_DIR/bin/python3"
MARKER="$PY_DIR/.deps-ok"
YTDLP_MARKER="$PY_DIR/.youtube-deps-ok"
MODELS="$SUPPORT/models"
ECDICT="$MODELS/ecdict.db"
ECAPA_DIR="$MODELS/spkrec-ecapa-voxceleb"
ECAPA_CKPT="$ECAPA_DIR/embedding_model.ckpt"
BIN_DIR="$SUPPORT/bin"
FFMPEG="$BIN_DIR/ffmpeg"
LOG="$SUPPORT/install-runtime.log"
PYTHON_TAG="${YTJ_PYTHON_STANDALONE_TAG:-20260814}"
PYTHON_VERSION="${YTJ_PYTHON_VERSION:-3.12.14}"
ECDICT_URL="${ECDICT_SQLITE_URL:-https://github.com/skywind3000/ECDICT/releases/download/1.0.28/ecdict-sqlite-28.zip}"

case "$ARCH" in
  x86_64)
    PYTHON_TRIPLE="x86_64-unknown-linux-gnu"
    FFMPEG_SLUG="linux64"
    ARCH_LABEL="Linux x86_64"
    DEFAULT_FFMPEG_URL="https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-n8.1-latest-linux64-gpl-8.1.tar.xz"
    ;;
  aarch64)
    PYTHON_TRIPLE="aarch64-unknown-linux-gnu"
    FFMPEG_SLUG="linuxarm64"
    ARCH_LABEL="Linux ARM64"
    DEFAULT_FFMPEG_URL="https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-n8.1-latest-linuxarm64-gpl-8.1.tar.xz"
    ;;
  *)
    echo "FAILED: unsupported CPU $ARCH" >&2
    exit 1
    ;;
esac

PYTHON_URL="${YTJ_PYTHON_STANDALONE_URL:-https://github.com/astral-sh/python-build-standalone/releases/download/${PYTHON_TAG}/cpython-${PYTHON_VERSION}+${PYTHON_TAG}-${PYTHON_TRIPLE}-install_only_stripped.tar.gz}"
FFMPEG_URL="${YTJ_FFMPEG_URL:-$DEFAULT_FFMPEG_URL}"

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
  if command -v curl >/dev/null 2>&1; then
    curl -L --fail --progress-bar -o "$2" "$1" || die "download failed: $1"
  elif command -v wget >/dev/null 2>&1; then
    wget -O "$2" "$1" || die "download failed: $1"
  else
    die "need curl or wget to download: $1"
  fi
}

file_sha256() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  else
    shasum -a 256 "$1" | awk '{print $1}'
  fi
}

python_deps_ok() {
  [[ -x "$PY" ]] || return 1
  PYTHONPATH="$APP_DIR" "$PY" -c "
import faster_whisper, numpy, torch, torchaudio, transformers
from speechbrain.inference.speaker import EncoderClassifier
print('ok')
" >/dev/null 2>&1
}

req_hash() {
  file_sha256 "$REQ"
}

python_matches_arch() {
  [[ -x "$PY" ]] || return 1
  local got
  got="$("$PY" -c "import platform; print(platform.machine())" 2>/dev/null || true)"
  case "$ARCH" in
    x86_64) [[ "$got" == "x86_64" ]] ;;
    aarch64) [[ "$got" == "aarch64" || "$got" == "arm64" ]] ;;
    *) return 1 ;;
  esac
}

install_python() {
  if python_matches_arch; then
    echo "Python already present: $PY ($ARCH)"
    return 0
  fi
  if [[ -x "$PY" ]]; then
    echo "Existing Python is wrong architecture; re-downloading for $ARCH."
    rm -rf "$PY_DIR"
  fi
  progress 8 "下載 Python ${PYTHON_VERSION}（${ARCH_LABEL}）"
  local tmp tgz
  tmp="$(mktemp -d "${TMPDIR:-/tmp}/ytj-python.XXXXXX")"
  tgz="$tmp/python-standalone.tar.gz"
  echo "Downloading CPython standalone $ARCH …"
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
  [[ -x "$PY" ]] || die "python3 missing: $PY"
  python_matches_arch || die "python3 architecture mismatch (want $ARCH)"
  echo "Python ready: $PY"
}

ensure_pip() {
  progress 20 "安裝 pip"
  if ! "$PY" -m pip --version >/dev/null 2>&1; then
    "$PY" -m ensurepip --upgrade || die "ensurepip failed"
  fi
  "$PY" -m pip install --upgrade pip setuptools wheel || die "pip bootstrap failed"
}

install_ffmpeg() {
  if [[ -x "$FFMPEG" ]] && "$FFMPEG" -version >/dev/null 2>&1; then
    echo "ffmpeg already present: $FFMPEG"
    return 0
  fi
  if [[ -x "$FFMPEG" ]]; then
    echo "Existing ffmpeg cannot run on $ARCH; re-downloading."
    rm -f "$FFMPEG"
  fi
  if command -v ffmpeg >/dev/null 2>&1; then
    echo "Using system ffmpeg: $(command -v ffmpeg)"
    return 0
  fi
  progress 25 "下載 ffmpeg（靜態組建，$ARCH）"
  mkdir -p "$BIN_DIR"
  local tmp archive
  tmp="$(mktemp -d "${TMPDIR:-/tmp}/ytj-ffmpeg.XXXXXX")"
  archive="$tmp/ffmpeg.tar.xz"
  echo "Downloading ffmpeg $FFMPEG_SLUG …"
  echo "  $FFMPEG_URL"
  if command -v curl >/dev/null 2>&1; then
    curl -L --fail --progress-bar -o "$archive" "$FFMPEG_URL" || die "ffmpeg download failed. Debian/Ubuntu: sudo apt install ffmpeg — then run yingtingjun again."
  elif command -v wget >/dev/null 2>&1; then
    wget -O "$archive" "$FFMPEG_URL" || die "ffmpeg download failed. Debian/Ubuntu: sudo apt install ffmpeg — then run yingtingjun again."
  else
    die "need curl or wget to download ffmpeg"
  fi
  progress 32 "解壓 ffmpeg"
  mkdir -p "$tmp/out"
  if ! tar -xJf "$archive" -C "$tmp/out" 2>/dev/null; then
    PYTHONPATH="$APP_DIR" "$PY" -c "
import tarfile, sys
from pathlib import Path
src, dest = Path(sys.argv[1]), Path(sys.argv[2])
with tarfile.open(src) as tf:
    tf.extractall(dest, filter='data')
" "$archive" "$tmp/out" || die "ffmpeg extract failed"
  fi
  local src
  src="$(find "$tmp/out" -type f -name ffmpeg -print -quit || true)"
  if [[ -z "$src" ]]; then
    rm -rf "$tmp"
    die "ffmpeg binary missing after extract"
  fi
  cp "$src" "$FFMPEG"
  chmod +x "$FFMPEG"
  rm -rf "$tmp"
  echo "Installed: $FFMPEG"
}

extract_zip() {
  local zip="$1"
  local dest="$2"
  mkdir -p "$dest"
  if command -v unzip >/dev/null 2>&1; then
    unzip -q -o "$zip" -d "$dest"
    return 0
  fi
  PYTHONPATH="$APP_DIR" "$PY" -c "
import zipfile, sys
from pathlib import Path
src, dest = Path(sys.argv[1]), Path(sys.argv[2])
dest.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(src) as zf:
    zf.extractall(dest)
" "$zip" "$dest" || die "zip extract failed: $zip"
}

install_ecdict() {
  if [[ -f "$ECDICT" ]]; then
    echo "ECDICT already present: $ECDICT"
    return 0
  fi
  progress 40 "下載英中詞典 ECDICT"
  mkdir -p "$MODELS"
  local tmp zip db
  tmp="$(mktemp -d "${TMPDIR:-/tmp}/ytj-ecdict.XXXXXX")"
  zip="$tmp/ecdict-sqlite.zip"
  echo "Downloading ECDICT SQLite (~200 MB zip) …"
  download "$ECDICT_URL" "$zip"
  progress 50 "解壓詞典"
  extract_zip "$zip" "$tmp/out"
  db="$(find "$tmp/out" -type f \( -name '*.db' -o -name '*.sqlite' -o -name '*.sqlite3' \) -print -quit || true)"
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
  progress 58 "安裝 Python 套件（torch / faster-whisper，較久）"
  echo "Python: $PY"
  "$PY" -m pip --version >/dev/null || die "pip is not available"
  progress 65 "pip install -r requirements-linux.txt"
  PYTHONPATH="$APP_DIR" "$PY" -m pip install -r "$REQ" || die "pip install failed"
  if ! python_deps_ok; then
    PYTHONPATH="$APP_DIR" "$PY" -c "
import faster_whisper, numpy, torch, torchaudio, transformers
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
  hash="$(file_sha256 "$REQ_YT")"
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
echo "CPU:           $ARCH"
echo "Log:           $LOG"
install_python
ensure_pip
install_ffmpeg
install_ecdict
install_packages
install_youtube_tools
install_ecapa
progress 100 "完成"
echo
echo "All runtime extras ready."
echo "Log: $LOG"
