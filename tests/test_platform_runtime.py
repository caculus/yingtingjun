"""Windows/macOS runtime helpers (no ASR / ffmpeg)."""

from pathlib import Path

from platform_runtime import (
    resolve_diarizer_name,
    resolve_venv_python,
    transcribe_child_env,
    transcribe_cmd,
)


def test_resolve_diarizer_auto_by_platform():
    assert resolve_diarizer_name("auto", platform="darwin") == "auto"
    assert resolve_diarizer_name("auto", platform="win32") == "ecapa"
    assert resolve_diarizer_name("auto", platform="linux") == "ecapa"


def test_resolve_diarizer_explicit_unchanged():
    assert resolve_diarizer_name("speakrs", platform="win32") == "speakrs"
    assert resolve_diarizer_name("ecapa", platform="darwin") == "ecapa"


def test_transcribe_cmd_inserts_unbuffered_flag():
    cmd = transcribe_cmd("/venv/python.exe", "transcribe.py", "talk.m4a")
    assert cmd[:3] == ["/venv/python.exe", "-u", "transcribe.py"]
    assert cmd[-1] == "talk.m4a"


def test_transcribe_child_env_forces_utf8_and_unbuffered():
    env = transcribe_child_env({"PATH": "/bin", "LANG": "C"})
    assert env["PYTHONUNBUFFERED"] == "1"
    assert env["PYTHONUTF8"] == "1"
    assert env["PYTHONIOENCODING"] == "utf-8"
    assert env["PATH"] == "/bin"


def test_resolve_venv_python_prefers_existing_path(tmp_path: Path):
    scripts = tmp_path / ".venv" / "Scripts"
    scripts.mkdir(parents=True)
    exe = scripts / "python.exe"
    exe.write_text("")
    found = resolve_venv_python(tmp_path)
    assert found == exe
