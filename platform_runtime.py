#!/usr/bin/env python3
"""OS-specific runtime helpers: stdio, diarizer defaults, venv python, child env.

Launch contract (packaged Win/macOS/Linux launchers must honor this):
  CLI: --workdir --outdir --uploads --notesdir on serve_player.py
  Env: YTJ_MODELS_DIR, YTJ_FFMPEG, ECDICT_DB, PYTHONUTF8=1
  If YTJ_MODELS_DIR is set, Hugging Face caches are pointed there.
  If port 8765 is already bound, open the existing UI instead of a second server.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path

_ROOT = Path(__file__).resolve().parent


def configure_stdio() -> None:
    """UTF-8 + line-buffered stdout/stderr (helps Windows consoles and player logs)."""
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if not callable(reconfigure):
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
        except Exception:
            pass


def resolve_diarizer_name(requested: str = "auto", *, platform: str | None = None) -> str:
    """auto → ecapa on Windows/Linux; keep auto on macOS (speakrs then ECAPA)."""
    choice = (requested or "auto").strip().lower()
    if choice not in {"auto", "speakrs", "ecapa"}:
        raise ValueError(f"Unknown diarizer: {requested}")
    if choice != "auto":
        return choice
    plat = (platform or sys.platform).lower()
    if plat.startswith("win") or plat.startswith("linux"):
        return "ecapa"
    return "auto"


def resolve_venv_python(root: Path | None = None) -> Path:
    root = Path(root) if root is not None else _ROOT
    exe = Path(sys.executable).resolve()
    try:
        exe.relative_to((root / ".venv").resolve())
        return exe
    except ValueError:
        pass
    candidates = (
        root / ".venv" / "bin" / "python",
        root / ".venv" / "bin" / "python3",
        root / ".venv" / "Scripts" / "python.exe",
        root / ".venv" / "Scripts" / "python3.exe",
    )
    for path in candidates:
        if path.exists():
            return path
    return Path(sys.executable)


def resolve_models_dir(
    root: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> Path:
    """YTJ_MODELS_DIR → packaged sibling models/ (when code lives in app/) → <root>/models."""
    environ = os.environ if env is None else env
    raw = str(environ.get("YTJ_MODELS_DIR") or "").strip()
    if raw:
        return Path(raw).expanduser()
    root = Path(root) if root is not None else _ROOT
    if root.name.lower() == "app":
        sibling = root.parent / "models"
        if sibling.is_dir():
            return sibling
    return root / "models"


def apply_model_cache_env(env: dict[str, str] | None = None) -> dict[str, str]:
    """When YTJ_MODELS_DIR is set, keep HF / transformers caches inside it."""
    out = dict(os.environ if env is None else env)
    models = str(out.get("YTJ_MODELS_DIR") or "").strip()
    if models:
        models_path = Path(models).expanduser()
        out.setdefault("HF_HOME", str(models_path))
        hub = str(models_path / "hub")
        out.setdefault("HUGGINGFACE_HUB_CACHE", hub)
        out.setdefault("TRANSFORMERS_CACHE", hub)
    return out


def transcribe_child_env(base: dict[str, str] | None = None) -> dict[str, str]:
    env = apply_model_cache_env(dict(os.environ if base is None else base))
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONUTF8"] = "1"
    env.setdefault("PYTHONIOENCODING", "utf-8")
    return env


def transcribe_import_args(
    source: Path | str, workdir: Path | str, outdir: Path | str
) -> list[str]:
    """CLI tail so player import jobs write into the launched data dirs."""
    return [str(source), "--workdir", str(workdir), "--outdir", str(outdir)]


def port_is_listening(host: str, port: int, timeout: float = 0.25) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def transcribe_cmd(python: Path | str, transcribe_py: Path | str, *args: str) -> list[str]:
    """Invoke transcribe.py unbuffered (`-u`) so player logs flush on Windows."""
    out = [str(python), "-u", str(transcribe_py)]
    out.extend(str(a) for a in args)
    return out


def subprocess_extra_kwargs() -> dict:
    extra: dict = {}
    if sys.platform.startswith("win"):
        extra["creationflags"] = int(getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return extra
