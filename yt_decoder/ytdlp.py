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

_YTDLP_BIN: str | None = None

# YouTube web client often fails ("page needs to be reloaded"); android works reliably.
_YOUTUBE_EXTRACTOR_ARGS = ("--extractor-args", "youtube:player_client=android")


def _ytdlp_candidates() -> list[Path]:
    names = ("yt-dlp.exe", "yt-dlp") if sys.platform == "win32" else ("yt-dlp",)
    candidates: list[Path] = []
    py_bin = Path(sys.executable).resolve().parent
    for name in names:
        candidates.append(py_bin / name)

    support = os.environ.get("YTJ_SUPPORT", "").strip()
    if support:
        support_bin = Path(support).expanduser() / "python" / "bin"
        for name in names:
            candidates.append(support_bin / name)
        if sys.platform == "win32":
            candidates.append(Path(support).expanduser() / "python" / "Scripts" / "yt-dlp.exe")

    scripts = os.environ.get("PATH", "").split(os.pathsep)
    for entry in scripts:
        if not entry:
            continue
        base = Path(entry)
        for name in names:
            candidates.append(base / name)
    return candidates


def find_ytdlp() -> str:
    global _YTDLP_BIN
    if _YTDLP_BIN is not None:
        return _YTDLP_BIN

    for candidate in _ytdlp_candidates():
        if candidate.is_file():
            _YTDLP_BIN = str(candidate)
            return _YTDLP_BIN

    path = shutil.which("yt-dlp")
    if path:
        _YTDLP_BIN = path
        return path

    raise ProbeError(
        "找不到 yt-dlp；請執行 brew install yt-dlp 或 pip install yt-dlp",
        code="ytdlp_missing",
    )


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
        find_ytdlp(),
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
