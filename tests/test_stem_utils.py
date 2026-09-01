"""Stem sanitization and file grouping."""

import json
from pathlib import Path

import pytest

from stem_utils import (
    StemCollisionError,
    StemError,
    build_stem_rename_plan,
    execute_stem_rename,
    iter_files_for_stem,
    path_matches_stem,
    renamed_file_path,
    sanitize_stem,
)


def test_sanitize_stem_keeps_chinese():
    assert sanitize_stem("  超市結帳  ") == "超市結帳"


def test_sanitize_stem_replaces_invalid_chars():
    assert sanitize_stem("面試/練習") == "面試-練習"
    assert sanitize_stem('bad:name') == "bad-name"


def test_sanitize_stem_rejects_empty():
    with pytest.raises(StemError, match="不可為空"):
        sanitize_stem("   ")
    with pytest.raises(StemError, match="不可為空"):
        sanitize_stem("...")


def test_sanitize_stem_truncates_long_names():
    long_name = "a" * 120
    assert len(sanitize_stem(long_name)) == 80


def test_sanitize_stem_avoids_windows_reserved_names():
    assert sanitize_stem("CON").endswith("_")
    assert sanitize_stem("com1").endswith("_")


def test_path_matches_stem_work_wav():
    path = Path("lesson.work.wav")
    assert path_matches_stem(path, "lesson")
    assert path_matches_stem(Path("lesson.json.bak-range"), "lesson")


def test_iter_files_for_stem_collects_related_files(tmp_path: Path):
    workdir = tmp_path / "workdir"
    outdir = tmp_path / "output"
    uploads = tmp_path / "uploads"
    notesdir = tmp_path / "notes"
    for d in (workdir, outdir, uploads, notesdir):
        d.mkdir()
    (workdir / "lesson.work.wav").write_bytes(b"wav")
    (outdir / "lesson.json").write_text("{}", encoding="utf-8")
    (outdir / "lesson.whisper.json").write_text("{}", encoding="utf-8")
    (uploads / "lesson.m4a").write_bytes(b"m4a")
    (notesdir / "lesson.json").write_text('{"stem":"lesson"}', encoding="utf-8")
    (workdir / "other.work.wav").write_bytes(b"x")

    found = {p.name for p in iter_files_for_stem(
        workdir=workdir,
        outdir=outdir,
        uploads=uploads,
        notesdir=notesdir,
        stem="lesson",
    )}
    assert found == {"lesson.work.wav", "lesson.json", "lesson.whisper.json", "lesson.m4a"}


def test_renamed_file_path_variants():
    assert renamed_file_path(Path("lesson.work.wav"), "lesson", "new").name == "new.work.wav"
    assert renamed_file_path(Path("lesson.json.bak-range"), "lesson", "new").name == "new.json.bak-range"
    assert renamed_file_path(Path("lesson.m4a"), "lesson", "new").name == "new.m4a"


def test_build_stem_rename_plan_rejects_collision(tmp_path: Path):
    workdir = tmp_path / "workdir"
    workdir.mkdir()
    (workdir / "old.work.wav").write_bytes(b"wav")
    (workdir / "new.work.wav").write_bytes(b"x")
    files = iter_files_for_stem(
        workdir=workdir,
        outdir=tmp_path / "output",
        uploads=tmp_path / "uploads",
        notesdir=tmp_path / "notes",
        stem="old",
    )
    with pytest.raises(StemCollisionError):
        build_stem_rename_plan(files, "old", "new")


def test_execute_stem_rename_moves_files(tmp_path: Path):
    workdir = tmp_path / "workdir"
    outdir = tmp_path / "output"
    uploads = tmp_path / "uploads"
    notesdir = tmp_path / "notes"
    for d in (workdir, outdir, uploads, notesdir):
        d.mkdir()
    (workdir / "lesson.work.wav").write_bytes(b"wav")
    (outdir / "lesson.json").write_text('{"turns":[]}', encoding="utf-8")
    (uploads / "lesson.m4a").write_bytes(b"m4a")
    (notesdir / "lesson.json").write_text('{"stem":"lesson","notes":[]}', encoding="utf-8")

    files = iter_files_for_stem(
        workdir=workdir,
        outdir=outdir,
        uploads=uploads,
        notesdir=notesdir,
        stem="lesson",
    )
    plan = build_stem_rename_plan(files, "lesson", "面試練習")
    execute_stem_rename(plan)

    assert (workdir / "面試練習.work.wav").exists()
    assert not (workdir / "lesson.work.wav").exists()
    assert (outdir / "面試練習.json").exists()
    notes = json.loads((notesdir / "面試練習.json").read_text(encoding="utf-8"))
    assert notes["stem"] == "lesson"  # stem field not auto-updated by execute_stem_rename
