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

### Windows on ARM 表現異常

請使用模擬執行下的 AMD64 Python，不要使用 ARM64 Python。

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

## 還是卡住？

回報問題時請附上：

- 平台與 CPU 架構
- 使用的是安裝包還是原始碼開發安裝
- 實際執行的指令
- 相關錯誤輸出
- 問題發生在安裝、轉寫還是播放階段
