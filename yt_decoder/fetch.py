"""Download audio (and optional video) via yt-dlp."""

from __future__ import annotations

from pathlib import Path

from yt_decoder.errors import ProbeError
from yt_decoder.ytdlp import run_ytdlp


def download_audio(url: str, dest: Path) -> Path:
    """Extract audio as m4a to dest (without extension). Returns final path."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    out_template = str(dest.with_suffix("")) + ".%(ext)s"

    run_ytdlp(
        url,
        "-x",
        "--audio-format",
        "m4a",
        "--audio-quality",
        "0",
        "-o",
        out_template,
    )

    for ext in (".m4a", ".opus", ".webm", ".mp3"):
        candidate = dest.with_suffix(ext)
        if candidate.is_file():
            if ext != ".m4a":
                raise ProbeError(
                    f"音訊格式為 {ext}，預期 m4a；請確認 ffmpeg 已安裝",
                    code="no_audio",
                )
            return candidate

    matches = sorted(dest.parent.glob(dest.name + ".*"))
    if matches:
        return matches[0]

    raise ProbeError("找不到可下載的音訊", code="no_audio")


def download_video(url: str, dest: Path, *, height: int = 360) -> Path:
    """Download low-res mp4 (M3). Returns final path."""
    raise NotImplementedError("download_video — implement in M3")
