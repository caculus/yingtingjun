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

### Installer shows `ERROR: pip's dependency resolver` / `requires torchaudio`

That is not a failed install. `speechbrain` declares a `torchaudio` dependency; the Windows package skips it on purpose and uses a stub. If you later see `Python packages ready.`, `yt-dlp ready.`, or `All runtime extras ready.`, the runtime download succeeded. `Scripts which is not on PATH` warnings can also be ignored.

### Windows on ARM behaves strangely

Use AMD64 Python under emulation, not ARM64 Python.

### Recordings are not under the install folder

Packaged Windows installs store transcripts and notes in `%USERPROFILE%\Documents\Yingtingjun\data\`, not `%LOCALAPPDATA%\Yingtingjun\`. Python, ffmpeg, and models stay in the install directory.

### Uninstall left `%LOCALAPPDATA%\Yingtingjun`

Older installers only removed files copied by Setup. Downloaded Python, ffmpeg, and models were left behind. Current uninstallers delete that directory after copying leftover `{app}\data` into Documents. If an old uninstall already finished, delete `%LOCALAPPDATA%\Yingtingjun` yourself. Keep `%USERPROFILE%\Documents\Yingtingjun\data\`.

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

## YouTube import

### yt-dlp not found

Install with `pip install -r requirements-youtube.txt` or `brew install yt-dlp`.

### Import fails or video unavailable

Common causes: geo block, login required, live stream, or playlist URL (use a single-video link). Check the import progress log for the error code.

### Poor auto-caption quality

Use **whisper** mode to force ASR, or fix individual sentences with partial re-transcription in the player.

## Still Stuck

When reporting an issue, include:

- platform and CPU architecture
- installer or source-based setup
- exact command run
- relevant error output
- whether the failure happens during install, transcription, or playback
