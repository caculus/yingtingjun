"""Stem sanitization and file grouping."""

from pathlib import Path

import pytest

from stem_utils import (
    StemError,
    iter_files_for_stem,
    path_matches_stem,
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
