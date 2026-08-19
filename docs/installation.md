# Installation

This project supports both normal users and developers.

- If you want the app with the least setup, use the platform installer.
- If you want to develop from source, use the development setup for your platform.

[English README](../README.md) · [繁中 README](../README.zh-TW.md) · [Development](development.md) / [開發說明](development.zh-TW.md) · [Troubleshooting](troubleshooting.md) / [疑難排解](troubleshooting.zh-TW.md)

## System Requirements

- Python `3.9+` for source-based development
- Stable internet on first launch for model and runtime downloads
- Several GB of free disk space for Whisper, translation, and speaker models
- Optional local dictionary: `models/ecdict.db`

## Normal User Install

### macOS Apple Silicon

- Use `Yingtingjun-macos-arm64.dmg`
- Drag `Yingtingjun.app` into `Applications`
- Open with right click -> Open the first time because the app is unsigned
- If macOS says the app cannot be opened or is damaged, open Terminal and run:

```bash
xattr -cr /Applications/Yingtingjun.app
```

- Then go back to Finder and use right click -> Open again
- The first successful launch opens Terminal and downloads Python, packages, ECDICT, and ECAPA
- The browser then opens `http://127.0.0.1:8765/`
- Data is kept in `~/Documents/Yingtingjun/data/`
- Runtime files live in `~/Library/Application Support/Yingtingjun/`

### Windows 10/11 x64

- Use `Yingtingjun-Setup-x64.exe`
- The installer downloads embedded Python, ffmpeg, packages, ECDICT, and ECAPA
- Data stays under the install directory `data\`
- Windows on ARM should still use the AMD64 build

### Linux x86_64 / ARM64

- Use `Yingtingjun-linux.tar.gz`
- Run `bash install.sh` after extracting
- First launch downloads standalone Python, ffmpeg when needed, packages, ECDICT, and ECAPA
- Data is stored in `~/Documents/Yingtingjun/data/`
- Runtime files live in `~/.local/share/yingtingjun/`

## Development Install

### macOS

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python transcribe.py --pick
python serve_player.py
```

Optional extras:

- `python -m pip install -r requirements-dev.txt`
- `bash scripts/setup_ecdict.sh`
- `bash scripts/build_speakrs.sh` on Apple Silicon only

### Windows

Use `requirements-windows.txt`, not `requirements.txt`.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
powershell -ExecutionPolicy Bypass -File scripts\install_windows.ps1
python transcribe.py "meeting.m4a"
python serve_player.py
```

Notes:

- Do not install ARM64 Python on Windows on ARM for this project
- Do not force-install `torchaudio` on Windows

### Linux

Use `requirements-linux.txt`, not `requirements.txt` or `requirements-windows.txt`.

```bash
python3 -m venv .venv
source .venv/bin/activate
bash scripts/install_linux.sh
python transcribe.py "meeting.m4a"
python serve_player.py
```

Notes:

- Install `ffmpeg` from your package manager when possible
- `--pick` may require `tkinter`

## Packaging

```bash
# macOS
bash packaging/macos/build_portable.sh

# Linux
bash packaging/linux/build_portable.sh
```

```powershell
# Windows
powershell -ExecutionPolicy Bypass -File packaging\windows\build_portable.ps1
```
