#!/bin/bash
# Remove Yingtingjun.app and downloaded runtime (python / models).
# User transcripts and notes under Documents/Yingtingjun/data/ are always kept.
set -euo pipefail

cd "$(dirname "$0")"

documents_dir() {
  if [[ -n "${YTJ_DOCUMENTS:-}" ]]; then
    printf '%s\n' "${YTJ_DOCUMENTS%/}"
    return
  fi
  local p
  p="$(/usr/bin/osascript -e 'tell application "Finder" to get POSIX path of (path to documents folder)' 2>/dev/null | tr -d '\n\r')"
  if [[ -n "$p" ]]; then
    printf '%s\n' "${p%/}"
    return
  fi
  printf '%s\n' "$HOME/Documents"
}

SUPPORT="$HOME/Library/Application Support/Yingtingjun"
APP="/Applications/Yingtingjun.app"
PY="$SUPPORT/python"
MODELS="$SUPPORT/models"
DATA="${YTJ_DATA:-$(documents_dir)/Yingtingjun/data}"
LEGACY_DATA="$SUPPORT/data"
LOG="$SUPPORT/install-runtime.log"

printf '\033]0;卸載英聽君\007'
echo "======================================"
echo "  英聽君 — 卸載"
echo "======================================"
echo
echo "將移除："
echo "  • $APP"
echo "  • $PY"
echo "  • $MODELS"
echo "  • $LOG"
echo
echo "將保留文稿與筆記："
echo "  • $DATA"
if [[ -d "$LEGACY_DATA" && "$LEGACY_DATA" != "$DATA" ]]; then
  echo "  • $LEGACY_DATA（舊版位置）"
fi
echo
echo "若英聽君正在執行，請先在終端機視窗按 Ctrl+C 結束。"
echo

read -r -p "確定要卸載？[y/N] " confirm
if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
  echo "已取消。"
  read -r -p "按 Enter 關閉…" _
  exit 0
fi

removed=0

if [[ -d "$APP" ]]; then
  rm -rf "$APP"
  echo "已刪除：$APP"
  removed=1
else
  echo "（未找到）$APP"
fi

if [[ -d "$PY" ]]; then
  rm -rf "$PY"
  echo "已刪除：$PY"
  removed=1
fi

if [[ -d "$MODELS" ]]; then
  rm -rf "$MODELS"
  echo "已刪除：$MODELS"
  removed=1
fi

if [[ -f "$LOG" ]]; then
  rm -f "$LOG"
  echo "已刪除：$LOG"
fi

echo "已保留：$DATA"
if [[ -d "$LEGACY_DATA" && "$LEGACY_DATA" != "$DATA" ]]; then
  echo "已保留（舊版）：$LEGACY_DATA"
fi

if [[ -d "$SUPPORT" ]]; then
  if [[ -z "$(ls -A "$SUPPORT" 2>/dev/null || true)" ]]; then
    rmdir "$SUPPORT" 2>/dev/null && echo "已刪除空目錄：$SUPPORT" || true
  fi
fi

echo
if [[ "$removed" -eq 1 ]]; then
  echo "卸載完成。"
else
  echo "沒有找到需要移除的項目（可能已卸載過）。"
fi
echo
read -r -p "按 Enter 關閉…" _
