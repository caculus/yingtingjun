"""Caption quality heuristics and stderr warnings."""

from __future__ import annotations

import sys

from yt_decoder.captions import Turn
from yt_decoder.probe import CaptionTrack


def caption_quality_warnings(track: CaptionTrack, turns: list[Turn]) -> list[str]:
    """Return human-readable warnings for auto / low-quality captions."""
    warnings: list[str] = []

    if track.kind == "auto":
        warnings.append(
            "使用 YouTube 自動字幕（非人工），錯字、斷句與時間軸可能不準"
        )

    if not turns:
        return warnings

    n = len(turns)
    short = sum(
        1
        for t in turns
        if (t.end - t.start) < 1.0 and len((t.text or "").split()) <= 3
    )
    if short / n > 0.35:
        warnings.append("字幕片段過短且零碎，常見於自動生成字幕")

    long_upper = sum(
        1 for t in turns if len(t.text or "") > 8 and (t.text or "").isupper()
    )
    if long_upper / n > 0.15:
        warnings.append("大量全大寫字幕，可能為自動字幕")

    if track.kind == "auto" or warnings:
        warnings.append("可在英聽君內使用「局部重辨」修正錯誤句段")

    return warnings


def emit_caption_warnings(track: CaptionTrack, turns: list[Turn]) -> None:
    for message in caption_quality_warnings(track, turns):
        print(f"[warn] {message}", file=sys.stderr, flush=True)
