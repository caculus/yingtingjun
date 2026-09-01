#!/bin/bash
# Build dist/Yingtingjun-linux.tar.gz (launch contract).
# Slim payload: app + launcher + bootstrap. Downloaded at first launch:
#   CPython standalone (x86_64 or aarch64), ffmpeg (if missing), pip wheels, ECDICT, ECAPA.
#   bash packaging/linux/build_portable.sh
set -euo pipefail

for arg in "$@"; do
  case "$arg" in
    -h|--help)
      echo "Usage: bash packaging/linux/build_portable.sh"
      exit 0
      ;;
    *)
      echo "Unknown option: $arg" >&2
      exit 1
      ;;
  esac
done

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PACK="$(cd "$(dirname "$0")" && pwd)"
DIST_ROOT="$ROOT/dist"
# Do not use dist/Yingtingjun — that is the Windows portable folder.
STAGE_ROOT="$DIST_ROOT/linux-stage"
STAGE="$STAGE_ROOT/Yingtingjun"
TGZ="$DIST_ROOT/Yingtingjun-linux.tar.gz"
APP_DIR="$STAGE/app"

step() {
  printf '\n== %s ==\n' "$1"
}

step "Clean $STAGE_ROOT"
rm -rf "$STAGE_ROOT"
mkdir -p "$APP_DIR/player"

step "Copy application (no Python / models / ffmpeg)"
APP_FILES=(
  transcribe.py
  serve_player.py
  stem_utils.py
  asr_backend.py
  audio_convert.py
  audio_resample.py
  platform_runtime.py
  progress_log.py
  torchaudio_compat.py
)
for name in "${APP_FILES[@]}"; do
  cp "$ROOT/$name" "$APP_DIR/$name"
done
if command -v ditto >/dev/null 2>&1; then
  ditto "$ROOT/player" "$APP_DIR/player"
  ditto "$ROOT/yt_decoder" "$APP_DIR/yt_decoder"
else
  cp -a "$ROOT/player/." "$APP_DIR/player/"
  cp -a "$ROOT/yt_decoder/." "$APP_DIR/yt_decoder/"
fi
cp "$ROOT/requirements-linux.txt" "$STAGE/requirements-linux.txt"
cp "$ROOT/requirements-youtube.txt" "$STAGE/requirements-youtube.txt"
cp "$ROOT/LICENSE" "$STAGE/LICENSE"
cp "$PACK/yingtingjun" "$STAGE/yingtingjun"
cp "$PACK/arch.sh" "$STAGE/arch.sh"
cp "$PACK/install_runtime.sh" "$STAGE/install_runtime.sh"
cp "$PACK/install.sh" "$STAGE/install.sh"
cp "$PACK/uninstall.sh" "$STAGE/uninstall.sh"
cp "$PACK/yingtingjun.desktop" "$STAGE/yingtingjun.desktop"
chmod +x "$STAGE/yingtingjun" "$STAGE/install_runtime.sh" "$STAGE/install.sh" "$STAGE/uninstall.sh"

if [[ ! -f "$APP_DIR/serve_player.py" ]]; then
  echo "app/serve_player.py missing" >&2
  exit 1
fi

cat >"$STAGE/第一次開啟.txt" <<'EOF'
英聽君（Linux x86_64 與 ARM64）

1. 解壓 Yingtingjun-linux.tar.gz
2. 在解壓出的 Yingtingjun 目錄執行：
     bash install.sh
   （不需管理員；會裝到 ~/.local/share/yingtingjun/）
3. 應用程式選單點「英聽君」，或執行 yingtingjun
4. 第一次會在終端機連網下載對應架構的 Python／ffmpeg／詞典／模型（數分鐘）
5. 瀏覽器開啟 http://127.0.0.1:8765/

也可不解壓後直接 ./yingtingjun（便攜）；Python／模型仍下載到
~/.local/share/yingtingjun/。

文稿與筆記在：
~/Documents/Yingtingjun/data/

卸載：
  bash ~/.local/share/yingtingjun/uninstall.sh
  → 刪程式、python/、models/、ffmpeg；文稿保留在「文件／Yingtingjun／data」

支援 x86_64 與 ARM64（aarch64）glibc（如 Ubuntu 22.04+）。Alpine／musl 請用原始碼開發安裝。
EOF

step "Create tarball"
rm -f "$TGZ"
mkdir -p "$DIST_ROOT"
tar -C "$STAGE_ROOT" -czf "$TGZ" Yingtingjun
echo "Portable folder: $STAGE"
echo "Installer: $TGZ"
