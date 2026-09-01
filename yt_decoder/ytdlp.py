"""yt-dlp subprocess helpers."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from yt_decoder.errors import ProbeError

_YTDLP_ARGV: list[str] | None = None

# YouTube web client often fails ("page needs to be reloaded"); android works reliably.
_YOUTUBE_EXTRACTOR_ARGS = ("--extractor-args", "youtube:player_client=android")


def _ytdlp_names() -> tuple[str, ...]:
    if sys.platform.startswith("win"):
        return ("yt-dlp.exe", "yt-dlp")
    return ("yt-dlp",)


def _ytdlp_candidates() -> list[Path]:
    names = _ytdlp_names()
    candidates: list[Path] = []
    py_dir = Path(sys.executable).resolve().parent
    # Unix venv: python and yt-dlp share bin/. Windows pip: yt-dlp.exe is in Scripts/.
    search_dirs = [py_dir, py_dir / "Scripts", py_dir / "bin"]

    support = os.environ.get("YTJ_SUPPORT", "").strip()
    if support:
        root = Path(support).expanduser()
        search_dirs.extend((root / "python" / "Scripts", root / "python" / "bin"))

    for directory in search_dirs:
        for name in names:
            candidates.append(directory / name)

    for entry in os.environ.get("PATH", "").split(os.pathsep):
        if not entry:
            continue
        base = Path(entry)
        for name in names:
            candidates.append(base / name)
    return candidates


def _missing_ytdlp_message() -> str:
    if sys.platform.startswith("win"):
        return "找不到 yt-dlp。請重新開啟英聽君以下載執行階段，或執行 pip install yt-dlp"
    if sys.platform == "darwin":
        return "找不到 yt-dlp；請執行 brew install yt-dlp 或 pip install yt-dlp"
    return "找不到 yt-dlp；請執行 pip install yt-dlp"


def ytdlp_argv() -> list[str]:
    """Command prefix: bundled yt-dlp.exe, PATH, or `python -m yt_dlp`."""
    global _YTDLP_ARGV
    if _YTDLP_ARGV is not None:
        return list(_YTDLP_ARGV)

    for candidate in _ytdlp_candidates():
        if candidate.is_file():
            _YTDLP_ARGV = [str(candidate)]
            return list(_YTDLP_ARGV)

    for name in _ytdlp_names():
        path = shutil.which(name)
        if path:
            _YTDLP_ARGV = [path]
            return list(_YTDLP_ARGV)

    try:
        import yt_dlp  # noqa: F401
    except ImportError:
        raise ProbeError(_missing_ytdlp_message(), code="ytdlp_missing") from None
    _YTDLP_ARGV = [sys.executable, "-m", "yt_dlp"]
    return list(_YTDLP_ARGV)


def find_ytdlp() -> str:
    argv = ytdlp_argv()
    return argv[0]


def _map_ytdlp_error(output: str) -> ProbeError:
    text = (output or "").lower()
    if "sign in" in text or "login" in text or "age-restricted" in text:
        return ProbeError("需登入或年齡驗證的影片不支援", code="login_required")
    if "not available in your country" in text or "geo" in text and "block" in text:
        return ProbeError("此影片在你所在地區無法取得", code="geo_blocked")
    if "live event" in text or "is live" in text or "premieres in" in text:
        return ProbeError("不支援直播或未結束的直播", code="live_stream")
    if "unavailable" in text or "private video" in text or "removed" in text:
        return ProbeError("影片無法取得", code="unavailable")
    if "unsupported url" in text or "no video" in text:
        return ProbeError("不是有效的 YouTube 影片", code="invalid_url")
    snippet = (output or "").strip().splitlines()
    message = snippet[-1] if snippet else "yt-dlp 執行失敗"
    return ProbeError(message, code="unavailable")


def _ffmpeg_args() -> tuple[str, ...]:
    from yt_decoder.util import resolve_ffmpeg_dir

    ffmpeg_dir = resolve_ffmpeg_dir()
    if ffmpeg_dir is not None:
        return ("--ffmpeg-location", str(ffmpeg_dir))
    return ()


def run_ytdlp(url: str, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    cmd = [
        *ytdlp_argv(),
        "--no-playlist",
        "--no-warnings",
        *_YOUTUBE_EXTRACTOR_ARGS,
        *_ffmpeg_args(),
        *args,
        url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if check and result.returncode != 0:
        raise _map_ytdlp_error(result.stderr or result.stdout)
    return result


def dump_json(url: str) -> dict[str, Any]:
    result = run_ytdlp(url, "--dump-single-json", "--skip-download", check=False)
    if result.returncode != 0:
        raise _map_ytdlp_error(result.stderr or result.stdout)
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ProbeError(f"無法解析 yt-dlp 輸出：{exc}", code="unavailable") from exc


def normalize_lang_code(lang: str) -> str:
    """Normalize en-US → en for matching; keep original in track.lang_code."""
    return lang.split("-")[0].lower() if lang else ""


def caption_display_name(lang: str, *, kind: str) -> str:
    if kind == "auto":
        return f"{lang} (auto-generated)"
    return lang
