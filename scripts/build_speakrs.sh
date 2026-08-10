#!/usr/bin/env bash
# Build speakrs_diarize into repo bin/ for voice2txt.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CLI="$ROOT/tools/speakrs_cli"
OUT_DIR="$ROOT/bin"
mkdir -p "$OUT_DIR"

if [[ -f "$HOME/.cargo/env" ]]; then
  # shellcheck source=/dev/null
  source "$HOME/.cargo/env"
fi

if ! command -v cargo >/dev/null 2>&1; then
  echo "cargo not found. Install Rust: https://rustup.rs" >&2
  exit 1
fi

echo "Building speakrs_diarize (release, CoreML) …"
(
  cd "$CLI"
  export CARGO_TARGET_DIR="$CLI/target"
  cargo build --release
)
cp -f "$CLI/target/release/speakrs_diarize" "$OUT_DIR/speakrs_diarize"
chmod +x "$OUT_DIR/speakrs_diarize"
echo "Installed → $OUT_DIR/speakrs_diarize"
"$OUT_DIR/speakrs_diarize" --help || true
