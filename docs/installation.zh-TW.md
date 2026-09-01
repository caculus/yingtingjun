# 安裝說明

本專案同時支援一般使用者與開發者。

- 如果你想用最少設定開始使用，請安裝對應平台的安裝包。
- 如果你想從原始碼開發，請使用你平台對應的開發安裝流程。

[English README](../README.md) · [繁中 README](../README.zh-TW.md) · [Development](development.md) / [開發說明](development.zh-TW.md) · [Troubleshooting](troubleshooting.md) / [疑難排解](troubleshooting.zh-TW.md)

## 系統需求

- 從原始碼開發時需要 Python `3.9+`
- 第一次啟動時需要穩定網路以下載執行階段與模型
- 需要數 GB 可用磁碟空間給 Whisper、翻譯與話者模型
- 可選的本機詞典：`models/ecdict.db`

## 一般使用者安裝

### macOS Apple Silicon

- 使用 `Yingtingjun-macos-arm64.dmg`
- 把 `Yingtingjun.app` 拖到 `Applications`
- 因為 App 尚未簽名，第一次請用右鍵 -> 打開
- 如果 macOS 提示 App 無法打開或已損壞，先打開`終端機`(Terminal) 執行：

```bash
xattr -cr /Applications/Yingtingjun.app
```

- 執行後再回 Finder 用右鍵 -> 打開一次
- 第一次成功啟動會打開 Terminal，並下載 Python、套件、ECDICT 與 ECAPA
- 接著瀏覽器會開啟 `http://127.0.0.1:8765/`
- 資料會保留在 `~/Documents/Yingtingjun/data/`
- 執行階段檔案位於 `~/Library/Application Support/Yingtingjun/`



### Windows 10/11 x64

- 使用 `Yingtingjun-Setup-x64.exe`
- 安裝程式會下載 embedded Python、ffmpeg、套件、ECDICT 與 ECAPA
- 資料會留在安裝目錄下的 `data\`
- Windows on ARM 仍應使用 AMD64 版本



### Linux x86_64 / ARM64

- 使用 `Yingtingjun-linux.tar.gz`
- 解壓後執行 `bash install.sh`
- 第一次啟動會下載 standalone Python、需要時的 ffmpeg、套件、ECDICT 與 ECAPA
- 資料會保存在 `~/Documents/Yingtingjun/data/`
- 執行階段檔案位於 `~/.local/share/yingtingjun/`



## 開發安裝



### macOS

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python transcribe.py --pick
python serve_player.py
```

可選額外安裝：

- `python -m pip install -r requirements-dev.txt`
- `python -m pip install -r requirements-youtube.txt`（播放器內 YouTube 匯入）
- `bash scripts/setup_ecdict.sh`
- `bash scripts/build_speakrs.sh`，僅限 Apple Silicon



### Windows

請使用 `requirements-windows.txt`，不要使用 `requirements.txt`。

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
powershell -ExecutionPolicy Bypass -File scripts\install_windows.ps1
python transcribe.py "meeting.m4a"
python serve_player.py
```

注意：

- 在 Windows on ARM 上不要安裝 ARM64 Python
- 不要為這個專案強制安裝 `torchaudio`



### Linux

請使用 `requirements-linux.txt`，不要使用 `requirements.txt` 或 `requirements-windows.txt`。

```bash
python3 -m venv .venv
source .venv/bin/activate
bash scripts/install_linux.sh
python transcribe.py "meeting.m4a"
python serve_player.py
```

注意：

- 可以的話，優先用套件管理器安裝 `ffmpeg`
- `--pick` 可能需要 `tkinter`

## YouTube 匯入（選用）

播放器 **匯入 ▾ → YouTube…** 需要本機已安裝 [yt-dlp](https://github.com/yt-dlp/yt-dlp)：

```bash
python -m pip install -r requirements-youtube.txt
# 或：brew install yt-dlp
```

仍需 `ffmpeg`（英聽君轉檔流程通常已具備）。**精簡安裝包**會在首次啟動時透過 `install_runtime` 自動安裝 `yt-dlp`。

## 封裝

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

