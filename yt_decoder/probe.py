"""YouTube metadata probe via yt-dlp --dump-json."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from yt_decoder.errors import ProbeError
from yt_decoder.util import extract_video_id
from yt_decoder.ytdlp import caption_display_name, dump_json, normalize_lang_code

CaptionKind = Literal["manual", "auto"]


@dataclass
class CaptionTrack:
    lang: str
    kind: CaptionKind
    name: str
    lang_code: str = ""

    def __post_init__(self) -> None:
        if not self.lang_code:
            self.lang_code = self.lang


@dataclass
class ProbeResult:
    ok: bool
    video_id: str
    title: str
    duration_sec: float
    caption_tracks: list[CaptionTrack] = field(default_factory=list)
    recommended: str | None = None
    within_limit: bool = True
    max_duration_sec: int = 2700
    url: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["caption_tracks"] = [asdict(t) for t in self.caption_tracks]
        return data


def _extract_caption_tracks(info: dict[str, Any]) -> list[CaptionTrack]:
    tracks: list[CaptionTrack] = []

    for lang_code, formats in (info.get("subtitles") or {}).items():
        if not normalize_lang_code(lang_code).startswith("en"):
            continue
        name = formats[0].get("name") if formats else lang_code
        tracks.append(
            CaptionTrack(
                lang=normalize_lang_code(lang_code) or lang_code,
                kind="manual",
                name=str(name or lang_code),
                lang_code=lang_code,
            )
        )

    for lang_code, formats in (info.get("automatic_captions") or {}).items():
        if not normalize_lang_code(lang_code).startswith("en"):
            continue
        name = formats[0].get("name") if formats else lang_code
        tracks.append(
            CaptionTrack(
                lang=normalize_lang_code(lang_code) or lang_code,
                kind="auto",
                name=str(name or caption_display_name(lang_code, kind="auto")),
                lang_code=lang_code,
            )
        )

    tracks.sort(key=lambda t: (0 if t.kind == "manual" else 1, t.lang_code))
    return tracks


def _recommended_track(tracks: list[CaptionTrack]) -> str | None:
    manual = [t for t in tracks if t.kind == "manual"]
    auto = [t for t in tracks if t.kind == "auto"]
    if manual:
        return "manual_en"
    if auto:
        return "auto_en"
    return None


def probe_url(url: str, *, max_duration_sec: int = 2700) -> ProbeResult:
    """Fetch video metadata and caption track list via yt-dlp."""
    info = dump_json(url)

    if info.get("is_live") or info.get("live_status") in {"is_live", "is_upcoming"}:
        raise ProbeError("不支援直播或未結束的直播", code="live_stream")

    duration = float(info.get("duration") or 0.0)
    if duration <= 0:
        raise ProbeError("無法取得影片長度", code="unavailable")

    if duration > max_duration_sec:
        minutes = max_duration_sec // 60
        raise ProbeError(f"超過 {minutes} 分鐘上限", code="too_long")

    video_id = info.get("id") or extract_video_id(url)
    title = str(info.get("title") or "untitled")
    tracks = _extract_caption_tracks(info)
    within_limit = duration <= max_duration_sec

    return ProbeResult(
        ok=True,
        video_id=video_id,
        title=title,
        duration_sec=duration,
        caption_tracks=tracks,
        recommended=_recommended_track(tracks),
        within_limit=within_limit,
        max_duration_sec=max_duration_sec,
        url=url,
    )


def pick_caption_track(
    tracks: list[CaptionTrack],
    preference: str = "manual_first",
) -> CaptionTrack | None:
    """Select best English caption track per preference."""
    en_tracks = [t for t in tracks if t.lang.startswith("en")]
    if not en_tracks:
        return None

    manual = [t for t in en_tracks if t.kind == "manual"]
    auto = [t for t in en_tracks if t.kind == "auto"]

    if preference == "manual_only":
        return manual[0] if manual else None
    if preference == "auto_ok":
        return (manual or auto)[0]
    return (manual or auto)[0]
