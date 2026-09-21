# Yingtingjun

**Turn real-life English you could not catch into private bilingual listening lessons.**

Yingtingjun is a local-first listening tool for macOS, Windows, and Linux. Bring your own real recordings, and it turns them into replayable bilingual study material with speaker labels, timestamps, notes, dictionary lookup, and partial re-transcription.

[繁體中文說明](README.md) · [Contributing](CONTRIBUTING.md) / [如何參與](CONTRIBUTING.zh-TW.md) · [Installation](docs/installation.md) / [安裝說明](docs/installation.zh-TW.md) · [Development](docs/development.md) / [開發說明](docs/development.zh-TW.md) · [Troubleshooting](docs/troubleshooting.md) / [疑難排解](docs/troubleshooting.zh-TW.md)

## How It Works

1. On first launch, a welcome card lets you open the bundled demo lesson, start from YouTube, or import a local recording.
2. Import any real English conversation recording, or paste a YouTube URL via **Import → YouTube** in the player.
3. Detect English, transcribe, and translate locally (YouTube videos prefer Chinese captions when available; English captions can use a faster caption path).
4. Review in **learning mode** while replaying, shadowing, taking notes, and looking up words. Turn on **Advanced** for partial re-transcription or export.

## Why It Feels Different

Most listening tools are built around generic content. Yingtingjun is for the English you actually run into in daily life: work calls, casual conversations, interviews, meetings, and voice notes.

- Your files stay on your computer. Packaged installs keep transcripts and notes in `Documents/Yingtingjun/data/`.
- The output is designed for repeated listening, not just transcription.
- The player defaults to learning mode, with an onboarding tour and a public-domain demo lesson.

## Product View

![Yingtingjun browser player screenshot](docs/assets/player-screenshot.png)

Browser player with bilingual transcript, speaker turns, notes, and click-to-lookup dictionary. Learning mode is the default.

## Platforms

Slim installers are available for all three platforms from the [latest GitHub Release](https://github.com/caculus/yingtingjun/releases/latest). They do not bundle Python or models; the runtime is downloaded on first launch or install. Expect about **6–8 GB** of additional disk space for Python, libraries, Whisper, translation, speaker models, and the dictionary.

| Platform | Package | ASR / diarization |
| --- | --- | --- |
| macOS Apple Silicon | `Yingtingjun-macos-arm64.dmg` | MLX Whisper + speakrs -> ECAPA |
| Windows 10/11 x64 | `Yingtingjun-Setup-x64.exe` | faster-whisper + ECAPA |
| Linux x86_64 / ARM64 | `Yingtingjun-linux.tar.gz` | faster-whisper + ECAPA |

## Core Features

- Local-first transcription and translation
- **YouTube import** (built-in; dev installs need `pip install -r requirements-youtube.txt`; slim installers install `yt-dlp` on first launch; **prefers Chinese captions** when available; English caption path **aligns highlight timings with Whisper by default** while keeping caption text)
- Speaker labels, punctuation, timestamps, and word timing
- Browser player for shadowing and review with adjustable speed (0.5×–2.0×)
- **Learning mode** (default; hides engineering controls; toggle **Advanced**) and an **onboarding tour**
- Bundled public-domain **demo lesson** (Aesop) that opens on first launch
- Click-to-lookup dictionary with local ECDICT first
- Per-recording notes with CSV export
- **Export bilingual transcript** as `.txt` / `.md` / `.html` (turn on **Advanced**, then **Open ▾ → Export**; optional speakers / timestamps)
- Partial re-transcription for only the problematic range

## Quick Start

Use the installer that matches your platform if you are a normal user. If you are developing from source, start in the docs:

- [Installation](docs/installation.md) / [安裝說明](docs/installation.zh-TW.md)
- [Development](docs/development.md) / [開發說明](docs/development.zh-TW.md)
- [Troubleshooting](docs/troubleshooting.md) / [疑難排解](docs/troubleshooting.zh-TW.md)
- [Contributing](CONTRIBUTING.md) / [如何參與](CONTRIBUTING.zh-TW.md)

### First launch

After install, the browser opens `http://127.0.0.1:8765/`. The welcome card can:

- **Open the demo lesson** (Aesop public-domain fable; no transcription needed)
- **Start from YouTube** or **import a recording**
- **Show the tour** (later, click **?** in the top right to replay; with a transcript open it shows the lesson tour)

Learning mode is the default (partial re-transcription, CSV export, and similar controls stay hidden). Turn on **Advanced** next to the title when you need them.

### YouTube import (optional)

In the player: **Import ▾ → YouTube…** (first menu item; local files are **Local recording…**): paste a URL, optionally rename the lesson, then load the bilingual transcript automatically. Chinese captions are preferred when present; the English caption path **aligns highlight timings with Whisper by default**.  
For development, run `pip install -r requirements-youtube.txt` (or `brew install yt-dlp`).  
YouTube is an input source, not the product focus; the core workflow remains real-life recordings you bring in.

## Roadmap

### Now

- Keep the three-platform slim installers stable
- Make it easy for newcomers to report bugs, improve docs, and join in

### Next

- Search and filter in the learning-notes sidebar ([#4](https://github.com/caculus/yingtingjun/issues/4))
- Lightweight `windows-latest` CI for unit tests ([#3](https://github.com/caculus/yingtingjun/issues/3))
- Phrase lookup in the dictionary overlay ([#5](https://github.com/caculus/yingtingjun/issues/5))

### Exploring

- Linux `.deb` / AppImage ([#6](https://github.com/caculus/yingtingjun/issues/6))
- macOS signing and notarization
- A short demo GIF or video
- Cross-recording vocabulary notebook ([#8](https://github.com/caculus/yingtingjun/issues/8))
- Highlight Whisper repetition loops ([#7](https://github.com/caculus/yingtingjun/issues/7))

## License

The source code is released under the [MIT License](LICENSE). Runtime-downloaded models and dictionaries keep their own upstream licenses.
