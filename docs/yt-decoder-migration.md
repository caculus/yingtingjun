# yt-decoder 遷移說明（給 GitHub Archive 用）

> 英听君已内建 YouTube 匯入（`匯入 ▾ → YouTube…`）。確認 yingtingjun 發版後，可將 [caculus/yt-decoder](https://github.com/caculus/yt-decoder) Archive。

## 建議步驟

1. 在 yt-decoder repo 打 tag：`v0.3.0-standalone`
2. 將 README 頂部改為下列內容
3. GitHub → Settings → **Archive this repository**

## README 頂部範本（繁中）

```markdown
# yt-decoder（已併入英聽君）

> **2026-09 起**：YouTube 匯入已內建於 [英聽君 yingtingjun](https://github.com/caculus/yingtingjun)。  
> 本 repo **不再維護**；請安裝最新版英聽君，在播放器使用 **匯入 ▾ → YouTube…**。

## 歷史

本 repo 為英聽君 companion 原型（M0–M3a），產出英聽君相容的 `output/*.json` 與音檔。  
獨立 CLI / `yt-decoder serve`（port 8766）止於 [v0.3.0-standalone](https://github.com/caculus/yt-decoder/releases/tag/v0.3.0-standalone)。

## 開發者

維護入口：`yingtingjun/yt_decoder/`（單一 repo）。
```
