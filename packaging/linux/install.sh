#!/bin/bash
# Copy slim payload into XDG data dir, install a .desktop launcher and ~/.local/bin symlink.
# No root required. Runtime Python / models are downloaded on first launch.
set -euo pipefail

resolve_self() {
  local src="$0"
  while [[ -L "$src" ]]; do
    local dir
    dir="$(cd "$(dirname "$src")" && pwd)"
    src="$(readlink "$src")"
    [[ "$src" == /* ]] || src="$dir/$src"
  done
  cd "$(dirname "$src")" && pwd
}

SRC="$(resolve_self)"
PREFIX="${YTJ_SUPPORT:-${XDG_DATA_HOME:-$HOME/.local/share}/yingtingjun}"
BIN_DIR="${XDG_BIN_HOME:-$HOME/.local/bin}"
DESKTOP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"

die() {
  echo "$*" >&2
  exit 1
}

if [[ "$(uname -s)" != "Linux" ]]; then
  die "install.sh 只能在 Linux 上執行。"
fi
if [[ ! -f "$SRC/arch.sh" ]]; then
  die "找不到 arch.sh。請用新版 Yingtingjun-linux.tar.gz 重新解壓後再執行。"
fi
# shellcheck source=arch.sh
source "$SRC/arch.sh"
ARCH="$(ytj_require_linux_arch)" || die "僅支援 x86_64 與 ARM64（aarch64）。其他架構請用 README「Linux 開發安裝」。"
if [[ ! -f "$SRC/app/serve_player.py" ]]; then
  die "找不到 app/serve_player.py（請在解壓後的 Yingtingjun 目錄執行）。"
fi

mkdir -p "$PREFIX" "$BIN_DIR" "$DESKTOP_DIR"

if [[ "$SRC" != "$PREFIX" ]]; then
  echo "複製到 $PREFIX"
  cp "$SRC/yingtingjun" "$PREFIX/yingtingjun"
  cp "$SRC/install_runtime.sh" "$PREFIX/install_runtime.sh"
  cp "$SRC/arch.sh" "$PREFIX/arch.sh"
  cp "$SRC/uninstall.sh" "$PREFIX/uninstall.sh"
  cp "$SRC/requirements-linux.txt" "$PREFIX/requirements-linux.txt"
  if [[ -f "$SRC/LICENSE" ]]; then
    cp "$SRC/LICENSE" "$PREFIX/LICENSE"
  fi
  if [[ -f "$SRC/yingtingjun.desktop" ]]; then
    cp "$SRC/yingtingjun.desktop" "$PREFIX/yingtingjun.desktop"
  fi
  rm -rf "$PREFIX/app"
  cp -a "$SRC/app" "$PREFIX/app"
fi

chmod +x "$PREFIX/yingtingjun" "$PREFIX/install_runtime.sh" "$PREFIX/uninstall.sh"

ln -sfn "$PREFIX/yingtingjun" "$BIN_DIR/yingtingjun"

cat >"$DESKTOP_DIR/yingtingjun.desktop" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=英聽君
Name[en]=Yingtingjun
Comment=本機英文聽力播放器
Comment[en]=Local English listening player
Exec=env YTJ_IN_TERMINAL=1 "$PREFIX/yingtingjun"
Path=$PREFIX
Terminal=true
Categories=AudioVideo;Education;
StartupNotify=true
StartupWMClass=yingtingjun
EOF
chmod +x "$DESKTOP_DIR/yingtingjun.desktop"
if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$DESKTOP_DIR" >/dev/null 2>&1 || true
fi

echo
echo "已安裝英聽君（無需管理員；架構 $ARCH）。"
echo "  程式：$PREFIX"
echo "  指令：$BIN_DIR/yingtingjun"
echo "  選單：$DESKTOP_DIR/yingtingjun.desktop"
echo
echo "第一次啟動會連網下載 Python／ffmpeg／詞典／模型。"
echo "文稿與筆記：$HOME/Documents/Yingtingjun/data/"
echo
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
  echo "若指令找不到，把下面這行加進 ~/.profile 後重新登入："
  echo "  export PATH=\"$BIN_DIR:\$PATH\""
  echo
fi
echo "啟動：yingtingjun"
echo "卸載：bash \"$PREFIX/uninstall.sh\""
