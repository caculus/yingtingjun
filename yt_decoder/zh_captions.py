"""Apply YouTube Chinese captions onto English turns (skip local NLLB when possible)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from yt_decoder.captions import Turn, download_caption, parse_vtt
from yt_decoder.io_util import log_stage
from yt_decoder.probe import CaptionTrack, pick_zh_caption_track

# Fraction of English turns that must receive non-empty ZH before we trust the track.
DEFAULT_MIN_COVERAGE = 0.45


def _overlap(a0: float, a1: float, b0: float, b1: float) -> float:
    return max(0.0, min(a1, b1) - max(a0, b0))


def _join_zh_parts(parts: list[str]) -> str:
    cleaned: list[str] = []
    for part in parts:
        text = (part or "").strip()
        if not text:
            continue
        if cleaned and cleaned[-1] == text:
            continue
        cleaned.append(text)
    return "".join(cleaned)


def map_zh_turns_to_en_turns(
    en_turns: list[dict[str, Any]],
    zh_turns: list[Turn] | list[dict[str, Any]],
    *,
    min_coverage: float = DEFAULT_MIN_COVERAGE,
) -> dict[str, Any]:
    """Fill text_zh by time overlap. Returns stats; clears text_zh if coverage too low.

    Each Chinese cue is assigned to the single English turn with the largest
    positive overlap (avoids boundary double-counting).
    """
    total = len(en_turns)
    if total == 0:
        return {
            "ok": False,
            "reason": "no_en_turns",
            "coverage": 0.0,
            "filled": 0,
            "total": 0,
        }

    zh_cues: list[tuple[float, float, str]] = []
    for cue in zh_turns:
        if isinstance(cue, Turn):
            start, end, text = cue.start, cue.end, cue.text
        else:
            start = float(cue.get("start") or 0.0)
            end = float(cue.get("end") or 0.0)
            text = str(cue.get("text") or "")
        text = text.strip()
        if not text or end <= start:
            continue
        zh_cues.append((start, end, text))

    if not zh_cues:
        for turn in en_turns:
            turn["text_zh"] = ""
        return {
            "ok": False,
            "reason": "empty_zh",
            "coverage": 0.0,
            "filled": 0,
            "total": total,
        }

    assigned: list[list[str]] = [[] for _ in en_turns]
    for z0, z1, text in zh_cues:
        best_i = -1
        best_ov = 0.0
        for i, turn in enumerate(en_turns):
            t0 = float(turn.get("start") or 0.0)
            t1 = float(turn.get("end") or 0.0)
            ov = _overlap(t0, t1, z0, z1)
            if ov > best_ov:
                best_ov = ov
                best_i = i
        if best_i >= 0 and best_ov > 0:
            assigned[best_i].append(text)

    filled = 0
    for turn, parts in zip(en_turns, assigned):
        zh_text = _join_zh_parts(parts)
        turn["text_zh"] = zh_text
        if zh_text:
            filled += 1

    coverage = filled / total if total else 0.0
    if coverage < min_coverage:
        for turn in en_turns:
            turn["text_zh"] = ""
        return {
            "ok": False,
            "reason": "low_coverage",
            "coverage": coverage,
            "filled": filled,
            "total": total,
            "min_coverage": min_coverage,
        }

    return {
        "ok": True,
        "reason": "ok",
        "coverage": coverage,
        "filled": filled,
        "total": total,
    }


def apply_zh_vtt_to_turns(
    en_turns: list[dict[str, Any]],
    zh_vtt: Path,
    track: CaptionTrack,
    *,
    min_coverage: float = DEFAULT_MIN_COVERAGE,
) -> dict[str, Any]:
    """Parse an already-downloaded ZH VTT and map onto English turns."""
    try:
        zh_turns = parse_vtt(zh_vtt)
    except Exception as exc:  # noqa: BLE001
        log_stage("zh_caption", f"略過（解析失敗：{exc}）")
        return {
            "ok": False,
            "source": "youtube_caption",
            "kind": track.kind,
            "lang_code": track.lang_code,
            "reason": f"parse:{exc}",
        }

    stats = map_zh_turns_to_en_turns(en_turns, zh_turns, min_coverage=min_coverage)
    result = {
        "source": "youtube_caption",
        "kind": track.kind,
        "lang_code": track.lang_code,
        "name": track.name,
        **stats,
    }
    if stats.get("ok"):
        log_stage(
            "zh_caption",
            f"套用 {track.lang_code}（{stats['filled']}/{stats['total']}，"
            f"{int(stats['coverage'] * 100)}%）",
        )
    else:
        log_stage(
            "zh_caption",
            f"略過（{stats.get('reason')}，覆蓋 "
            f"{stats.get('filled', 0)}/{stats.get('total', 0)}）",
        )
    return result


def try_apply_youtube_zh_captions(
    url: str,
    en_turns: list[dict[str, Any]],
    zh_tracks: list[CaptionTrack],
    *,
    dest_vtt: Path,
    min_coverage: float = DEFAULT_MIN_COVERAGE,
    zh_vtt: Path | None = None,
    track: CaptionTrack | None = None,
) -> dict[str, Any] | None:
    """Use YouTube ZH captions for text_zh.

    Prefer ``zh_vtt`` already downloaded with the English track (one yt-dlp call).
    Otherwise download the best ZH track (may 429 if called right after another fetch).
    Returns None when no ZH track exists.
    """
    if zh_vtt is not None and zh_vtt.is_file():
        chosen = track or pick_zh_caption_track(zh_tracks)
        if chosen is None:
            chosen = CaptionTrack(
                lang="zh",
                kind="auto",
                name=zh_vtt.name,
                lang_code=zh_vtt.stem,
            )
        log_stage("zh_caption", f"{chosen.kind} / {chosen.lang_code}（已下載）")
        return apply_zh_vtt_to_turns(
            en_turns, zh_vtt, chosen, min_coverage=min_coverage
        )

    chosen = track or pick_zh_caption_track(zh_tracks)
    if chosen is None:
        return None

    log_stage("zh_caption", f"{chosen.kind} / {chosen.lang_code}")
    try:
        download_caption(url, chosen, dest_vtt)
    except Exception as exc:  # noqa: BLE001
        log_stage("zh_caption", f"略過（下載失敗：{exc}）")
        return {
            "ok": False,
            "source": "youtube_caption",
            "kind": chosen.kind,
            "lang_code": chosen.lang_code,
            "reason": f"download:{exc}",
        }

    return apply_zh_vtt_to_turns(
        en_turns, dest_vtt, chosen, min_coverage=min_coverage
    )
