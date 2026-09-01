"""Tests for YouTube API wiring in serve_player."""

from pathlib import Path
from unittest.mock import patch

from serve_player import AppState


def _state(tmp_path: Path) -> AppState:
    outdir = tmp_path / "output"
    workdir = tmp_path / "workdir"
    uploads = tmp_path / "uploads"
    notes = tmp_path / "notes"
    for path in (outdir, workdir, uploads, notes):
        path.mkdir()
    return AppState(None, None, outdir, workdir, uploads, notes)


def test_probe_youtube_returns_metadata(tmp_path: Path):
    from yt_decoder.probe import CaptionTrack, ProbeResult

    mock_probe = ProbeResult(
        ok=True,
        video_id="abc123",
        title="Demo Talk",
        duration_sec=600.0,
        caption_tracks=[CaptionTrack(lang="en", kind="manual", name="en")],
        recommended="manual_en",
        url="https://www.youtube.com/watch?v=abc123",
    )

    with patch("yt_decoder.probe.probe_url", return_value=mock_probe), patch(
        "yt_decoder.util.normalize_youtube_url",
        return_value="https://www.youtube.com/watch?v=abc123",
    ):
        result = _state(tmp_path).probe_youtube("https://www.youtube.com/watch?v=abc123")

    assert result["ok"] is True
    assert result["suggested_stem"].endswith("-abc123")
    assert result["has_manual_caption"] is True


def test_start_youtube_job_rejects_invalid_mode(tmp_path: Path):
    result = _state(tmp_path).start_youtube_job(
        "https://www.youtube.com/watch?v=abc123",
        stem_raw=None,
        mode="invalid",
        skip_translate=True,
    )
    assert result["ok"] is False
    assert "mode" in result["error"]
