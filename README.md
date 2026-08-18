# 英聽君（yingtingjun）

**把你每天真正遇到的英文，變成個人化聽力教材。**

剛移居紐澳時，日常對話總是聽過就過。英聽君是作者為自己做的小工具：把生活裡真正遇到的英文，變成可以反覆跟讀的雙語教材。

選任意錄音 → 偵測是否為英文對話 → 英文轉寫 + 下一行中文翻譯  
（含話者區分、標點、分段、時間戳），並可用瀏覽器「英聽君」邊聽邊跟讀、記筆記、查詞典、局部重辨。

語料來自你的生活，檔案留在你的電腦（Mac、Windows 或 Linux），不上雲端。

**English:** Cross-platform local tool (macOS, Windows, Linux) that turns *your* real English recordings into bilingual listening lessons. Built by an engineer newly settled in Australasia, to keep up with everyday conversations.

三平台皆有**精簡安裝包**（不含 Python／模型；首次啟動或安裝時連網下載）：

| 平台 | 安裝包 | 話者／ASR |
|------|--------|-----------|
| macOS Apple Silicon | `Yingtingjun-macos-arm64.dmg` | MLX Whisper + speakrs→ECAPA |
| Windows 10/11 x64 | `Yingtingjun-Setup-x64.exe` | faster-whisper + ECAPA |
| Linux x86_64／ARM64 | `Yingtingjun-linux.tar.gz` | faster-whisper + ECAPA |

## 安裝（Install）

> **一般使用者：** macOS（Apple Silicon）用「[macOS 安裝檔](#macos-安裝檔建議apple-silicon)」；Windows 用「[Windows 安裝檔](#windows-安裝檔建議)」；Linux（x86_64 與 ARM64）用「[Linux 安裝檔](#linux-安裝檔建議x86_64-與-arm64)」。從原始碼開發再看對應開發步驟。不要在 Windows／Linux 編譯 speakrs。

### 系統需求

| 項目 | 說明 |
|------|------|
| 作業系統 | **macOS**（轉檔優先 `afconvert`，否則 ffmpeg）；**Windows 10/11**（安裝檔會連線下載 ffmpeg；話者為 ECAPA）；**Linux x86_64／ARM64**（ffmpeg + ECAPA，與 Windows 同一條執行路徑） |
| 晶片 | **Apple Silicon** 建議（MLX Whisper、speakrs CoreML 較快）；Linux 安裝檔支援 **x86_64** 與 **ARM64（aarch64）** |
| Python | **3.9+**（建議用專案內虛擬環境） |
| 磁碟／網路 | 首次會下載模型（Whisper／NLLB／speakrs／ECAPA），合計約數 GB；需可連網 |
| 可選 | ECDICT 英中詞典（`models/ecdict.db`，約數百 MB；點詞查中文用） |

可選（話者區分效果較好）：

| 項目 | 說明 |
|------|------|
| Rust（`rustup`） | **僅 macOS**：編譯 `speakrs_diarize`（依賴 Apple CoreML）；**Windows／Linux 請跳過**，改用 ECAPA |

### macOS 安裝檔（建議，Apple Silicon）

給不想自己裝 Python 的使用者。安裝包是精簡 `.dmg`（約 10 MB，含 speakrs），**不含** Python／模型；第一次開啟會連網下載，並在終端機顯示進度。

**僅支援 Apple Silicon（M1 起）。** Intel Mac 請用下方「macOS 開發安裝」。

1. 開啟 `dist/Yingtingjun-macos-arm64.dmg`（或發佈的同名檔）
2. 把 **Yingtingjun** 拖到「應用程式」
3. **第一次請右鍵 → 打開**（未簽名，系統會詢問；不要只雙擊，可能被擋）
4. 會開終端機視窗「英聽君」，依序下載：
   - CPython **3.12** arm64 standalone + pip
   - ECDICT 英中詞典 → `models/ecdict.db`
   - torch／MLX Whisper／transformers 等套件
   - SpeechBrain ECAPA 話者模型
5. 完成後瀏覽器開啟 [http://127.0.0.1:8765/](http://127.0.0.1:8765/)
6. 關閉：在終端機按 `Ctrl+C`。已在跑時再點一次圖示會打開既有頁面、不會起第二個伺服器

安裝需穩定網路，第一次可能要數分鐘（套件較大）。若下載失敗，之後再開一次會再試。

文稿與筆記在 **`~/Documents/Yingtingjun/data/`**（Finder 可能顯示為「文稿／Yingtingjun／data」；內含 `workdir`／`output`／`uploads`／`notes`）。

Python 與模型仍在 `~/Library/Application Support/Yingtingjun/`（`python/`、`models/`）。

**卸載：** 雙擊 dmg 裡的 **`Uninstall Yingtingjun.command`**。會移除 App、`python/`、`models/`；**文稿與筆記一律保留**在「文件」的 `Yingtingjun/data/`。**只把 App 丟垃圾桶不會清掉** Application Support 裡的下載內容。

若提示「已損壞、無法打開」：

```bash
xattr -cr /Applications/Yingtingjun.app
```

然後再右鍵 → 打開。

從原始碼重編安裝包（須在 **Apple Silicon Mac** 上）：

```bash
bash packaging/macos/build_portable.sh
# 產物：dist/Yingtingjun.app 與 dist/Yingtingjun-macos-arm64.dmg
# 只要 .app、不編 dmg：加上 --skip-dmg
# 不編譯 speakrs：加上 --skip-speakrs（執行時話者改走 ECAPA）
```

組裝時會編譯並打進 `speakrs_diarize`（需 Rust／cargo；沒有則警告並省略）。`packaging/macos/` 只負責組裝，`dist/` 不進 git。執行階段 Python／模型下載到 Application Support，不寫進 `.app`。

### macOS 開發安裝

從原始碼跑（Intel Mac、或本機已有 Python 的開發者）。

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

### 3.（建議，僅 macOS）編譯 speakrs 話者區分 CLI

**Windows／Linux：請整步跳過。** speakrs 依賴 Apple CoreML，無法在 Windows 編譯；`--diarizer auto` 會直接用 SpeechBrain ECAPA，話者區分仍可用。

macOS 上預設 `--diarizer auto` 會優先使用 speakrs；編譯一次即可：

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

### Windows 安裝檔（建議）

給不想自己裝 Python 的使用者。安裝包約 **2 MB**，**不含** Python／ffmpeg／模型；安裝時會連網下載，並跳出進度視窗顯示百分比。

1. 執行 `dist\Yingtingjun-Setup-x64.exe`（或發佈的同名安裝檔）
2. 安裝到 `%LOCALAPPDATA%\Yingtingjun`（不需系統管理員）
3. 複製檔案後會開 **「英聽君 — 下載執行階段」** 視窗，依序下載：
   - CPython **3.13.15 AMD64 embed** + pip
   - ffmpeg essentials → `bin\ffmpeg.exe`
   - ECDICT 英中詞典 → `models\ecdict.db`
   - torch／faster-whisper／transformers 等套件
   - SpeechBrain ECAPA 話者模型
4. 完成後用桌面或開始功能表捷徑啟動（實際是 `Yingtingjun.bat`）

安裝需穩定網路，第一次可能要數分鐘。若下載失敗，安裝精靈仍會結束；之後再開捷徑會再試一次。

**Windows on ARM（Snapdragon）**：安裝檔下載的是 **AMD64** Python（在 ARM 上模擬執行）。**不要**另外裝 ARM64 Python 來取代它。

文稿與筆記在安裝目錄的 `data\`（`workdir`／`output`／`uploads`／`notes`）。卸載時**不會**刪這些資料。

從原始碼重編安裝檔：

```powershell
powershell -ExecutionPolicy Bypass -File packaging\windows\build_portable.ps1
# 產物：dist\Yingtingjun\（便攜目錄）與 dist\Yingtingjun-Setup-x64.exe
# 只要便攜目錄、不編 Inno：加上 -SkipInstaller
```

需 [Inno Setup 6](https://jrsoftware.org/isinfo.php)（腳本找不到 `ISCC.exe` 時會嘗試 `winget install JRSoftware.InnoSetup`）。Git 樹保持扁平（`*.py` 在倉庫根目錄）；`packaging\windows\` 只負責組裝，`dist\` 不進 git。

### Windows 開發安裝（B 層）

請用 [python.org](https://www.python.org/downloads/) 安裝 **Python 3.12 Windows installer (64-bit)**（勾選 **Add python.exe to PATH**）。開發用 venv；上面的安裝檔則自帶 3.13 embed，兩者分開。

重要：若電腦是 **Snapdragon / Windows on ARM**，請下載標示 **Windows installer (64-bit)** 的 **AMD64** 版（在 ARM 上以模擬執行），**不要**選 **ARM64** 版。ARM64 Python 能裝 `torch`，但常 **沒有 `torchaudio` **，pip 會報 `from versions: none`。

勿用 Microsoft Store 版 Python（`--pick` / tkinter 常缺 tcl/tk）。

```powershell
cd path\to\yingtingjun
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
# 建議用安裝腳本（先從 PyTorch CPU 索引裝 torch，再裝其餘）
powershell -ExecutionPolicy Bypass -File scripts\install_windows.ps1
# 或手動：
# python -m pip install torch==2.9.1 --index-url https://download.pytorch.org/whl/cpu
# python -m pip install -r requirements-windows.txt
# 注意：Windows 請用 requirements-windows.txt，不要用 requirements.txt（含 mlx-whisper）
# 注意：不要強裝 torchaudio；版本不合會跳出「無法找到程序輸入點 torch_library_impl」視窗

# ffmpeg（擇一）
winget install Gyan.FFmpeg
# 或把 ffmpeg.exe 放到專案 bin\，或設 YTJ_FFMPEG

# 可選：本機英中詞典
powershell -ExecutionPolicy Bypass -File scripts\setup_ecdict.ps1

python transcribe.py "meeting.m4a"
python serve_player.py
# 瀏覽器：http://127.0.0.1:8765/
```

Windows **不編譯 speakrs**；`--diarizer auto` 會直接用 ECAPA。CPU 轉寫會比 Apple Silicon 慢。若 PowerShell 禁止執行腳本，用上面的 `-ExecutionPolicy Bypass`，或先 `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`。

若 `torch` 顯示 `from versions: none`：確認是 **64-bit AMD64** Python。若診斷輸出是 `ARM64`，請改裝 python.org 的 **64-bit（AMD64）** 安裝包，刪除 `.venv` 後重建：

```powershell
python -c "import platform,struct,sys; print(sys.version); print(platform.machine(), struct.calcsize('P')*8)"
# 期望：AMD64 64
# 若是 ARM64 64 → 重裝 AMD64 Python，再：
Remove-Item -Recurse -Force .venv
py -3.12-64 -m venv .venv
.\.venv\Scripts\Activate.ps1
powershell -ExecutionPolicy Bypass -File scripts\install_windows.ps1
```

（`py -3.12-64` 強制用 64-bit x86；若命令不存在，用「開始功能表」裡 Python 3.12 的完整路徑建立 venv。）

若轉寫到話者區分時跳出 **「無法找到程序輸入點 torch_library_impl」**（`torchaudio\lib\_torchaudio.pyd`），或日誌出現 `WinError 127` / `Could not load this library: ..._torchaudio.pyd`：

這是 **torchaudio 與 torch 不相容**。新版程式會在 Windows **自動用 stub**（不必卸載也能過 ECAPA）。也可手動卸載：

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip uninstall -y torchaudio
python -c "from speechbrain.inference.speaker import EncoderClassifier; print('ok')"
```

（若尚未 pull 含 stub 的更新，卸載後需有 stub 程式，否則 speechbrain 仍會因缺 torchaudio 失敗。）然後重跑轉寫（Whisper／NLLB 快取會重用）。

### Linux 安裝檔（建議，x86_64 與 ARM64）

給不想自己裝 Python 的使用者。安裝包是精簡 `Yingtingjun-linux.tar.gz`（約 70 KB），**不含** Python／ffmpeg／模型；**同一份 tarball** 在 x86_64 與 ARM64 上通用，第一次啟動會依本機 CPU 連網下載對應的 standalone Python 與套件，並在終端機顯示進度。

**支援 x86_64 與 ARM64（aarch64），glibc（如 Ubuntu 22.04+）。** 已在 Ubuntu ARM64 實機驗證。Alpine／musl 請用下方「Linux 開發安裝」。

1. 解壓 `dist/Yingtingjun-linux.tar.gz`（或發佈的同名檔）
2. 進入解壓出的 `Yingtingjun` 目錄，執行 `bash install.sh`（不需 root；裝到 `~/.local/share/yingtingjun/`，並加應用程式選單與 `~/.local/bin/yingtingjun`）
3. 若終端找不到 `yingtingjun`，確認 `~/.local/bin` 在 `PATH` 內（或重新登入）
4. 從應用程式選單開 **英聽君**，或執行 `yingtingjun`（會開終端機視窗）
5. 第一次依序下載：
   - CPython **3.12** standalone + pip（**x86_64 或 ARM64**，依本機）
   - **ffmpeg**：若 PATH 上已有（建議 Debian／Ubuntu 先 `sudo apt install ffmpeg`），會跳過下載；否則下載靜態組建 → `~/.local/share/yingtingjun/bin/ffmpeg`
   - ECDICT 英中詞典 → `models/ecdict.db`
   - torch／faster-whisper／transformers 等套件（含 **torchaudio**；請用 `requirements-linux.txt`，**不要**用 Windows 那份）
   - SpeechBrain ECAPA 話者模型
6. 完成後瀏覽器開啟 [http://127.0.0.1:8765/](http://127.0.0.1:8765/)
7. 關閉：在終端機按 `Ctrl+C`。已在跑時再啟動一次會打開既有頁面、不會起第二個伺服器

也可不解壓後直接 `./yingtingjun`（便攜）；Python／模型仍下載到 `~/.local/share/yingtingjun/`。

安裝需穩定網路，第一次可能要數分鐘。若下載中斷，之後再開 `yingtingjun` 會從未完成處繼續。日誌：`~/.local/share/yingtingjun/install-runtime.log`。

文稿與筆記在 **`~/Documents/Yingtingjun/data/`**（若桌面環境把「文件」指到別處，會跟 `xdg-user-dir DOCUMENTS`）。

Python、模型與（必要時）ffmpeg 在 `~/.local/share/yingtingjun/`（`python/`、`models/`、`bin/`）。

**卸載：** `bash ~/.local/share/yingtingjun/uninstall.sh`。會移除程式、`python/`、`models/`、ffmpeg 與選單捷徑；**文稿與筆記一律保留**。解壓出來的資料夾請自行刪除。

**常見問題**

- **ffmpeg 下載失敗**：先 `sudo apt install ffmpeg`（Debian／Ubuntu），再執行 `yingtingjun`。
- **仍顯示「僅支援 x86_64」**： tarball 太舊；請用含 `arch.sh` 的新版 `Yingtingjun-linux.tar.gz` 重新解壓並 `bash install.sh`。
- **依賴檔**：Linux 用 `requirements-linux.txt` + `scripts/install_linux.sh`；勿用 `requirements.txt`（含 mlx-whisper）或 `requirements-windows.txt`（刻意不安裝 torchaudio）。

從原始碼重編安裝包（macOS 或 Linux 皆可組裝）：

```bash
bash packaging/linux/build_portable.sh
# 產物：dist/linux-stage/Yingtingjun/ 與 dist/Yingtingjun-linux.tar.gz
```

`packaging/linux/` 只負責組裝，`dist/` 不進 git。執行階段 Python／模型下載到 XDG data 目錄，不打進 tarball。Linux **不編譯 speakrs**；`--diarizer auto` 用 ECAPA。

### Linux 開發安裝

從原始碼跑（x86_64 與 ARM64 皆可）。請用系統 Python 3.9+（Debian／Ubuntu：`sudo apt install python3 python3-venv python3-pip`）。開發用 venv；上面的安裝檔則自帶 3.12 standalone，兩者分開。

```bash
cd /path/to/yingtingjun
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
# 建議用安裝腳本（從 PyTorch CPU 索引裝 torch + torchaudio）
bash scripts/install_linux.sh
# 或手動：
# python -m pip install -r requirements-linux.txt
# 注意：Linux 請用 requirements-linux.txt，不要用 requirements.txt（含 mlx-whisper）
# 注意：不要用 requirements-windows.txt（刻意不安裝 torchaudio）

# ffmpeg（擇一）
sudo apt install ffmpeg          # Debian / Ubuntu
# sudo dnf install ffmpeg        # Fedora
# 或把 ffmpeg 放到專案 bin/，或設 YTJ_FFMPEG

# 可選：本機英中詞典
bash scripts/setup_ecdict.sh

python transcribe.py "meeting.m4a"
python serve_player.py
# 瀏覽器：http://127.0.0.1:8765/
```

Linux **不編譯 speakrs**；`--diarizer auto` 會直接用 ECAPA。CPU 轉寫會比 Apple Silicon 慢。指令列 `--pick` 需要 tkinter（Debian／Ubuntu：`sudo apt install python3-tk`）；一般用播放器「匯入音檔」即可。

單元測試請不要用 `requirements-dev.txt`（會拉 macOS 的 mlx-whisper）：

```bash
source .venv/bin/activate
python -m pip install pytest
python -m pytest
```

### 目錄（安裝後會用到）

| 路徑 | 說明 |
|------|------|
| `.venv/` | Python 虛擬環境（不進 git） |
| `models/` | ECAPA、`ecdict.db` 等（不進 git） |
| `bin/speakrs_diarize` | speakrs CLI（編譯產出，不進 git） |
| `bin/ffmpeg` / `ffmpeg.exe` | 可選：本機 ffmpeg（不進 git；也可用 PATH / `YTJ_FFMPEG`） |
| `workdir/` | 標準化 16 kHz wav（不進 git） |
| `uploads/` | 頁面匯入的原始音檔（不進 git） |
| `notes/` | 學習筆記 `notes/<stem>.json`；詞典快取 `_dict_cache.json`（不進 git） |
| `output/` | 文稿與快取；局部重辨快照 `*.json.bak-range`（**個人文稿不進 git**） |
| `requirements-linux.txt` | **Linux**（faster-whisper + torchaudio；勿用 `requirements.txt`） |
| `scripts/setup_ecdict.sh` / `setup_ecdict.ps1` | 下載／安裝 ECDICT（macOS／Linux bash / Windows PowerShell） |
| `scripts/install_linux.sh` | Linux 開發依賴（PyTorch CPU；不要用 `requirements.txt`） |
| `scripts/build_speakrs.sh` | 編譯 speakrs（macOS；Windows／Linux 請跳過） |
| `packaging/macos/` | macOS Apple Silicon `.app`／`.dmg` 組裝（開發打包用） |
| `packaging/windows/` | Windows 便攜組裝與 Inno 腳本（開發打包用） |
| `packaging/linux/` | Linux x86_64／ARM64 便攜組裝與 tarball（開發打包用） |
| `dist/Yingtingjun-macos-arm64.dmg` | 編譯出的 Mac 安裝映像（不進 git） |
| `dist/Yingtingjun-Setup-x64.exe` | 編譯出的 Windows 安裝檔（不進 git） |
| `dist/Yingtingjun-linux.tar.gz` | 編譯出的 Linux 安裝包（x86_64 與 ARM64；不進 git） |
| `dist/linux-stage/Yingtingjun/` | Linux 組裝出的便攜目錄（不進 git；勿與 Windows 的 `dist/Yingtingjun/` 混淆） |
| `~/Documents/Yingtingjun/data/` | macOS／Linux 安裝檔的文稿／音檔／筆記（不進 git） |
| `~/Library/Application Support/Yingtingjun/` | macOS 安裝檔的 Python／模型（不進 git） |
| `~/.local/share/yingtingjun/` | Linux 安裝檔的 Python／模型／ffmpeg（不進 git） |

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

1. 轉成 16 kHz WAV（`afconvert` → ffmpeg → soundfile，存在 `workdir/`）
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
| `--asr` | `auto`（預設：macOS→MLX，Windows／Linux→faster-whisper）／`mlx`／`faster` |
| `--diarizer` | `auto`（macOS→speakrs 否則 ECAPA；**Windows／Linux→ECAPA**）／`speakrs`／`ecapa` |
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
| **拖選鬆手即存** | 多字拖選後鬆手即存筆記（用文稿中譯；**不**走詞典；第一版片語不查 API） |
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
| `--workdir` / `--outdir` / `--uploads` / `--notesdir` | 目錄覆寫（Windows 安裝檔指向 `data\`；macOS／Linux 安裝檔指向 `~/Documents/Yingtingjun/data/`） |

不帶 `--audio` / `--transcript` 時會嘗試預設載入一支；有多支時請用頁面「選擇音檔」再「載入」，或啟動時明確指定成對路徑。

## 技術說明

| 步驟 | 方案 |
|------|------|
| 語種偵測 / ASR | **macOS**：MLX Whisper（`whisper-large-v3-turbo`）；**Windows／Linux**：faster-whisper（`--asr auto`） |
| 轉檔 | 16 kHz mono WAV：`afconvert`（macOS）→ **ffmpeg** → soundfile |
| 話者區分 | **macOS**：speakrs（CoreML）→ ECAPA；**Windows／Linux**：ECAPA（`--diarizer auto`） |
| 長段切分 | 依句號，每段最多 `--max-sentences`（預設 3）；播放器載入時也會即時切 |
| 中文翻譯 | 本機 NLLB（`zho_Hant`；逐句；glossary + 幻覺 scrub） |
| 局部重辨 | 切 wav 區間重跑 Whisper（關 previous-text 條件）+ NLLB；話者不重跑 |
| 詞典 | ECDICT SQLite（本機）→ Free Dictionary（外網）；結果快取 |
| 光棒同步 | JSON 詞級時間戳 + `requestAnimationFrame`；`/audio` Range 串流 |
| 學習筆記 | `notes/<stem>.json`；可選 `dict` 欄 |

## 注意

- 真實錄音、文稿、筆記含生活內容，**預設不進 git**；公開分享前請勿提交 `output/`、`notes/`、音檔
- 需 macOS（`afconvert`）與 Apple Silicon 較佳體驗（MLX / speakrs CoreML）。一般使用者用安裝檔（僅 arm64）；開發見「macOS 開發安裝」
- **Windows**：一般使用者用安裝檔（見上方）；開發見「Windows 開發安裝」。faster-whisper + ffmpeg + ECAPA。CPU 較慢；speakrs 不支援。若 8765 已被佔用，再開一次會打開既有頁面、不會起第二個伺服器
- **Linux 安裝檔**：`Yingtingjun-linux.tar.gz`（x86_64 與 ARM64 同一份）。解壓 → `bash install.sh`（不需 root）→ `yingtingjun`。文稿在 `~/Documents/Yingtingjun/data/`；執行階段在 `~/.local/share/yingtingjun/`。建議先 `sudo apt install ffmpeg`。卸載：`~/.local/share/yingtingjun/uninstall.sh`（保留文稿）
- **macOS 安裝檔**：僅 Apple Silicon；未簽名，第一次需右鍵打開。若 8765 已被佔用，再開一次會打開既有頁面
- **Linux 開發**：見「Linux 開發安裝」。`requirements-linux.txt` + `scripts/install_linux.sh`；Linux 上跑 `pytest` 請只裝 `pytest`（勿用 `requirements-dev.txt`，會拉 mlx-whisper）
- speakrs 未編譯時 `--diarizer auto` 會回退 ECAPA；**強制人數**必須 ECAPA（`--num-speakers`）
- **勿**把多句英文合併成一大 chunk 送 NLLB（會整句丟譯）
- NLLB「樓盤／搜尋」幻覺：翻譯時會過濾；舊稿可用 `--scrub-zh`
- Whisper 偶發重複幻覺（如連續 `that's right`）：用**局部重辨**修該時段
- 詞典第一版只查**單字**；片語請拖選存筆記或靠文稿中譯
- 多支錄音請用頁面成對載入，或啟動時指定 `--audio` + `--transcript`（勿依賴根目錄殘留的 `recording.wav`）
- 開發（**macOS／Windows**）：`python -m pip install -r requirements-dev.txt && python -m pytest`（不跑 ASR／翻譯，只測切段、scrub、詞典、局部重辨拼接）
- 大型檔案（`.venv/`、`models/`、音訊、`.whisper.json`、`uploads/`、`notes/`、`bin/`、`*.bak-range`）預設不進 git

## License

本專案原始碼為 [MIT License](LICENSE)。執行時下載的 Whisper／NLLB／ECDICT 等模型與詞典另依其各自授權。
