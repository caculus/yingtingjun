"""Tests for bundled demo lesson seeding."""

from __future__ import annotations

import shutil
from pathlib import Path

from demo_seed import DEMO_AUDIO_NAME, DEMO_JSON_NAME, DEMO_STEM, seed_demo_lesson


def test_seed_demo_copies_into_study_dirs(tmp_path: Path):
    app = tmp_path / "app"
    demo = app / "demo"
    demo.mkdir(parents=True)
    # Minimal placeholder bytes (seed only checks file presence + copy).
    (demo / DEMO_AUDIO_NAME).write_bytes(b"ID3demo")
    (demo / DEMO_JSON_NAME).write_text(
        '{"language":"en","bilingual":true,"turns":[{"speaker":"SPEAKER_01","start":0,"end":1,"text":"Hi","text_zh":"嗨","words":[]}]}',
        encoding="utf-8",
    )

    uploads = tmp_path / "data" / "uploads"
    workdir = tmp_path / "data" / "workdir"
    outdir = tmp_path / "data" / "output"

    first = seed_demo_lesson(uploads, workdir, outdir, app_root=app)
    assert first["ok"] is True
    assert first["seeded"] is True
    assert first["stem"] == DEMO_STEM
    assert (uploads / DEMO_AUDIO_NAME).is_file()
    assert (workdir / DEMO_AUDIO_NAME).is_file()
    assert (outdir / DEMO_JSON_NAME).is_file()
    assert (uploads.parent / ".ytj_demo_seeded").is_file()

    second = seed_demo_lesson(uploads, workdir, outdir, app_root=app)
    assert second["ok"] is True
    assert second["seeded"] is False
    assert second["already_present"] is True


def test_seed_demo_does_not_recreate_after_user_delete(tmp_path: Path):
    app = tmp_path / "app"
    demo = app / "demo"
    demo.mkdir(parents=True)
    (demo / DEMO_AUDIO_NAME).write_bytes(b"ID3demo")
    (demo / DEMO_JSON_NAME).write_text('{"turns":[{"text":"x","words":[]}]}', encoding="utf-8")

    uploads = tmp_path / "data" / "uploads"
    workdir = tmp_path / "data" / "workdir"
    outdir = tmp_path / "data" / "output"
    seed_demo_lesson(uploads, workdir, outdir, app_root=app)

    (uploads / DEMO_AUDIO_NAME).unlink()
    (workdir / DEMO_AUDIO_NAME).unlink()
    (outdir / DEMO_JSON_NAME).unlink()

    again = seed_demo_lesson(uploads, workdir, outdir, app_root=app)
    assert again["ok"] is True
    assert again.get("skipped") is True
    assert not (workdir / DEMO_AUDIO_NAME).exists()

    forced = seed_demo_lesson(uploads, workdir, outdir, app_root=app, force=True)
    assert forced["ok"] is True
    assert (workdir / DEMO_AUDIO_NAME).is_file()
