# 英聽君（yingtingjun）

**把真實生活裡沒聽懂的英文，變成你的私人雙語聽力教材。**

英聽君是給 macOS、Windows、Linux 使用的本機工具。只要匯入你每天真正遇到的英文錄音，它就會把內容整理成可反覆跟讀的雙語教材，並在瀏覽器裡提供同步播放、查詞、記筆記與局部重辨。

[English](README.md) · [如何參與](CONTRIBUTING.zh-TW.md) · [安裝說明](docs/installation.zh-TW.md) · [開發說明](docs/development.zh-TW.md) · [疑難排解](docs/troubleshooting.zh-TW.md)

## 怎麼運作

1. 匯入任意英文對話錄音，或從播放器 **匯入 → YouTube** 貼上影片連結
2. 偵測語言、轉寫英文、加上中文翻譯（YouTube 有英文字幕時可走字幕快徑）
3. 在瀏覽器播放器裡邊聽邊跟讀、查詞、做筆記、修正問題片段

## 它和一般逐字稿工具不同的地方

多數語言學習工具用的是通用教材；英聽君想處理的是你在生活中真的聽不懂的英文，例如日常對話、工作會議、面試、電話與語音訊息。

- 檔案留在你的電腦，不上雲端。安裝包會把文稿與筆記放在「文件／文稿」的 `Yingtingjun/data/`
- 輸出重點是反覆聽與跟讀，不只是逐字稿
- 播放器支援筆記、詞典與局部重辨

## 產品畫面

![英聽君瀏覽器播放器截圖](docs/assets/player-screenshot.png)

瀏覽器播放器可同步顯示雙語文稿、話者分段、學習筆記與點詞查詢。

## 支援平台

三平台都有精簡安裝包，不內含 Python 或模型；首次啟動或安裝時會自動下載執行階段。

| 平台 | 安裝包 | 話者 / ASR |
| --- | --- | --- |
| macOS Apple Silicon | `Yingtingjun-macos-arm64.dmg` | MLX Whisper + speakrs -> ECAPA |
| Windows 10/11 x64 | `Yingtingjun-Setup-x64.exe` | faster-whisper + ECAPA |
| Linux x86_64 / ARM64 | `Yingtingjun-linux.tar.gz` | faster-whisper + ECAPA |

## 核心功能

- 本機轉寫與翻譯
- **YouTube 匯入**（內建；開發環境需 `pip install -r requirements-youtube.txt`；安裝包首次啟動會自動安裝 `yt-dlp`）
- 話者標記、時間戳、詞級時間
- 瀏覽器同步播放與跟讀，支援 0.5×–2.0× 播放速度
- ECDICT 優先的點詞查詢
- 每支錄音獨立的學習筆記與 CSV 匯出
- 只重跑局部區段的局部重辨

## 快速開始

一般使用者直接安裝對應平台的安裝包；如果你是開發者，請從分拆後的文件開始：

- [如何參與](CONTRIBUTING.zh-TW.md)
- [安裝說明](docs/installation.zh-TW.md)
- [開發說明](docs/development.zh-TW.md)
- [疑難排解](docs/troubleshooting.zh-TW.md)

### 從 YouTube 匯入（選用）

播放器內 **匯入 ▾ → YouTube…**：貼 URL、可改教材名稱，完成後自動載入雙語文稿。  
開發環境請先執行 `pip install -r requirements-youtube.txt`（或 `brew install yt-dlp`）。  
YouTube 只是輸入來源之一；產品主線仍是你在真實生活裡遇到的錄音。

## 路線圖

### 現在

- 維持三平台精簡安裝包穩定
- 讓新人容易回報 bug、改文件、一起參與

### 下一步

- 學習筆記側欄搜尋與過濾（[#4](https://github.com/caculus/yingtingjun/issues/4)）
- 輕量的 `windows-latest` 單元測試 CI（[#3](https://github.com/caculus/yingtingjun/issues/3)）
- 詞典浮層支援片語查詢（[#5](https://github.com/caculus/yingtingjun/issues/5)）

### 探索中

- Linux `.deb` / AppImage（[#6](https://github.com/caculus/yingtingjun/issues/6)）
- macOS 簽名與公證
- 短版 Demo GIF 或影片
- 跨錄音生字本（[#8](https://github.com/caculus/yingtingjun/issues/8)）
- 標示 Whisper 迴圈（[#7](https://github.com/caculus/yingtingjun/issues/7)）

## 授權

原始碼採用 [MIT License](LICENSE)。執行時下載的模型與詞典仍各自遵循其上游授權。
