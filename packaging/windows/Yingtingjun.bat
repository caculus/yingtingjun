@echo off
setlocal EnableExtensions
rem Launch contract (same as macOS / Linux):
rem   CLI: --workdir --outdir --uploads --notesdir
rem   Env: YTJ_MODELS_DIR, YTJ_FFMPEG, ECDICT_DB, PYTHONUTF8=1
rem   Study data: %USERPROFILE%\Documents\Yingtingjun\data  (override: YTJ_DATA / YTJ_DOCUMENTS)
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"

set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "PYTHONUNBUFFERED=1"
set "YTJ_SUPPORT=%ROOT%"
set "YTJ_MODELS_DIR=%ROOT%\models"
set "HF_HOME=%ROOT%\models"
set "YTJ_FFMPEG=%ROOT%\bin\ffmpeg.exe"
if exist "%ROOT%\models\ecdict.db" set "ECDICT_DB=%ROOT%\models\ecdict.db"

if not defined YTJ_DOCUMENTS set "YTJ_DOCUMENTS=%USERPROFILE%\Documents"
if "%YTJ_DOCUMENTS:~-1%"=="\" set "YTJ_DOCUMENTS=%YTJ_DOCUMENTS:~0,-1%"
if not defined YTJ_DATA set "YTJ_DATA=%YTJ_DOCUMENTS%\Yingtingjun\data"
if "%YTJ_DATA:~-1%"=="\" set "YTJ_DATA=%YTJ_DATA:~0,-1%"
set "DATA_ROOT=%YTJ_DATA%"

if not exist "%ROOT%\app\serve_player.py" (
  echo Missing app\serve_player.py
  pause
  exit /b 1
)

set "PY=%ROOT%\python\python.exe"
if not exist "%PY%" set "PY=%ROOT%\python\Scripts\python.exe"

set "NEED_DOWNLOAD="
if not exist "%PY%" set "NEED_DOWNLOAD=1"
if not exist "%ROOT%\python\.deps-ok" set "NEED_DOWNLOAD=1"
if not exist "%ROOT%\bin\ffmpeg.exe" set "NEED_DOWNLOAD=1"
if not exist "%ROOT%\models\ecdict.db" set "NEED_DOWNLOAD=1"
if not exist "%ROOT%\models\spkrec-ecapa-voxceleb\embedding_model.ckpt" set "NEED_DOWNLOAD=1"
if defined NEED_DOWNLOAD (
  echo.
  echo Downloading Python, ffmpeg, dictionary, ECAPA, and packages.
  echo A progress window will open. This needs the internet.
  echo.
  powershell.exe -NoProfile -ExecutionPolicy Bypass -NoLogo -File "%ROOT%\Install-PythonDeps.ps1"
  if errorlevel 1 (
    echo Runtime download failed.
    pause
    exit /b 1
  )
  set "PY=%ROOT%\python\python.exe"
  if exist "%ROOT%\models\ecdict.db" set "ECDICT_DB=%ROOT%\models\ecdict.db"
)

if not exist "%PY%" (
  echo Missing Python after download: %ROOT%\python\python.exe
  pause
  exit /b 1
)

rem One-time: old slim installs kept study data under {app}\data.
if exist "%ROOT%\data\" if not exist "%DATA_ROOT%\" (
  echo Migrating study data to "%DATA_ROOT%"
  mkdir "%DATA_ROOT%" 2>nul
  xcopy /E /I /Y "%ROOT%\data" "%DATA_ROOT%" >nul
)

mkdir "%DATA_ROOT%\workdir" 2>nul
mkdir "%DATA_ROOT%\output" 2>nul
mkdir "%DATA_ROOT%\uploads" 2>nul
mkdir "%DATA_ROOT%\notes" 2>nul

echo Data directory: %DATA_ROOT%
echo Models directory: %YTJ_MODELS_DIR%
echo.

"%PY%" -u "%ROOT%\app\serve_player.py" --workdir "%DATA_ROOT%\workdir" --outdir "%DATA_ROOT%\output" --uploads "%DATA_ROOT%\uploads" --notesdir "%DATA_ROOT%\notes"
exit /b %ERRORLEVEL%
