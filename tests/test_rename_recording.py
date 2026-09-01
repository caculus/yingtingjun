"""Rename imported recordings across data directories."""

import json
from pathlib import Path

from serve_player import AppState


def _make_state(tmp_path: Path) -> AppState:
    workdir = tmp_path / "workdir"
    outdir = tmp_path / "output"
    uploads = tmp_path / "uploads"
    notesdir = tmp_path / "notes"
    for d in (workdir, outdir, uploads, notesdir):
        d.mkdir()
    audio = workdir / "lesson.work.wav"
    audio.write_bytes(b"wav")
    transcript = outdir / "lesson.json"
    transcript.write_text('{"turns":[{"speaker":"SPEAKER_01","start":0,"end":1,"text":"Hi","text_zh":"","words":[]}]}', encoding="utf-8")
    (uploads / "lesson.m4a").write_bytes(b"m4a")
    (notesdir / "lesson.json").write_text(
        json.dumps({"stem": "lesson", "notes": []}, ensure_ascii=False),
        encoding="utf-8",
    )
    return AppState(audio, transcript, outdir, workdir, uploads, notesdir)


def test_rename_workdir_file_updates_all_paths(tmp_path: Path):
    state = _make_state(tmp_path)
    result = state.rename_workdir_file("lesson.work.wav", "面試練習")
    assert result["ok"] is True
    assert result["new_stem"] == "面試練習"
    assert (state.workdir / "面試練習.work.wav").exists()
    assert (state.outdir / "面試練習.json").exists()
    assert (state.uploads / "面試練習.m4a").exists()
    notes = json.loads((state.notesdir / "面試練習.json").read_text(encoding="utf-8"))
    assert notes["stem"] == "面試練習"
    assert state.audio.name == "面試練習.work.wav"
    assert state.transcript.name == "面試練習.json"


def test_rename_workdir_file_rejects_collision(tmp_path: Path):
    state = _make_state(tmp_path)
    (state.workdir / "taken.work.wav").write_bytes(b"x")
    result = state.rename_workdir_file("lesson.work.wav", "taken")
    assert result["ok"] is False
    assert "已存在" in (result.get("error") or "")


def test_rename_workdir_file_rejects_while_busy(tmp_path: Path):
    state = _make_state(tmp_path)
    state.job = {"status": "running"}
    result = state.rename_workdir_file("lesson.work.wav", "new-name")
    assert result["ok"] is False
    assert "處理中" in (result.get("error") or "")
