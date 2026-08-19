# Development

[English README](../README.md) · [繁中 README](../README.zh-TW.md) · [Installation](installation.md) / [安裝說明](installation.zh-TW.md) · [Troubleshooting](troubleshooting.md) / [疑難排解](troubleshooting.zh-TW.md)

## Project Structure

- `transcribe.py`: main transcription pipeline
- `serve_player.py`: local web app server
- `player/index.html`: browser UI
- `platform_runtime.py`: cross-platform runtime contract
- `asr_backend.py`: MLX / faster-whisper selection
- `audio_convert.py`: audio conversion pipeline
- `requirements.txt`: macOS development dependencies
- `requirements-windows.txt`: Windows dependencies
- `requirements-linux.txt`: Linux dependencies
- `packaging/`: platform installer packaging scripts
- `tests/`: unit tests without real ASR or translation runs

## Common Commands

### Run the app locally

```bash
source .venv/bin/activate
python transcribe.py --pick
python serve_player.py
```

Open `http://127.0.0.1:8765/`.

### Run tests

On macOS:

```bash
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pytest
```

On Linux:

```bash
source .venv/bin/activate
python -m pip install pytest
python -m pytest
```

For Windows, follow the existing venv flow and keep the dependency split with `requirements-windows.txt`.

## Important Platform Rules

- macOS development uses `requirements.txt`
- Windows development uses `requirements-windows.txt`
- Linux development uses `requirements-linux.txt`
- Do not compile `speakrs` on Windows or Linux
- Windows on ARM should still use AMD64 Python

## Runtime Data Layout

- `workdir/`: normalized audio
- `uploads/`: imported original files
- `output/`: transcripts and caches
- `notes/`: per-recording notes and dictionary cache
- `models/`: local speaker and dictionary assets
- `bin/`: local helper binaries such as `speakrs_diarize`

For packaged installs:

- macOS runtime data: `~/Library/Application Support/Yingtingjun/`
- Linux runtime data: `~/.local/share/yingtingjun/`
- User study data: `~/Documents/Yingtingjun/data/`

## Product-Specific Behaviors

- Existing Whisper caches are reused when available
- Partial re-transcription only reruns ASR and translation for a selected range
- Speaker labels are preserved during partial re-transcription instead of re-running diarization
- The player can lock actions while import or re-transcription is running

## Release-Facing Priorities

Before wider promotion, keep these checked:

1. The public README stays product-first
2. Installer instructions stay consistent across all platforms
3. macOS, Linux, and Windows installers are smoke-tested on clean machines
4. Linux slim packaging is finalized and committed
