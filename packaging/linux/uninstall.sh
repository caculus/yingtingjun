#!/bin/bash
# Remove XDG payload and downloaded runtime (python / models / ffmpeg).
# User transcripts and notes under Documents/Yingtingjun/data/ are always kept.
set -euo pipefail

documents_dir() {
  if [[ -n "${YTJ_DOCUMENTS:-}" ]]; then
    printf '%s\n' "${YTJ_DOCUMENTS%/}"
    return
  fi
  if command -v xdg-user-dir >/dev/null 2>&1; then
    local p
    p="$(xdg-user-dir DOCUMENTS 2>/dev/null || true)"
    if [[ -n "$p" ]]; then
      printf '%s\n' "${p%/}"
      return
    fi
  fi
  printf '%s\n' "${HOME}/Documents"
}

SUPPORT="${YTJ_SUPPORT:-${XDG_DATA_HOME:-$HOME/.local/share}/yingtingjun}"
BIN_LINK="${XDG_BIN_HOME:-$HOME/.local/bin}/yingtingjun"
DESKTOP="${XDG_DATA_HOME:-$HOME/.local/share}/applications/yingtingjun.desktop"
DATA="${YTJ_DATA:-$(documents_dir)/Yingtingjun/data}"
LOG="$SUPPORT/install-runtime.log"

printf '\033]0;卸載英聽君\007'
echo "======================================"
echo "  英聽君 — 卸載"
echo "======================================"
echo
echo "將移除："
echo "  • $SUPPORT"
echo "  • $BIN_LINK"
echo "  • $DESKTOP"
echo
echo "將保留文稿與筆記："
echo "  • $DATA"
echo
echo "若英聽君正在執行，請先在終端機按 Ctrl+C 結束。"
echo

read -r -p "確定要卸載？[y/N] " confirm
if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
  echo "已取消。"
  exit 0
fi

removed=0

if [[ -L "$BIN_LINK" || -f "$BIN_LINK" ]]; then
  rm -f "$BIN_LINK"
  echo "已刪除：$BIN_LINK"
  removed=1
else
  echo "（未找到）$BIN_LINK"
fi

if [[ -f "$DESKTOP" ]]; then
  rm -f "$DESKTOP"
  echo "已刪除：$DESKTOP"
  removed=1
else
  echo "（未找到）$DESKTOP"
fi

if [[ -d "$SUPPORT" ]]; then
  rm -rf "$SUPPORT"
  echo "已刪除：$SUPPORT"
  removed=1
else
  echo "（未找到）$SUPPORT"
  if [[ -f "$LOG" ]]; then
    rm -f "$LOG"
  fi
fi

echo "已保留：$DATA"

desktop_dir="$(dirname "$DESKTOP")"
if command -v update-desktop-database >/dev/null 2>&1 && [[ -d "$desktop_dir" ]]; then
  update-desktop-database "$desktop_dir" >/dev/null 2>&1 || true
fi

echo
if [[ "$removed" -eq 1 ]]; then
  echo "卸載完成。"
else
  echo "沒有找到需要移除的項目（可能已卸載過）。"
fi
echo "解壓出來的資料夾若還在，請自行刪除。"
