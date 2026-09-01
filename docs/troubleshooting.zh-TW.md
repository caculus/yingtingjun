# 疑難排解

[English README](../README.md) · [繁中 README](../README.zh-TW.md) · [Installation](installation.md) / [安裝說明](installation.zh-TW.md) · [Development](development.md) / [開發說明](development.zh-TW.md)

## macOS

### App 顯示已損壞或無法打開

```bash
xattr -cr /Applications/Yingtingjun.app
```

執行後再回 Finder 用右鍵 -> 打開。

### Intel Mac 無法使用安裝包

目前封裝好的 macOS App 只支援 Apple Silicon。Intel Mac 請改用原始碼開發安裝流程。

### 找不到 `speakrs`

這是可以接受的。當 `speakrs` 不可用時，程式會回退到 ECAPA。

## Windows

### `torch` 顯示 `from versions: none`

通常是 Python 架構裝錯了。請重新安裝 AMD64 Python、刪除 `.venv`，然後重建環境。

### `torchaudio` 當掉或回報缺少 entry points

這個專案在 Windows 上不應強制安裝 `torchaudio`。請改用 `requirements-windows.txt` 與提供的安裝腳本。

### 安裝視窗出現 `ERROR: pip's dependency resolver` / `requires torchaudio`

這不是失敗。`speechbrain` 宣告依賴 `torchaudio`，但 Windows 安裝包刻意不安裝它（改用內建 stub）。後面若出現 `Python packages ready.`、`yt-dlp ready.` 或 `All runtime extras ready.` 就代表成功。`Scripts which is not on PATH` 同樣可忽略。

### Windows on ARM 表現異常

請使用模擬執行下的 AMD64 Python，不要使用 ARM64 Python。

### 錄音不在安裝目錄裡

Windows 安裝包把文稿與筆記放在 `%USERPROFILE%\Documents\Yingtingjun\data\`，不在 `%LOCALAPPDATA%\Yingtingjun\`。Python、ffmpeg、模型才在安裝目錄。

### 卸載後 `%LOCALAPPDATA%\Yingtingjun` 還在

舊版安裝程式只刪 Setup 複製進去的檔案，事後下載的 Python、ffmpeg、模型會留下。現在的卸載會先把殘留的 `{app}\data` 複製到「文件」，再刪除安裝目錄。若舊版已經卸載完，請自行刪除 `%LOCALAPPDATA%\Yingtingjun`。請保留 `%USERPROFILE%\Documents\Yingtingjun\data\`。

## Linux

### `ffmpeg` 下載失敗

先用你的套件管理器安裝 `ffmpeg`，再重新執行程式。

### 安裝器顯示只支援 `x86_64`

你可能使用了較舊的 tarball。請重新 build 或重新下載包含新版 Linux 封裝腳本的套件。

### Alpine 或 musl-based 發行版

請改用原始碼開發安裝流程，不要使用封裝安裝流程。

## 轉寫 / 翻譯

### 只有某一段 Whisper 或翻譯結果不對

請使用局部重辨，而不是整支錄音全部重跑。

### 出現已知翻譯幻覺

舊逐字稿可能仍含已知的 NLLB 異常輸出。請重新執行清理步驟，或只重生受影響的區段。

### 需要強制指定說話者人數

請使用 ECAPA 路徑。`speakrs` 不支援強制指定說話者數量。

## 播放器

### 頁面沒有反映最新變更

修改程式碼或逐字稿檔案後，請對瀏覽器做硬重新整理。

### `8765` 埠已被占用

程式預期會重新打開既有頁面，而不是再啟動第二個伺服器。

## YouTube 匯入

### 找不到 yt-dlp

請安裝：`pip install -r requirements-youtube.txt` 或 `brew install yt-dlp`。

### 匯入失敗或影片無法取得

常見原因：地區限制、需登入、直播、播放清單連結（請貼單支影片 URL）。錯誤訊息會顯示在匯入進度 log。

### 自動字幕品質差

可改用 **whisper** 模式強制轉寫，或在英聽君內用局部重辨修正單句。

## 還是卡住？

回報問題時請附上：

- 平台與 CPU 架構
- 使用的是安裝包還是原始碼開發安裝
- 實際執行的指令
- 相關錯誤輸出
- 問題發生在安裝、轉寫還是播放階段
