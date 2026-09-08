"""YouTube metadata probe via yt-dlp --dump-json."""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from yt_decoder.errors import ProbeError
from yt_decoder.util import extract_video_id
from yt_decoder.ytdlp import caption_display_name, dump_json, normalize_lang_code

CaptionKind = Literal["manual", "auto"]

# Lower is better. Manual always beats auto (see pick_zh_caption_track).
# Within script: Taiwan / Traditional before China / Simplified.
_ZH_LANG_RANK: dict[str, int] = {
    "zh-tw": 0,
    "zh-hant": 1,
    "zh-hk": 2,
    "zh-hans": 10,
    "zh-cn": 11,
    "zh": 12,
}

# Blur-probe + import should share one dump_json (extra dumps burn zh timedtext quota).
_PROBE_CACHE_TTL_SEC = 180.0
_probe_cache: dict[str, tuple[float, "ProbeResult"]] = {}


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
    zh_caption_tracks: list[CaptionTrack] = field(default_factory=list)
    recommended: str | None = None
    within_limit: bool = True
    max_duration_sec: int = 2700
    url: str = ""
    # Full yt-dlp dump when available (avoid a second dump_json during import).
    raw_info: dict[str, Any] | None = field(default=None, repr=False, compare=False)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("raw_info", None)
        data["caption_tracks"] = [asdict(t) for t in self.caption_tracks]
        data["zh_caption_tracks"] = [asdict(t) for t in self.zh_caption_tracks]
        return data


def _tracks_from_map(
    caption_map: dict[str, Any] | None,
    *,
    kind: CaptionKind,
    lang_prefix: str,
) -> list[CaptionTrack]:
    tracks: list[CaptionTrack] = []
    for lang_code, formats in (caption_map or {}).items():
        if not normalize_lang_code(lang_code).startswith(lang_prefix):
            continue
        name = formats[0].get("name") if formats else lang_code
        display = str(name or lang_code)
        if kind == "auto" and not name:
            display = caption_display_name(lang_code, kind="auto")
        tracks.append(
            CaptionTrack(
                lang=normalize_lang_code(lang_code) or lang_code,
                kind=kind,
                name=display,
                lang_code=lang_code,
            )
        )
    return tracks


def _extract_caption_tracks(info: dict[str, Any]) -> list[CaptionTrack]:
    tracks = _tracks_from_map(info.get("subtitles"), kind="manual", lang_prefix="en")
    tracks.extend(
        _tracks_from_map(info.get("automatic_captions"), kind="auto", lang_prefix="en")
    )
    tracks.sort(key=lambda t: (0 if t.kind == "manual" else 1, t.lang_code))
    return tracks


def _extract_zh_caption_tracks(info: dict[str, Any]) -> list[CaptionTrack]:
    tracks = _tracks_from_map(info.get("subtitles"), kind="manual", lang_prefix="zh")
    tracks.extend(
        _tracks_from_map(info.get("automatic_captions"), kind="auto", lang_prefix="zh")
    )
    tracks.sort(key=_zh_track_sort_key)
    return tracks


def normalize_zh_lang_key(lang_code: str) -> str:
    """Lowercase YouTube zh codes for ranking (zh-TW → zh-tw)."""
    return (lang_code or "").strip().lower().replace("_", "-")


def is_zh_lang_code(lang_code: str) -> bool:
    return normalize_zh_lang_key(lang_code).startswith("zh")


def zh_lang_rank(lang_code: str) -> int:
    """Prefer Traditional/Taiwan before Simplified/China; unknown zh* last."""
    key = normalize_zh_lang_key(lang_code)
    if key in _ZH_LANG_RANK:
        return _ZH_LANG_RANK[key]
    # zh-Hans-CN / zh-Hant-TW style
    if "hant" in key or key.startswith("zh-tw") or key.startswith("zh-hk"):
        return 3
    if "hans" in key or key.startswith("zh-cn"):
        return 13
    if key.startswith("zh"):
        return 20
    return 99


def _zh_track_sort_key(track: CaptionTrack) -> tuple[int, int, str]:
    kind_rank = 0 if track.kind == "manual" else 1
    return (kind_rank, zh_lang_rank(track.lang_code), track.lang_code)


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
    zh_tracks = _extract_zh_caption_tracks(info)
    within_limit = duration <= max_duration_sec

    return ProbeResult(
        ok=True,
        video_id=video_id,
        title=title,
        duration_sec=duration,
        caption_tracks=tracks,
        zh_caption_tracks=zh_tracks,
        recommended=_recommended_track(tracks),
        within_limit=within_limit,
        max_duration_sec=max_duration_sec,
        url=url,
        raw_info=info,
    )


def probe_url_cached(
    url: str,
    *,
    max_duration_sec: int = 2700,
    ttl_sec: float = _PROBE_CACHE_TTL_SEC,
    force: bool = False,
) -> ProbeResult:
    """Like probe_url, but reuses a recent result for the same URL.

    UI blur-probe + import start often fire twice; sharing one dump avoids
    burning YouTube timedtext quota before Chinese captions can download.
    """
    key = f"{url}|{max_duration_sec}"
    now = time.monotonic()
    if not force:
        hit = _probe_cache.get(key)
        if hit is not None:
            ts, cached = hit
            if now - ts <= ttl_sec:
                return cached
    result = probe_url(url, max_duration_sec=max_duration_sec)
    _probe_cache[key] = (now, result)
    return result


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


def english_caption_candidates(
    tracks: list[CaptionTrack],
    preference: str = "manual_first",
) -> list[CaptionTrack]:
    """Ordered English tracks to try: preferred first, then en-orig / other en*."""
    primary = pick_caption_track(tracks, preference)
    if primary is None:
        return []
    ordered = [primary]
    for track in tracks:
        if not track.lang.startswith("en"):
            continue
        if track.lang_code == primary.lang_code and track.kind == primary.kind:
            continue
        ordered.append(track)
    # Prefer original ASR code when primary is plain ``en`` auto.
    ordered.sort(
        key=lambda t: (
            0 if t.lang_code == primary.lang_code and t.kind == primary.kind else 1,
            0 if t.lang_code == "en-orig" else 1,
            0 if t.kind == "manual" else 1,
            t.lang_code,
        )
    )
    # Keep primary first after stable preference for en-orig as second.
    rest = [t for t in ordered if not (t.lang_code == primary.lang_code and t.kind == primary.kind)]
    rest.sort(key=lambda t: (0 if t.lang_code == "en-orig" else 1, t.lang_code))
    return [primary, *rest]


def pick_zh_caption_track(tracks: list[CaptionTrack]) -> CaptionTrack | None:
    """Select Chinese caption: manual before auto; Traditional/TW before Simplified/CN."""
    zh_tracks = [t for t in tracks if is_zh_lang_code(t.lang_code)]
    if not zh_tracks:
        return None
    return sorted(zh_tracks, key=_zh_track_sort_key)[0]
