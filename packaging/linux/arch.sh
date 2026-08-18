#!/bin/bash
# Shared Linux CPU arch helper. Sourced by install.sh / yingtingjun / install_runtime.sh.
# Prints x86_64 or aarch64. Empty string = unsupported.

ytj_linux_arch() {
  case "$(uname -m)" in
    x86_64|amd64) printf 'x86_64\n' ;;
    aarch64|arm64) printf 'aarch64\n' ;;
    *) printf '\n' ;;
  esac
}

ytj_require_linux_arch() {
  local arch
  arch="$(ytj_linux_arch)"
  if [[ -z "$arch" ]]; then
    echo "英聽君 Linux 安裝包僅支援 x86_64 與 ARM64（aarch64）。目前是 $(uname -m)。其他架構請用 README「Linux 開發安裝」。" >&2
    return 1
  fi
  printf '%s\n' "$arch"
}
