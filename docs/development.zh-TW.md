# 開發說明

[English README](../README.md) · [繁中 README](../README.zh-TW.md) · [Contributing](../CONTRIBUTING.md) / [如何參與](../CONTRIBUTING.zh-TW.md) · [Installation](installation.md) / [安裝說明](installation.zh-TW.md) · [Troubleshooting](troubleshooting.md) / [疑難排解](troubleshooting.zh-TW.md)

## 專案結構

- `transcribe.py`：主要轉寫流程
- `serve_player.py`：本機網頁播放器伺服器
- `player/index.html`：瀏覽器 UI
- `platform_runtime.py`：跨平台執行階段契約
- `asr_backend.py`：MLX / faster-whisper 選擇
- `audio_convert.py`：音訊轉檔流程
- `requirements.txt`：macOS 開發依賴
- `requirements-windows.txt`：Windows 依賴
- `requirements-linux.txt`：Linux 依賴
- `packaging/`：各平台安裝包封裝腳本
- `tests/`：不跑真實 ASR 或翻譯的單元測試

## 常用指令

### 本機執行程式

```bash
source .venv/bin/activate
python transcribe.py --pick
python serve_player.py
```

打開 `http://127.0.0.1:8765/`。

### 執行測試

macOS：

```bash
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pytest
```

Linux：

```bash
source .venv/bin/activate
python -m pip install pytest
python -m pytest
```

Windows 請沿用現有 venv 流程，並維持 `requirements-windows.txt` 的依賴分流。

## 重要平台規則

- macOS 開發使用 `requirements.txt`
- Windows 開發使用 `requirements-windows.txt`
- Linux 開發使用 `requirements-linux.txt`
- 不要在 Windows 或 Linux 編譯 `speakrs`
- Windows on ARM 仍應使用 AMD64 Python

## 執行資料目錄

- `workdir/`：正規化後音訊
- `uploads/`：匯入的原始檔
- `output/`：逐字稿與快取
- `notes/`：每支錄音的筆記與詞典快取
- `models/`：本機話者與詞典資產
- `bin/`：本機輔助二進位，例如 `speakrs_diarize`

對於封裝安裝：

- macOS 執行階段資料：`~/Library/Application Support/Yingtingjun/`
- Linux 執行階段資料：`~/.local/share/yingtingjun/`
- 使用者學習資料：`~/Documents/Yingtingjun/data/`

## 產品特有行為

- 若已有 Whisper 快取，會優先重用
- 局部重辨只會對選定區段重跑 ASR 與翻譯
- 局部重辨會保留原本的話者標記，不重新跑 diarization
- 匯入或局部重辨進行中時，播放器可以鎖定操作
- 播放速度可選 0.5×、0.75×、1.0×（預設）、1.25×、1.5× 或 2.0×；同一工作階段內切換錄音時會維持目前速度

## 發佈前優先事項

在更大規模對外推廣前，請優先確認：

1. 公開 README 保持產品導向
2. 各平台安裝說明彼此一致
3. macOS、Linux、Windows 安裝包都已在乾淨機器 smoke test
4. Linux slim packaging 已整理完成並 commit
