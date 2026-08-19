# Troubleshooting

[English README](../README.md) · [繁中 README](../README.zh-TW.md) · [Installation](installation.md) / [安裝說明](installation.zh-TW.md) · [Development](development.md) / [開發說明](development.zh-TW.md)

## macOS

### The app says it is damaged or cannot be opened

```bash
xattr -cr /Applications/Yingtingjun.app
```

Then open it again with right click -> Open.

### Intel Mac cannot use the installer

The packaged macOS app is Apple Silicon only. Use the source-based development flow instead.

### `speakrs` is missing

That is acceptable. The app will fall back to ECAPA when `speakrs` is not available.

## Windows

### `torch` shows `from versions: none`

You are likely using the wrong Python architecture. Reinstall AMD64 Python, delete `.venv`, then recreate the environment.

### `torchaudio` crashes or reports missing entry points

Windows should not force-install `torchaudio` for this project. Use `requirements-windows.txt` and the provided installer script.

### Windows on ARM behaves strangely

Use AMD64 Python under emulation, not ARM64 Python.

## Linux

### `ffmpeg` download fails

Install `ffmpeg` from your package manager first, then run the app again.

### The installer says only `x86_64` is supported

You may be using an older tarball. Rebuild or redownload the package that includes the updated Linux packaging scripts.

### Alpine or musl-based distro

Use the development path instead of the packaged installer flow.

## Transcription / Translation

### Whisper or translation output looks wrong in only one segment

Use partial re-transcription instead of rerunning the whole file.

### A known translation hallucination appears

Old transcripts may still contain known NLLB artifacts. Re-run the cleanup or regenerate the affected segments.

### Forced speaker count is needed

Use the ECAPA path when forcing the number of speakers. `speakrs` does not support forced speaker counts.

## Player

### The page does not reflect recent changes

Hard-refresh the browser after changing code or transcript files.

### Port `8765` is already in use

The app is expected to reopen the existing page instead of starting a second server.

## Still Stuck

When reporting an issue, include:

- platform and CPU architecture
- installer or source-based setup
- exact command run
- relevant error output
- whether the failure happens during install, transcription, or playback
