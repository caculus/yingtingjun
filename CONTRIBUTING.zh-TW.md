# 如何參與

感謝你幫忙英聽君。

不需要會寫程式也能貢獻。回報 bug、安裝過程的卡住點、改文件、潤飾介面文案、提出學習功能想法，都很有用。

[English](CONTRIBUTING.md)

## 可以幫忙的方向

- 回報 bug，或安裝流程裡讓人卡住的步驟
- 改善文件（`README.zh-TW.md`、`docs/`）
- 翻譯或潤飾播放器介面文案
- 讓安裝流程更清楚、更穩定
- 補不需要真跑 ASR／翻譯模型的測試
- 改善學習功能：筆記、詞典、局部重辨

請**不要**提交個人錄音、文稿、筆記或 `HANDOFF.md`。這些只留本機。

## 回報 bug

請開 GitHub issue，並附上：

- 平台與 CPU 架構（例如 macOS Apple Silicon、Windows x64、Linux ARM64）
- 用的是安裝檔還是從原始碼跑
- 你做了什麼
- 預期結果
- 實際結果
- 相關終端機或播放器日誌

若看起來像已知安裝問題，可先看 [疑難排解](docs/troubleshooting.zh-TW.md)。

## 開發環境

請從這裡開始：

- [安裝說明](docs/installation.zh-TW.md)
- [開發說明](docs/development.zh-TW.md)

重點：

- macOS 用 `requirements.txt`
- Windows 用 `requirements-windows.txt` 與 `scripts/install_windows.ps1`
- Linux 用 `requirements-linux.txt` 與 `scripts/install_linux.sh`
- 不要在 Windows／Linux 編譯 `speakrs`
- 測試保持本機、輕量：`python -m pytest`

## Pull request

- 一次只處理一個 issue
- 盡量跟附近檔案的既有風格一致
- 若改到安裝或封裝行為，請說明你怎麼 smoke test
- 若只改文件或文案，也請在 PR 裡註明

## 語言

Issue、PR 與介面文案都歡迎英文或繁體中文。
