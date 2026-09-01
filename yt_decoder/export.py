"""Write Yingtingjun-compatible JSON and sidecar metadata."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from yt_decoder.constants import TOOL_NAME, TOOL_VERSION


def build_transcript_payload(
    turns: list[dict[str, Any]],
    *,
    language: str = "en",
    bilingual: bool = True,
    source: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build output/{stem}.json payload aligned with yingtingjun write_outputs()."""
    text = " ".join((t.get("text") or "").strip() for t in turns).strip()
    payload: dict[str, Any] = {
        "language": language,
        "bilingual": bilingual,
        "text": text,
        "turns": [
            {
                "speaker": t["speaker"],
                "start": t["start"],
                "end": t["end"],
                "text": t["text"],
                "text_zh": t.get("text_zh") or "",
                "words": t.get("words") or [],
            }
            for t in turns
        ],
    }
    if source is not None:
        payload["source"] = source
    return payload


def build_source_metadata(
    *,
    source_type: str,
    url: str,
    video_id: str,
    title: str,
    duration_sec: float,
    caption_kind: str | None = None,
    caption_format: str | None = None,
) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "type": source_type,
        "url": url,
        "video_id": video_id,
        "title": title,
        "duration_sec": duration_sec,
        "tool": TOOL_NAME,
        "tool_version": TOOL_VERSION,
        "imported_at": datetime.now(timezone.utc).astimezone().isoformat(),
    }
    if caption_kind or caption_format:
        meta["caption"] = {
            "kind": caption_kind,
            "format": caption_format,
        }
    return meta


def inject_source_metadata(json_path: Path, source: dict[str, Any]) -> None:
    """Add or replace top-level source block on an existing transcript JSON."""
    data = json.loads(json_path.read_text(encoding="utf-8"))
    data["source"] = source
    json_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def write_outputs(
    output_dir: Path,
    stem: str,
    payload: dict[str, Any],
    *,
    probe_data: dict[str, Any] | None = None,
    caption_vtt: Path | None = None,
) -> Path:
    """Write output/{stem}.json and optional sidecars. Returns JSON path."""
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / f"{stem}.json"
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    if probe_data is not None:
        sidecar = output_dir / f"{stem}.source.json"
        sidecar.write_text(
            json.dumps(probe_data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    if caption_vtt is not None and caption_vtt.is_file():
        dest = output_dir / f"{stem}.caption.vtt"
        dest.write_text(caption_vtt.read_text(encoding="utf-8"), encoding="utf-8")

    return json_path
