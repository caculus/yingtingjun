#!/usr/bin/env bash
# Download ECDICT SQLite into models/ecdict.db for local EN→ZH lookup.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MODELS="$ROOT/models"
DEST="$MODELS/ecdict.db"
URL="${ECDICT_SQLITE_URL:-https://github.com/skywind3000/ECDICT/releases/download/1.0.28/ecdict-sqlite-28.zip}"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/ecdict.XXXXXX")"

cleanup() { rm -rf "$TMP"; }
trap cleanup EXIT

mkdir -p "$MODELS"

if [[ -f "$DEST" ]]; then
  echo "Already exists: $DEST"
  echo "Remove it first to re-download."
  exit 0
fi

echo "Downloading ECDICT SQLite (large, ~200MB zip) ..."
echo "  $URL"
ZIP="$TMP/ecdict-sqlite.zip"
if command -v curl >/dev/null 2>&1; then
  curl -L --fail --progress-bar -o "$ZIP" "$URL"
elif command -v wget >/dev/null 2>&1; then
  wget -O "$ZIP" "$URL"
else
  echo "Need curl or wget" >&2
  exit 1
fi

echo "Extracting ..."
unzip -q -o "$ZIP" -d "$TMP/out"

# Zip may contain Chinese filenames; find any .db
DB_SRC="$(find "$TMP/out" -type f \( -name '*.db' -o -name '*.sqlite' -o -name '*.sqlite3' \) | head -n 1 || true)"
if [[ -z "$DB_SRC" ]]; then
  echo "No .db found inside zip. Contents:" >&2
  find "$TMP/out" -type f | head -n 40 >&2
  exit 1
fi

cp "$DB_SRC" "$DEST"
echo "Installed: $DEST"
echo "Size: $(du -h "$DEST" | awk '{print $1}')"
echo "Done. Restart serve_player.py to use ECDICT-first dictionary lookup."
