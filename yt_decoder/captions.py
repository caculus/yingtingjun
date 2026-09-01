"""Download and parse YouTube captions (VTT / json3) into turns."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from yt_decoder.constants import DEFAULT_SPEAKER
from yt_decoder.probe import CaptionTrack
from yt_decoder.ytdlp import run_ytdlp

_MIN_CUE_DURATION = 0.3
_TIMESTAMP_RE = re.compile(
    r"(?P<start>\d{1,2}:\d{2}(?::\d{2})?\.\d{3})\s*-->\s*(?P<end>\d{1,2}:\d{2}(?::\d{2})?\.\d{3})"
)
_TAG_RE = re.compile(r"<[^>]+>")


@dataclass
class Turn:
    speaker: str
    start: float
    end: float
    text: str
    text_zh: str = ""
    words: list[dict[str, Any]] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "speaker": self.speaker,
            "start": self.start,
            "end": self.end,
            "text": self.text,
            "text_zh": self.text_zh,
            "words": self.words if self.words is not None else [],
        }


def ensure_sentence_punctuation(text: str) -> str:
    text = text.strip()
    if not text:
        return text
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r"([,.;:!?])([A-Za-z])", r"\1 \2", text)
    text = re.sub(r"\bMm\s*-\s*hmm\b", "Mm-hmm", text, flags=re.I)
    text = re.sub(r"\s+", " ", text).strip()
    if text[-1] not in ".?!…\"')":
        text += "."
    return text


def _parse_timestamp(value: str) -> float:
    parts = value.strip().split(":")
    if len(parts) == 2:
        minutes, seconds = parts
        hours = 0.0
    elif len(parts) == 3:
        hours, minutes, seconds = parts
    else:
        raise ValueError(f"invalid timestamp: {value}")
    sec_parts = seconds.split(".")
    whole = int(sec_parts[0])
    millis = int(sec_parts[1]) if len(sec_parts) > 1 else 0
    return int(hours) * 3600 + int(minutes) * 60 + whole + millis / 1000.0


def clean_vtt_text(text: str) -> str:
    text = _TAG_RE.sub("", text)
    text = html.unescape(text)
    text = text.replace("\u00a0", " ").replace("&nbsp;", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _parse_vtt_cues(content: str) -> list[tuple[float, float, str]]:
    cues: list[tuple[float, float, str]] = []
    blocks = re.split(r"\n\s*\n", content.replace("\r\n", "\n"))
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines or lines[0].upper().startswith("WEBVTT"):
            continue
        if lines[0].isdigit():
            lines = lines[1:]
        if not lines:
            continue
        match = _TIMESTAMP_RE.match(lines[0])
        if not match:
            continue
        start = _parse_timestamp(match.group("start"))
        end = _parse_timestamp(match.group("end"))
        text = clean_vtt_text(" ".join(lines[1:]))
        if text:
            cues.append((start, end, text))
    return cues


def _merge_short_cues(cues: list[tuple[float, float, str]]) -> list[tuple[float, float, str]]:
    if not cues:
        return cues
    merged: list[tuple[float, float, str]] = []
    for start, end, text in cues:
        if merged and (end - start) < _MIN_CUE_DURATION:
            prev_start, prev_end, prev_text = merged[-1]
            merged[-1] = (prev_start, end, f"{prev_text} {text}".strip())
        else:
            merged.append((start, end, text))
    return merged


def _merge_duplicate_lines(cues: list[tuple[float, float, str]]) -> list[tuple[float, float, str]]:
    if not cues:
        return cues
    merged: list[tuple[float, float, str]] = [cues[0]]
    for start, end, text in cues[1:]:
        prev_start, prev_end, prev_text = merged[-1]
        if text == prev_text:
            merged[-1] = (prev_start, end, prev_text)
        else:
            merged.append((start, end, text))
    return merged


def parse_vtt(path: Path, *, speaker: str = DEFAULT_SPEAKER) -> list[Turn]:
    """Parse WebVTT into turn list with HTML cleanup and cue merging."""
    content = path.read_text(encoding="utf-8")
    cues = _parse_vtt_cues(content)
    cues = _merge_short_cues(cues)
    cues = _merge_duplicate_lines(cues)
    return [
        Turn(
            speaker=speaker,
            start=start,
            end=end,
            text=ensure_sentence_punctuation(text),
        )
        for start, end, text in cues
    ]


def download_caption(url: str, track: CaptionTrack, dest: Path) -> Path:
    """Download caption file via yt-dlp. Returns path to VTT."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    out_base = dest.with_suffix("")
    out_template = str(out_base) + ".%(ext)s"

    args = ["--skip-download", "--sub-format", "vtt/best", "-o", out_template]
    if track.kind == "manual":
        args.extend(["--write-subs", "--sub-langs", track.lang_code])
    else:
        args.extend(["--write-auto-subs", "--sub-langs", track.lang_code])

    run_ytdlp(url, *args)

    candidates = sorted(dest.parent.glob(out_base.name + "*.vtt"))
    if not candidates:
        candidates = sorted(dest.parent.glob("*.vtt"))
    if not candidates:
        raise FileNotFoundError(f"yt-dlp 未產生 VTT 字幕：{dest}")

    vtt_path = candidates[0]
    if vtt_path != dest:
        dest.write_text(vtt_path.read_text(encoding="utf-8"), encoding="utf-8")
        if vtt_path != dest:
            try:
                vtt_path.unlink()
            except OSError:
                pass
    return dest


def vtt_turns_to_dicts(turns: list[Turn]) -> list[dict[str, Any]]:
    return [t.to_dict() for t in turns]
