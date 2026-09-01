"""URL parsing, stem naming, and default paths."""

from __future__ import annotations

import re
import shutil
import sys
import unicodedata
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from yt_decoder.constants import STEM_MAX_LEN

_YOUTUBE_HOSTS = frozenset(
    {
        "youtube.com",
        "www.youtube.com",
        "m.youtube.com",
        "music.youtube.com",
        "youtu.be",
        "www.youtu.be",
    }
)


class UrlError(ValueError):
    """Invalid or unsupported YouTube URL."""

    code = "invalid_url"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code is not None:
            self.code = code


def default_outdir() -> Path:
    """Default Yingtingjun data directory for the current platform."""
    home = Path.home()
    if sys.platform == "darwin":
        return home / "Documents" / "Yingtingjun" / "data"
    if sys.platform.startswith("win"):
        return home / "Documents" / "Yingtingjun" / "data"
    return home / "Documents" / "Yingtingjun" / "data"


def normalize_youtube_url(url: str) -> str:
    """Return a canonical watch URL or raise UrlError."""
    raw = (url or "").strip()
    if not raw:
        raise UrlError("請提供 YouTube 影片 URL")

    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    host = (parsed.netloc or "").lower()
    if host not in _YOUTUBE_HOSTS:
        raise UrlError("不是有效的 YouTube URL")

    path = parsed.path or ""

    if host.endswith("youtu.be"):
        video_id = path.lstrip("/").split("/")[0]
        if not video_id:
            raise UrlError("無法從 youtu.be 連結解析 video_id")
        return f"https://www.youtube.com/watch?v={video_id}"

    if "/shorts/" in path:
        video_id = path.split("/shorts/", 1)[1].split("/")[0]
        if not video_id:
            raise UrlError("無法從 Shorts 連結解析 video_id")
        return f"https://www.youtube.com/watch?v={video_id}"

    if "/live/" in path:
        raise UrlError("不支援直播影片", code="live_stream")

    if "/playlist" in path:
        raise UrlError("請貼單支影片連結，不支援播放清單", code="playlist_not_supported")

    query = parse_qs(parsed.query)
    if "list" in query and "v" not in query:
        raise UrlError("請貼單支影片連結，不支援播放清單", code="playlist_not_supported")

    video_ids = query.get("v") or []
    if not video_ids or not video_ids[0]:
        raise UrlError("無法從 URL 解析 video_id")
    video_id = video_ids[0]
    return f"https://www.youtube.com/watch?v={video_id}"


def extract_video_id(url: str) -> str:
    """Parse video_id from a YouTube URL."""
    normalized = normalize_youtube_url(url)
    return parse_qs(urlparse(normalized).query)["v"][0]


def sanitize_stem(title: str, video_id: str) -> str:
    """Build `{sanitized_title}-{video_id}` capped at STEM_MAX_LEN."""
    title = (title or "untitled").strip()
    normalized = unicodedata.normalize("NFKC", title)
    cleaned = re.sub(r"[^\w\s\-]+", "", normalized, flags=re.UNICODE)
    cleaned = re.sub(r"\s+", "-", cleaned.strip())
    cleaned = re.sub(r"-+", "-", cleaned).strip("-").lower()
    if not cleaned:
        cleaned = "untitled"

    suffix = f"-{video_id}"
    max_title_len = max(1, STEM_MAX_LEN - len(suffix))
    if len(cleaned) > max_title_len:
        cleaned = cleaned[:max_title_len].rstrip("-")
    return f"{cleaned}{suffix}"


def resolve_import_stem(probe, options) -> str:
    if options.preferred_stem:
        return options.preferred_stem
    return sanitize_stem(probe.title, probe.video_id)


def resolve_yingtingjun_root() -> Path | None:
    """Return Yingtingjun repo path from env or common local locations."""
    import os

    env = os.environ.get("YT_DECODER_YINGTINGJUN", "").strip()
    if env:
        path = Path(env).expanduser()
        return path if path.is_dir() else None

    # Vendored inside yingtingjun repo (yt_decoder/../transcribe.py).
    package_root = Path(__file__).resolve().parent.parent
    if (package_root / "transcribe.py").is_file():
        return package_root

    candidates = [
        Path.home() / "Downloads" / "yingtingjun",
        Path(__file__).resolve().parents[2] / "yingtingjun",
    ]
    for path in candidates:
        if (path / "transcribe.py").is_file():
            return path
    return None


def resolve_ffmpeg_dir() -> Path | None:
    """Return directory containing ffmpeg for yt-dlp postprocessing."""
    import os

    for key in ("YT_DECODER_FFMPEG", "YTJ_FFMPEG"):
        raw = os.environ.get(key, "").strip()
        if not raw:
            continue
        path = Path(raw).expanduser()
        if path.is_dir() and (path / "ffmpeg").is_file():
            return path
        if path.is_file():
            return path.parent

    root = resolve_yingtingjun_root()
    if root is not None:
        bin_dir = root / "bin"
        if (bin_dir / "ffmpeg").is_file():
            return bin_dir

    found = shutil.which("ffmpeg")
    if found:
        return Path(found).parent
    return None
