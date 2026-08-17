"""Audio conversion helpers (no real ffmpeg / afconvert)."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from audio_convert import (
    TARGET_SR,
    build_ffmpeg_cmd,
    convert_to_work_wav,
    find_ffmpeg_bin,
    try_copy_16k_mono_wav,
)


def test_find_ffmpeg_env_override(tmp_path: Path):
    fake = tmp_path / "custom-ffmpeg"
    fake.write_text("")
    found = find_ffmpeg_bin(
        env={"YTJ_FFMPEG": str(fake), "FFMPEG_BIN": "/nope"},
        repo_root=tmp_path / "empty-repo",
        which=lambda _: None,
    )
    assert found == fake


def test_find_ffmpeg_repo_bin_exe(tmp_path: Path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    exe = bin_dir / "ffmpeg.exe"
    exe.write_text("")
    found = find_ffmpeg_bin(env={}, repo_root=tmp_path, which=lambda _: None)
    assert found == exe


def test_find_ffmpeg_packaged_parent_bin(tmp_path: Path):
    app = tmp_path / "app"
    app.mkdir()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    exe = bin_dir / "ffmpeg.exe"
    exe.write_text("")
    found = find_ffmpeg_bin(env={}, repo_root=app, which=lambda _: None)
    assert found == exe


def test_find_ffmpeg_path_which(tmp_path: Path):
    on_path = tmp_path / "ffmpeg"
    on_path.write_text("")
    found = find_ffmpeg_bin(
        env={},
        repo_root=tmp_path / "no-bin",
        which=lambda name: str(on_path) if name == "ffmpeg" else None,
    )
    assert found == on_path


def test_find_ffmpeg_winget_links(tmp_path: Path):
    links = tmp_path / "Local" / "Microsoft" / "WinGet" / "Links"
    links.mkdir(parents=True)
    exe = links / "ffmpeg.exe"
    exe.write_text("")
    found = find_ffmpeg_bin(
        env={"LOCALAPPDATA": str(tmp_path / "Local")},
        repo_root=tmp_path / "no-bin",
        which=lambda _: None,
    )
    assert found == exe


def test_find_ffmpeg_winget_package_glob(tmp_path: Path):
    pkg = tmp_path / "Local" / "Microsoft" / "WinGet" / "Packages" / "Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe"
    bin_dir = pkg / "ffmpeg-7.1-full_build" / "bin"
    bin_dir.mkdir(parents=True)
    exe = bin_dir / "ffmpeg.exe"
    exe.write_text("")
    found = find_ffmpeg_bin(
        env={"LOCALAPPDATA": str(tmp_path / "Local")},
        repo_root=tmp_path / "no-bin",
        which=lambda _: None,
    )
    assert found == exe


def test_build_ffmpeg_cmd_is_16k_mono_pcm():
    cmd = build_ffmpeg_cmd(Path("/usr/bin/ffmpeg"), Path("in.m4a"), Path("out.work.wav"))
    assert Path(cmd[0]) == Path("/usr/bin/ffmpeg")
    assert "-ar" in cmd and str(TARGET_SR) in cmd
    assert "-ac" in cmd and "1" in cmd
    assert "pcm_s16le" in cmd
    assert "-y" in cmd


def test_convert_prefers_afconvert_over_ffmpeg(tmp_path: Path):
    src = tmp_path / "talk.m4a"
    src.write_bytes(b"fake")
    dest = tmp_path / "talk.work.wav"
    ran: list[list[str]] = []

    def fake_run(cmd, check=True, capture_output=True, text=True):
        ran.append(list(cmd))
        dest.write_bytes(b"RIFF")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    used = convert_to_work_wav(
        src,
        dest,
        ffmpeg=Path("/usr/bin/ffmpeg"),
        afconvert=Path("/usr/bin/afconvert"),
        run=fake_run,
    )
    assert used == "afconvert"
    assert Path(ran[0][0]) == Path("/usr/bin/afconvert")
    assert dest.exists()


def test_convert_uses_ffmpeg_when_no_afconvert(tmp_path: Path):
    src = tmp_path / "talk.m4a"
    src.write_bytes(b"fake")
    dest = tmp_path / "talk.work.wav"
    ran: list[list[str]] = []

    def fake_run(cmd, check=True, capture_output=True, text=True):
        ran.append(list(cmd))
        dest.write_bytes(b"RIFF")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    used = convert_to_work_wav(
        src,
        dest,
        ffmpeg=Path("/usr/bin/ffmpeg"),
        afconvert=None,
        run=fake_run,
    )
    assert used == "ffmpeg"
    assert Path(ran[0][0]) == Path("/usr/bin/ffmpeg")
    assert "-ar" in ran[0] and "16000" in ran[0]


def test_convert_soundfile_fallback(tmp_path: Path):
    src = tmp_path / "talk.m4a"
    src.write_bytes(b"fake")
    dest = tmp_path / "talk.work.wav"
    called: list[Path] = []

    def fallback(source: Path, target: Path) -> None:
        called.append(source)
        target.write_bytes(b"RIFF")

    used = convert_to_work_wav(
        src,
        dest,
        ffmpeg=None,
        afconvert=None,
        soundfile_fallback=fallback,
    )
    assert used == "soundfile"
    assert called == [src]
    assert dest.exists()


def test_convert_error_mentions_ffmpeg_when_nothing_works(tmp_path: Path):
    src = tmp_path / "talk.m4a"
    src.write_bytes(b"fake")
    dest = tmp_path / "talk.work.wav"
    with pytest.raises(RuntimeError, match="ffmpeg"):
        convert_to_work_wav(
            src,
            dest,
            ffmpeg=None,
            afconvert=None,
            soundfile_fallback=None,
        )


def test_try_copy_16k_wav(tmp_path: Path):
    import numpy as np
    import soundfile as sf

    src = tmp_path / "already.wav"
    dest = tmp_path / "already.work.wav"
    sf.write(str(src), np.zeros(1600, dtype=np.float32), 16000, subtype="PCM_16")
    assert try_copy_16k_mono_wav(src, dest) is True
    assert dest.exists()
    _audio, sr = sf.read(str(dest))
    assert sr == 16000
