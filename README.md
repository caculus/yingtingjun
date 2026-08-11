# 英聽君（yingtingjun）

**把你每天真正遇到的英文，變成個人化聽力教材。**

剛移居紐澳時，日常對話總是聽過就過。英聽君是作者為自己做的小工具：把生活裡真正遇到的英文，變成可以反覆跟讀的雙語教材。

選任意錄音 → 偵測是否為英文對話 → 英文轉寫 + 下一行中文翻譯  
（含話者區分、標點、分段、時間戳），並可用瀏覽器「英聽君」邊聽邊跟讀、記筆記、查詞典、局部重辨。

語料來自你的生活，檔案留在你的 Mac，不上雲。

**English:** Local macOS tool that turns *your* real English recordings into bilingual listening lessons. Built by an engineer newly settled in Australasia, to keep up with everyday conversations.

## 安裝（Install）

### 系統需求

| 項目 | 說明 |
|------|------|
| 作業系統 | **macOS**（轉檔依賴系統內建 `afconvert`） |
| 晶片 | **Apple Silicon** 建議（MLX Whisper、speakrs CoreML 較快） |
| Python | **3.9+**（建議用專案內虛擬環境） |
| 磁碟／網路 | 首次會下載模型（Whisper／NLLB／speakrs／ECAPA），合計約數 GB；需可連網 |
| 可選 | ECDICT 英中詞典（`models/ecdict.db`，約數百 MB；點詞查中文用） |

可選（話者區分效果較好）：

| 項目 | 說明 |
|------|------|
| Rust（`rustup`） | 用來編譯 `speakrs_diarize`；未安裝時仍可用 ECAPA 後備方案 |

### 1. 進入專案並建立虛擬環境

```bash
cd /path/to/yingtingjun

# 若尚未建立虛擬環境：
python -m venv .venv

# 每次使用前先啟動：
source .venv/bin/activate
```

確認提示符前有 `(.venv)`，且 `which python` 指向專案內 `.venv/bin/python`（若你系統沒有 `python` 指令，請先安裝或配置為指向 Python 3）。

### 2. 安裝 Python 依賴

```bash
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# 若要跑單元測試：
python -m pip install -r requirements-dev.txt
python -m pytest
```

主要套件（版本已釘在 `requirements.txt`，對應當前可用環境）：`mlx-whisper`、`torch`／`torchaudio`、`speechbrain`、`transformers`（NLLB）、`soundfile`、`scikit-learn` 等。

### 3.（建議）編譯 speakrs 話者區分 CLI

預設 `--diarizer auto` 會優先使用 speakrs；編譯一次即可：

```bash
# 安裝 Rust（若尚未安裝）：https://rustup.rs
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source "$HOME/.cargo/env"

# 編譯並安裝到 bin/speakrs_diarize
bash scripts/build_speakrs.sh
```

驗證：

```bash
./bin/speakrs_diarize --help
```

若跳過此步，轉寫仍可跑，但會回退 SpeechBrain ECAPA。也可用環境變數 `SPEAKRS_BIN` 指向自訂二進位。

### 4.（建議）安裝 ECDICT 英中詞典

點詞查字典時：**本機 ECDICT 英中優先**，沒有該詞或未安裝時再走 Free Dictionary 英英。

```bash
bash scripts/setup_ecdict.sh
# → models/ecdict.db（不進 git；可設 ECDICT_DB=/path/to.db 覆寫）
```

未執行此步時，查詞仍可用（僅英英後備）。

### 5. 首次執行時的模型下載

第一次跑轉寫時會自動下載／快取模型（可能較久）：

| 模型 | 用途 | 大致位置 |
|------|------|----------|
| MLX Whisper `whisper-large-v3-turbo` | 語種偵測／ASR | Hugging Face 快取 |
| NLLB `nllb-200-distilled-600M` | 英→繁中翻譯 | Hugging Face 快取 |
| speakrs 模型 | 話者區分（若有 CLI） | speakrs 預設快取／`--speakrs-models-dir` |
| SpeechBrain ECAPA | 話者區分後備 | `models/spkrec-ecapa-voxceleb/` |
| ECDICT（可選） | 點詞英→中 | `models/ecdict.db` |

之後同機再跑會重用快取，不必重下。

### 6. 快速確認安裝成功

```bash
source .venv/bin/activate

# 轉寫（會開檔案選擇視窗；或改為指定路徑）
python transcribe.py --pick

# 另開終端：啟動英聽君
python serve_player.py
# 瀏覽器：http://127.0.0.1:8765/
```

### 目錄（安裝後會用到）

| 路徑 | 說明 |
|------|------|
| `.venv/` | Python 虛擬環境（不進 git） |
| `models/` | ECAPA、`ecdict.db` 等（不進 git） |
| `bin/speakrs_diarize` | speakrs CLI（編譯產出，不進 git） |
| `workdir/` | 標準化 16 kHz wav（不進 git） |
| `uploads/` | 頁面匯入的原始音檔（不進 git） |
| `notes/` | 學習筆記 `notes/<stem>.json`；詞典快取 `_dict_cache.json`（不進 git） |
| `output/` | 文稿與快取；局部重辨快照 `*.json.bak-range`（**個人文稿不進 git**） |
| `scripts/setup_ecdict.sh` | 下載／安裝 ECDICT |
| `scripts/build_speakrs.sh` | 編譯 speakrs |

## 轉寫（語音 → 雙語文稿）

使用前請先 `source .venv/bin/activate`。

```bash
# 開啟檔案選擇視窗
python transcribe.py --pick

# 或直接指定錄音
python transcribe.py "meeting.m4a"
python transcribe.py "interview.m4a"
```

也可在英聽君頁面用「匯入音檔」按鈕完成同一流程（見下方）。

流程：

1. 轉成 16 kHz WAV（存在 `workdir/`）
2. 偵測語種（非英文會停止；可加 `--force` 強制繼續）
3. Whisper 英文轉寫（含詞級時間戳）
4. 話者區分（SPEAKER_01 / SPEAKER_02 …）
5. **長段切分**：同一說話者超過 N 句（預設 **3**）會切成多段，方便跟讀
6. 本機英文 → 中文翻譯（NLLB；逐句；短回應 glossary + 幻覺 scrub）
7. 寫入 `output/`

常用參數：

| 參數 | 說明 |
|------|------|
| `--pick` | 用系統視窗選檔 |
| `--force` | 語種不是英文也繼續 |
| `--skip-translate` | 只轉寫、不翻譯 |
| `--whisper-json PATH` | 指定 Whisper 快取，跳過 ASR |
| `--from-json PATH` | 對已有 `*.json` 切段／重跑翻譯／重寫輸出 |
| `--retranscribe-range START END` | 搭配 `--from-json`：只對該秒數區間重跑 ASR + 翻譯（話者沿用舊稿重疊；寫 `.bak-range`） |
| `--restore-range` | 搭配 `--from-json`：從 `*.json.bak-range` 還原 |
| `--range-padding SEC` | 局部重辨音訊前後留白秒數（預設 0.75） |
| `--scrub-zh` | 搭配 `--from-json`：清掉 NLLB「樓盤／搜尋」幻覺；Yeah／Mm-hmm 用固定對譯；只重譯受污染段 |
| `--min-speakers` / `--max-speakers` | 話者數量範圍（僅 **ECAPA** 後端；預設 2–4） |
| `--num-speakers N` | **強制**剛好 N 個說話人（覆寫 min/max；自動改用 **ECAPA**；speakrs 不支援） |
| `--estimate-speakers-only` | 只估說話人數（ECAPA + silhouette），印出 N 後結束；不跑 ASR／翻譯 |
| `--max-sentences` | 同一說話者長段切成每段最多 N 句（預設 **3**） |
| `--diarizer` | `auto`（預設，優先 speakrs）／`speakrs`／`ecapa` |
| `--speakrs-mode` | `coreml`（預設）／`coreml-fast`／`cpu` |
| `--speakrs-models-dir` | 指定本機 speakrs 模型目錄（否則自動下載快取） |

若同一支錄音已有 `output/<檔名>.whisper.json`，再跑時會**自動重用**，不必重做整段 ASR。

話者人數範例：

```bash
# 只估人數（約需載入 ECAPA，長錄音可能要一兩分鐘）
python transcribe.py --estimate-speakers-only --min-speakers 2 --max-speakers 4 \
  "workdir/meeting.work.wav"

# 已知雙人：強制 2 人重跑話者（可重用 Whisper 快取）
python transcribe.py --num-speakers 2 --whisper-json "output/meeting.whisper.json" \
  "workdir/meeting.work.wav"
```

（`--num-speakers` / `--estimate-speakers-only` 與 `--from-json` 互斥；後者不重做 diarization。）

### 長段切分（每段最多 3 句）

同一說話者若一次講很長，文稿會依句號（`.?!。！？`）切開，**每段最多 3 句**（不足 3 句也自成一段）。說話者標籤不變，時間戳與詞級光棒仍對齊。

- **新轉寫**：寫入 `output/` 前就切好
- **播放器**：載入舊 JSON 時也會即時切（重新整理即可看到）
- **把磁碟上的舊文稿也改掉**（並依短段重譯中文）：

```bash
source .venv/bin/activate
python transcribe.py --from-json "output/meeting.json"
# 只要切段、不重譯：
# python transcribe.py --from-json "output/meeting.json" --skip-translate
```

### 局部重辨（只修有問題的時段）

不必整檔重轉。指定秒數區間，只重跑該段 Whisper + NLLB，其餘 turns 保留；話者標籤沿用舊稿重疊結果（第一版不重跑 diarization）。會寫 `output/<stem>.json.bak-range` 供還原。

```bash
source .venv/bin/activate
# 例：修 11:57–12:30（約 717–750 秒）
python transcribe.py --from-json "output/meeting.json" \
  "workdir/meeting.work.wav" \
  --retranscribe-range 717 750

# 還原
python transcribe.py --from-json "output/meeting.json" --restore-range
```

播放器操作：

1. 點問題段 → **用選中段**，或分別 **設起點／設終點**
2. **重辨這段**（單次 ≤180 秒）→ 看進度日誌 → 完成自動重載
3. 不滿意 → **還原**

## 輸出檔（`output/`）

以 `meeting` 為例（檔名隨你的錄音而定；個人文稿只留本機）：

| 檔案 | 說明 |
|------|------|
| `meeting.md` | 可讀文稿：英文 + 下一行中文 |
| `meeting.txt` | 純文字 |
| `meeting.srt` | 字幕 |
| `meeting.json` | 結構化（話者、時間、words、text_zh） |
| `*.whisper.json` | Whisper 快取（中間檔） |
| `*.turns.json` | 話者分離／切段後、翻譯前快取 |
| `*.json.bak-range` | 局部重辨前快照（可 `--restore-range`） |
| `*.range-meta.json` | 局部重辨元資料（起迄等） |

對應音訊與筆記：

- `workdir/<檔名>.work.wav`（播放器預設從這裡選；多支時請用頁面「選擇音檔」再載入）
- `uploads/`（頁面「匯入音檔」上傳的原始檔）
- `notes/<檔名>.json`（該錄音的學習筆記；刪錄音時一併刪除）
- `notes/_dict_cache.json`（詞典查詢快取，跨錄音共用）

## 英聽君（同步播放）

### 啟動

```bash
python serve_player.py
```

也可仍用指令列指定初始檔（可選，保留相容）：

```bash
python serve_player.py \
  --audio "workdir/meeting.work.wav" \
  --transcript "output/meeting.json"
```

瀏覽器開啟 [http://127.0.0.1:8765/](http://127.0.0.1:8765/)

改過程式或文稿後請**硬重新整理**頁面。

### 頁面功能

| 操作 | 說明 |
|------|------|
| **匯入音檔** | 選本機錄音 → 後端執行 `python transcribe.py <檔案>` → 顯示進度／日誌 → **完成後自動載入** |
| **選擇音檔** | 下拉列出已匯入音檔（顯示檔名、不含 `.work.wav`；只選中，**不會**立刻切換） |
| **載入** | 載入下拉目前選中的音檔；有對應 JSON 就播放；**沒有文稿**則提示並自動轉寫 |
| **刪除** | 確認後刪除該 stem 在 `workdir/`、`output/`、`uploads/`、`notes/` 的相關檔 |
| **學習筆記** | 見下方：點詞查字典、存當前句、選字松手存、單句循環、編輯／NLLB 重翻 |
| **點段落** | 只選中／反光該段，**不播放** |
| **點詞** | 開詞典浮層（**不跳播**） |
| **局部重辨** | 文稿上方：設起／終點或「用選中段」→ **重辨這段**（≤180 秒）→ 可 **還原** |
| **播放／暫停** | 有選中段時，下一次播放從該段開頭開始；暫停再播則從目前進度續播。空白鍵同按鈕 |
| ±5 秒 | ← / →（只移動進度，不強制開播） |
| 自動捲動 | 光棒接近視窗外時平滑捲動 |
| 處理中 | 匯入／轉寫／局部重辨時鎖定操作 |
| 停止伺服器 | 終端機 `Ctrl+C` |

頂欄：標題 + 檔案操作 + 播放控制。文稿右側為學習筆記側欄。進度區顯示 `transcribe.py` 日誌。

`/audio` 支援 **HTTP Range** 串流；瀏覽器取消下載時不會再噴未處理的 `BrokenPipeError`。

### 學習筆記與詞典

每支錄音各自一份，存在本機 `notes/<stem>.json`。

| 操作 | 說明 |
|------|------|
| **點詞查字典** | 文稿或**筆記英文句**點單一詞 → 浮層（不跳播）：**ECDICT 英中優先**，否則 Free Dictionary。文稿「存到筆記」新增一則；筆記內「寫入此則」可**附加多個生字**到同一則（`lemmas`）。chip × 移除單一詞。查無結果仍可存。 |
| **存當前句** | 側欄大按鈕；中譯取自文稿 `text_zh`（不重跑 NLLB） |
| **拖選松手即存** | 多字拖選後鬆手即存筆記（用文稿中譯；**不**走詞典；第一版片語不查 API） |
| **點筆記** | 跳到該則時間並播放；勾選「單句循環」則重複該句 |
| **編輯** | 卡片「編輯」→ 彈窗；可選「NLLB 重翻」 |
| **進階：手動新增** | 側欄摺疊區 |
| **匯出 CSV** | 含 `dict_lemma`、`dict_gloss` 等欄 |

一則筆記可含多個生字（`lemmas`）；`word`／`dict` 為最近寫入的那一個（相容舊資料）：

```json
{
  "word": "expensive",
  "dict": { "lemma": "expensive", "phonetic": "...", "senses": [], "source": "ecdict" },
  "lemmas": [
    { "lemma": "reluctant", "phonetic": "/ɹɪˈlʌktənt/", "senses": [{ "pos": "adj", "zh": "不情願的" }], "source": "ecdict" },
    { "lemma": "expensive", "phonetic": "/ɪkˈspɛnsɪv/", "senses": [{ "pos": "adj", "zh": "昂貴的" }], "source": "ecdict" }
  ]
}
```

API：

- `POST /api/notes`（含 `id` 時為更新）
- `GET /api/dict?q=`（ECDICT → Free Dictionary；快取 `notes/_dict_cache.json`）
- `POST /api/translate`（筆記編輯時 NLLB 重翻）
- `POST /api/retranscribe-range` / `POST /api/retranscribe-restore`

### 指令列參數（可選）

| 參數 | 說明 |
|------|------|
| `--audio` / `--transcript` | 啟動時預載的音訊與文稿 |
| `--port` | 預設 `8765` |
| `--no-open` | 不自動開瀏覽器 |
| `--workdir` / `--outdir` / `--uploads` / `--notesdir` | 目錄覆寫 |

不帶 `--audio` / `--transcript` 時會嘗試預設載入一支；有多支時請用頁面「選擇音檔」再「載入」，或啟動時明確指定成對路徑。

## 技術說明

| 步驟 | 方案 |
|------|------|
| 語種偵測 / ASR | MLX Whisper（`mlx-community/whisper-large-v3-turbo`） |
| 話者區分 | **speakrs**（CoreML，預設）→ 失敗時回退 SpeechBrain ECAPA |
| 長段切分 | 依句號，每段最多 `--max-sentences`（預設 3）；播放器載入時也會即時切 |
| 中文翻譯 | 本機 NLLB（`zho_Hant`；逐句；glossary + 幻覺 scrub） |
| 局部重辨 | 切 wav 區間重跑 Whisper（關 previous-text 條件）+ NLLB；話者不重跑 |
| 詞典 | ECDICT SQLite（本機）→ Free Dictionary（外網）；結果快取 |
| 光棒同步 | JSON 詞級時間戳 + `requestAnimationFrame`；`/audio` Range 串流 |
| 學習筆記 | `notes/<stem>.json`；可選 `dict` 欄 |

## 注意

- 真實錄音、文稿、筆記含生活內容，**預設不進 git**；公開分享前請勿提交 `output/`、`notes/`、音檔
- 需 macOS（`afconvert`）與 Apple Silicon 較佳體驗（MLX / speakrs CoreML）
- speakrs 未編譯時 `--diarizer auto` 會回退 ECAPA；**強制人數**必須 ECAPA（`--num-speakers`）
- **勿**把多句英文合併成一大 chunk 送 NLLB（會整句丟譯）
- NLLB「樓盤／搜尋」幻覺：翻譯時會過濾；舊稿可用 `--scrub-zh`
- Whisper 偶發重複幻覺（如連續 `that's right`）：用**局部重辨**修該時段
- 詞典第一版只查**單字**；片語請拖選存筆記或靠文稿中譯
- 多支錄音請用頁面成對載入，或啟動時指定 `--audio` + `--transcript`（勿依賴根目錄殘留的 `recording.wav`）
- 開發：`python -m pip install -r requirements-dev.txt && python -m pytest`（不跑 ASR／翻譯，只測切段、scrub、詞典、局部重辨拼接）
- 大型檔案（`.venv/`、`models/`、音訊、`.whisper.json`、`uploads/`、`notes/`、`bin/`、`*.bak-range`）預設不進 git

## License

本專案原始碼為 [MIT License](LICENSE)。執行時下載的 Whisper／NLLB／ECDICT 等模型與詞典另依其各自授權。
