"""Tests for vendored yt_decoder integration."""

from pathlib import Path

from yt_decoder.types import ImportOptions
from yt_decoder.util import resolve_import_stem, resolve_yingtingjun_root, sanitize_stem


class _FakeProbe:
    title = "How Citizens Not Politicians"
    video_id = "abc123xyz"


def test_sanitize_stem_includes_video_id():
    stem = sanitize_stem("How Citizens Not Politicians", "abc123xyz")
    assert stem.endswith("-abc123xyz")
    assert "how-citizens" in stem


def test_resolve_import_stem_prefers_user_stem():
    probe = _FakeProbe()
    options = ImportOptions.from_data_root(
        Path("/tmp/data"),
        preferred_stem="my-lesson",
    )
    assert resolve_import_stem(probe, options) == "my-lesson"


def test_resolve_yingtingjun_root_points_at_repo():
    root = resolve_yingtingjun_root()
    assert root is not None
    assert (root / "transcribe.py").is_file()
    assert (root / "yt_decoder" / "import_video.py").is_file()


def test_import_options_from_yingtingjun_paths(tmp_path: Path):
    output_dir = tmp_path / "output"
    workdir = tmp_path / "workdir"
    uploads = tmp_path / "uploads"
    options = ImportOptions.from_yingtingjun(
        output_dir=output_dir,
        workdir=workdir,
        uploads_dir=uploads,
        mode="caption",
    )
    assert options.output_dir == output_dir
    assert options.workdir == workdir
    assert options.uploads_dir == uploads
    assert options.mode == "caption"
