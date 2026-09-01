from pathlib import Path

from yt_decoder import ytdlp


def test_ytdlp_candidates_include_windows_scripts(monkeypatch, tmp_path: Path):
    py = tmp_path / "python" / "python.exe"
    py.parent.mkdir()
    py.write_bytes(b"")
    (tmp_path / "python" / "Scripts").mkdir()
    monkeypatch.setattr(ytdlp.sys, "executable", str(py))
    monkeypatch.setattr(ytdlp.sys, "platform", "win32")
    monkeypatch.delenv("YTJ_SUPPORT", raising=False)
    monkeypatch.setenv("PATH", "")

    candidates = ytdlp._ytdlp_candidates()
    assert tmp_path / "python" / "Scripts" / "yt-dlp.exe" in candidates


def test_ytdlp_argv_finds_scripts_binary(monkeypatch, tmp_path: Path):
    py = tmp_path / "python" / "python.exe"
    py.parent.mkdir()
    py.write_bytes(b"")
    scripts = tmp_path / "python" / "Scripts"
    scripts.mkdir()
    exe = scripts / "yt-dlp.exe"
    exe.write_bytes(b"")
    monkeypatch.setattr(ytdlp.sys, "executable", str(py))
    monkeypatch.setattr(ytdlp.sys, "platform", "win32")
    monkeypatch.delenv("YTJ_SUPPORT", raising=False)
    monkeypatch.setenv("PATH", "")
    ytdlp._YTDLP_ARGV = None

    assert ytdlp.ytdlp_argv() == [str(exe)]
