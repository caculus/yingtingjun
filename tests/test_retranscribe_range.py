"""Partial re-transcription (局部重辨) wiring and merge logic."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from unittest.mock import patch

import numpy as np

from serve_player import AppState
from transcribe import (
    range_backup_path,
    restore_range_backup,
    retranscribe_time_range,
)


def _state(tmp_path: Path, *, transcript: Path | None = None, audio: Path | None = None) -> AppState:
    outdir = tmp_path / "output"
    workdir = tmp_path / "workdir"
    uploads = tmp_path / "uploads"
    notes = tmp_path / "notes"
    for path in (outdir, workdir, uploads, notes):
        path.mkdir(parents=True, exist_ok=True)
    return AppState(audio, transcript, outdir, workdir, uploads, notes)


def _sample_transcript(path: Path) -> None:
    payload = {
        "language": "en",
        "turns": [
            {
                "speaker": "SPEAKER_01",
                "start": 0.0,
                "end": 2.0,
                "text": "Hello there.",
                "text_zh": "你好。",
            },
            {
                "speaker": "SPEAKER_01",
                "start": 2.0,
                "end": 5.0,
                "text": "Bad segment.",
                "text_zh": "錯誤句。",
            },
            {
                "speaker": "SPEAKER_02",
                "start": 5.0,
                "end": 8.0,
                "text": "Thanks.",
                "text_zh": "謝謝。",
            },
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_silent_wav(path: Path, *, duration_sec: float = 10.0, sr: int = 16000) -> None:
    import soundfile as sf

    samples = np.zeros(int(duration_sec * sr), dtype=np.float32)
    sf.write(path, samples, sr)


def test_retranscribe_time_range_replaces_overlap_and_creates_backup(tmp_path: Path):
    outdir = tmp_path / "output"
    workdir = tmp_path / "workdir"
    outdir.mkdir()
    workdir.mkdir()
    json_path = outdir / "lesson.json"
    audio_path = workdir / "lesson.work.wav"
    _sample_transcript(json_path)
    _write_silent_wav(audio_path)

    fake_segments = [
        {
            "text": "Fixed segment.",
            "start": 0.8,
            "end": 2.2,
            "words": [
                {"word": "Fixed", "start": 0.8, "end": 1.2},
                {"word": "segment.", "start": 1.2, "end": 2.2},
            ],
        }
    ]

    def fake_translate(turns):
        for turn in turns:
            turn["text_zh"] = "已修正。"

    with patch("transcribe.load_audio_mono") as load_audio, patch(
        "transcribe.transcribe", return_value={"segments": fake_segments}
    ), patch("transcribe.translate_turns", side_effect=fake_translate):
        load_audio.return_value = (np.zeros(160000, dtype=np.float32), 16000)
        result = retranscribe_time_range(
            json_path,
            start=2.0,
            end=5.0,
            audio_path=audio_path,
            workdir=workdir,
            outdir=outdir,
            skip_translate=False,
        )

    assert result["ok"] is True
    assert range_backup_path(json_path).exists()

    updated = json.loads(json_path.read_text(encoding="utf-8"))
    texts = [t["text"] for t in updated["turns"]]
    assert "Bad segment." not in texts
    assert any("Fixed" in t for t in texts)
    assert texts[0] == "Hello there."
    assert texts[-1] == "Thanks."


def test_restore_range_backup_reverts_transcript(tmp_path: Path):
    outdir = tmp_path / "output"
    outdir.mkdir()
    json_path = outdir / "lesson.json"
    _sample_transcript(json_path)
    original = json_path.read_text(encoding="utf-8")
    backup = range_backup_path(json_path)
    backup.write_text(original, encoding="utf-8")

    mutated = json.loads(original)
    mutated["turns"][1]["text"] = "Mutated."
    json_path.write_text(json.dumps(mutated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    restore_range_backup(json_path, outdir=outdir)
    restored = json.loads(json_path.read_text(encoding="utf-8"))
    assert restored["turns"][1]["text"] == "Bad segment."


def test_app_state_rejects_invalid_range(tmp_path: Path):
    outdir = tmp_path / "output"
    workdir = tmp_path / "workdir"
    outdir.mkdir()
    workdir.mkdir()
    json_path = outdir / "lesson.json"
    audio_path = workdir / "lesson.work.wav"
    _sample_transcript(json_path)
    audio_path.write_bytes(b"x")

    state = _state(tmp_path, transcript=json_path, audio=audio_path)

    too_long = state.start_retranscribe_range_job(0.0, 200.0)
    assert too_long["ok"] is False
    assert "180" in too_long["error"]

    bad_order = state.start_retranscribe_range_job(5.0, 2.0)
    assert bad_order["ok"] is False


def test_app_state_retranscribe_job_completes_with_mocked_subprocess(tmp_path: Path):
    outdir = tmp_path / "output"
    workdir = tmp_path / "workdir"
    outdir.mkdir()
    workdir.mkdir()
    json_path = outdir / "lesson.json"
    audio_path = workdir / "lesson.work.wav"
    _sample_transcript(json_path)
    audio_path.write_bytes(b"x")
    state = _state(tmp_path, transcript=json_path, audio=audio_path)

    class FakeProc:
        def __init__(self):
            self.stdout = iter(["[range] Done\n"])
            self.returncode = 0

        def wait(self):
            return 0

    with patch("serve_player.subprocess.Popen", return_value=FakeProc()):
        started = state.start_retranscribe_range_job(2.0, 4.0)
        assert started["ok"] is True

        deadline = time.time() + 3.0
        while time.time() < deadline:
            snap = state.job_snapshot()
            if snap and snap.get("status") != "running":
                break
            time.sleep(0.05)

        snap = state.job_snapshot()
        assert snap["status"] == "done"
        assert snap["kind"] == "retranscribe-range"
        assert "局部重辨完成" in snap["message"]


def test_app_state_restore_requires_backup(tmp_path: Path):
    outdir = tmp_path / "output"
    outdir.mkdir()
    json_path = outdir / "lesson.json"
    _sample_transcript(json_path)
    state = _state(tmp_path, transcript=json_path, audio=Path("x.wav"))

    missing = state.restore_retranscribe_range()
    assert missing["ok"] is False
    assert "bak-range" in missing["error"]
