"""Bilingual transcript export helpers (no ASR)."""

import io
import zipfile
from pathlib import Path

from export_transcript import (
    build_export_download,
    format_export_ts,
    render_html,
    render_md,
    render_txt,
    write_export_files,
)


TURNS = [
    {
        "speaker": "SPEAKER_01",
        "start": 0.0,
        "end": 7.2,
        "text": "Hello there.",
        "text_zh": "你好。",
    },
    {
        "speaker": "SPEAKER_02",
        "start": 8.0,
        "end": 9.5,
        "text": "Thanks.",
        "text_zh": "謝謝。",
    },
]


def test_format_export_ts():
    assert format_export_ts(7.2) == "00:07"
    assert format_export_ts(65) == "01:05"


def test_render_txt_default_without_timestamps():
    text = render_txt(TURNS, include_timestamps=False)
    assert "SPEAKER_01" in text
    assert "Hello there." in text
    assert "你好。" in text
    assert "→" not in text


def test_render_txt_without_speakers():
    text = render_txt(TURNS, include_speakers=False, include_timestamps=False)
    assert "SPEAKER_01" not in text
    assert "Hello there." in text
    assert text.index("Hello there.") < text.index("你好。")


def test_render_txt_with_timestamps():
    text = render_txt(TURNS, include_timestamps=True)
    assert "00:00 → 00:07" in text
    assert "00:08 → 00:10" in text  # 9.5s rounds to 10
    assert "SPEAKER_01" in text


def test_render_md_and_html():
    md = render_md(TURNS, include_timestamps=False, title="lesson")
    assert md.startswith("# lesson")
    assert "Speakers: yes" in md
    assert "Timestamps: no" in md
    html = render_html(
        TURNS, include_speakers=True, include_timestamps=True, title="lesson"
    )
    assert "<!DOCTYPE html>" in html
    assert 'class="en"' in html
    assert 'class="zh"' in html
    assert "含說話者" in html
    assert "含時間戳" in html
    assert "Hello there." in html


def test_write_export_files(tmp_path: Path):
    written = write_export_files(
        TURNS,
        directory=tmp_path,
        basename="demo",
        formats=["txt", "html"],
        include_timestamps=False,
    )
    names = sorted(p.name for p in written)
    assert names == ["demo.html", "demo.txt"]
    assert "SPEAKER_01" in (tmp_path / "demo.txt").read_text(encoding="utf-8")
    assert "Hello there." in (tmp_path / "demo.html").read_text(encoding="utf-8")


def test_write_export_requires_format(tmp_path: Path):
    try:
        write_export_files(TURNS, directory=tmp_path, basename="x", formats=[])
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "格式" in str(exc)


def test_build_export_download_single_and_zip():
    name, body, mime = build_export_download(
        TURNS, basename="demo", formats=["txt"], include_timestamps=False
    )
    assert name == "demo.txt"
    assert mime.startswith("text/plain")
    assert b"Hello there." in body

    zname, zbody, zmime = build_export_download(
        TURNS, basename="demo", formats=["txt", "md", "html"], include_timestamps=True
    )
    assert zname == "demo.zip"
    assert zmime == "application/zip"
    with zipfile.ZipFile(io.BytesIO(zbody)) as zf:
        assert sorted(zf.namelist()) == ["demo.html", "demo.md", "demo.txt"]
