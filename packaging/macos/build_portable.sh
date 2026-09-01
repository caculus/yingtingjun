#!/bin/bash
# Build dist/Yingtingjun.app (launch contract) and optionally a UDZO dmg.
# Slim payload: app + launcher + bootstrap. Downloaded at first launch:
#   CPython standalone arm64, pip wheels, ECDICT, ECAPA.
#   bash packaging/macos/build_portable.sh
#   bash packaging/macos/build_portable.sh --skip-dmg
#   bash packaging/macos/build_portable.sh --skip-speakrs
set -euo pipefail

SKIP_DMG=0
SKIP_SPEAKRS=0
for arg in "$@"; do
  case "$arg" in
    --skip-dmg) SKIP_DMG=1 ;;
    --skip-speakrs) SKIP_SPEAKRS=1 ;;
    -h|--help)
      echo "Usage: bash packaging/macos/build_portable.sh [--skip-dmg] [--skip-speakrs]"
      exit 0
      ;;
    *)
      echo "Unknown option: $arg" >&2
      exit 1
      ;;
  esac
done

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "macOS packaging must run on macOS." >&2
  exit 1
fi
if [[ "$(uname -m)" != "arm64" ]]; then
  echo "Apple Silicon only (uname -m must be arm64)." >&2
  exit 1
fi

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PACK="$(cd "$(dirname "$0")" && pwd)"
DIST_ROOT="$ROOT/dist"
APP="$DIST_ROOT/Yingtingjun.app"
CONTENTS="$APP/Contents"
MACOS="$CONTENTS/MacOS"
RES="$CONTENTS/Resources"
APP_DIR="$RES/app"

step() {
  printf '\n== %s ==\n' "$1"
}

step "Clean $APP"
rm -rf "$APP"
mkdir -p "$MACOS" "$APP_DIR/player" "$APP_DIR/bin"

step "Copy application (no Python / models)"
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
ditto "$ROOT/player" "$APP_DIR/player"
ditto "$ROOT/yt_decoder" "$APP_DIR/yt_decoder"
cp "$ROOT/requirements.txt" "$RES/requirements.txt"
cp "$ROOT/requirements-youtube.txt" "$RES/requirements-youtube.txt"
cp "$ROOT/LICENSE" "$RES/LICENSE"
cp "$PACK/install_runtime.sh" "$RES/install_runtime.sh"
cp "$PACK/Yingtingjun" "$MACOS/Yingtingjun"
cp "$PACK/Info.plist" "$CONTENTS/Info.plist"
echo -n 'APPL????' >"$CONTENTS/PkgInfo"
chmod +x "$MACOS/Yingtingjun" "$RES/install_runtime.sh"

if [[ ! -f "$APP_DIR/serve_player.py" ]]; then
  echo "app/serve_player.py missing" >&2
  exit 1
fi

if [[ "$SKIP_SPEAKRS" -eq 0 ]]; then
  step "Build speakrs_diarize (CoreML)"
  if [[ -f "$HOME/.cargo/env" ]]; then
    # shellcheck source=/dev/null
    source "$HOME/.cargo/env"
  fi
  if command -v cargo >/dev/null 2>&1; then
    bash "$ROOT/scripts/build_speakrs.sh"
    cp "$ROOT/bin/speakrs_diarize" "$APP_DIR/bin/speakrs_diarize"
    chmod +x "$APP_DIR/bin/speakrs_diarize"
    echo "Bundled speakrs → $APP_DIR/bin/speakrs_diarize"
  elif [[ -x "$ROOT/bin/speakrs_diarize" ]]; then
    echo "cargo not found; using existing bin/speakrs_diarize"
    cp "$ROOT/bin/speakrs_diarize" "$APP_DIR/bin/speakrs_diarize"
    chmod +x "$APP_DIR/bin/speakrs_diarize"
  else
    echo "WARNING: speakrs not bundled (no cargo / bin/speakrs_diarize). Runtime will use ECAPA." >&2
  fi
else
  echo "Skip speakrs (--skip-speakrs)."
fi

step "App bundle ready"
echo "$APP"

if [[ "$SKIP_DMG" -eq 1 ]]; then
  echo "Skip dmg (--skip-dmg)."
  exit 0
fi

step "Create dmg"
STAGE="$DIST_ROOT/dmg-stage"
DMG="$DIST_ROOT/Yingtingjun-macos-arm64.dmg"
rm -rf "$STAGE"
mkdir -p "$STAGE"
ditto "$APP" "$STAGE/Yingtingjun.app"
ln -s /Applications "$STAGE/Applications"
cp "$PACK/Uninstall Yingtingjun.command" "$STAGE/Uninstall Yingtingjun.command"
chmod +x "$STAGE/Uninstall Yingtingjun.command"
cat >"$STAGE/第一次開啟.txt" <<'EOF'
英聽君（Apple Silicon）

1. 把 Yingtingjun 拖到「應用程式」
2. 第一次請右鍵 → 打開（未簽名，系統會詢問）
3. 若出現「無法打開」或「已損壞」，先開 Terminal 執行：
   xattr -cr /Applications/Yingtingjun.app
   執行後再回 Finder 右鍵 → 打開一次
4. 會跳出終端機，連網下載 Python／詞典／模型（數分鐘）
5. 瀏覽器開啟 http://127.0.0.1:8765/

文稿與筆記在「文件」資料夾：
~/Documents/Yingtingjun/data/
（Finder 可能顯示為「文稿／Yingtingjun／data」）

卸載：雙擊「Uninstall Yingtingjun.command」
  → 會刪 App、python/、models/；文稿保留在「文件／Yingtingjun／data」
  （只把 App 丟垃圾桶不會清掉下載的 Python／模型）
EOF
rm -f "$DMG"
hdiutil create -volname "英聽君" -srcfolder "$STAGE" -ov -format UDZO "$DMG"
rm -rf "$STAGE"
echo "Installer: $DMG"
