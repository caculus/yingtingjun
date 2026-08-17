"""Windows/macOS runtime helpers (no ASR / ffmpeg)."""

from pathlib import Path

from platform_runtime import (
    apply_model_cache_env,
    port_is_listening,
    resolve_diarizer_name,
    resolve_models_dir,
    resolve_venv_python,
    transcribe_child_env,
    transcribe_cmd,
    transcribe_import_args,
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


def test_resolve_models_dir_env_override(tmp_path: Path):
    custom = tmp_path / "pack-models"
    found = resolve_models_dir(root=tmp_path, env={"YTJ_MODELS_DIR": str(custom)})
    assert found == custom


def test_resolve_models_dir_packaged_app_sibling(tmp_path: Path):
    app = tmp_path / "app"
    models = tmp_path / "models"
    app.mkdir()
    models.mkdir()
    assert resolve_models_dir(root=app, env={}) == models


def test_resolve_models_dir_dev_repo_default(tmp_path: Path):
    assert resolve_models_dir(root=tmp_path, env={}) == tmp_path / "models"


def test_apply_model_cache_env_sets_hf_home():
    env = apply_model_cache_env({"YTJ_MODELS_DIR": r"C:\Yingtingjun\models", "PATH": "x"})
    assert env["HF_HOME"] == r"C:\Yingtingjun\models"
    assert env["HUGGINGFACE_HUB_CACHE"].endswith("hub")
    assert env["PATH"] == "x"


def test_transcribe_child_env_honors_models_dir(tmp_path: Path):
    models = tmp_path / "models"
    env = transcribe_child_env({"YTJ_MODELS_DIR": str(models), "PATH": "/bin"})
    assert env["HF_HOME"] == str(models)
    assert env["PYTHONUNBUFFERED"] == "1"


def test_transcribe_import_args_pass_data_dirs():
    args = transcribe_import_args("talk.m4a", "/data/workdir", "/data/output")
    assert args == [
        "talk.m4a",
        "--workdir",
        "/data/workdir",
        "--outdir",
        "/data/output",
    ]


def test_port_is_listening_roundtrip():
    import socket

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port = srv.getsockname()[1]
    try:
        assert port_is_listening("127.0.0.1", port)
    finally:
        srv.close()
    assert not port_is_listening("127.0.0.1", port)
