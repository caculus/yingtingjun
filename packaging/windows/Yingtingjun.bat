@echo off
setlocal EnableExtensions
rem Launch contract: data dirs via CLI; models/ffmpeg/dict via env.
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"

set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "PYTHONUNBUFFERED=1"
set "YTJ_MODELS_DIR=%ROOT%\models"
set "HF_HOME=%ROOT%\models"
set "YTJ_FFMPEG=%ROOT%\bin\ffmpeg.exe"
if exist "%ROOT%\models\ecdict.db" set "ECDICT_DB=%ROOT%\models\ecdict.db"

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

"%PY%" -u "%ROOT%\app\serve_player.py" --workdir "%ROOT%\data\workdir" --outdir "%ROOT%\data\output" --uploads "%ROOT%\data\uploads" --notesdir "%ROOT%\data\notes"
exit /b %ERRORLEVEL%
