#!/usr/bin/env python3
"""OS-specific runtime helpers: stdio, diarizer defaults, venv python, child env."""

from __future__ import annotations

import os
import subprocess
import sys
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


def transcribe_child_env(base: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(os.environ if base is None else base)
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONUTF8"] = "1"
    env.setdefault("PYTHONIOENCODING", "utf-8")
    return env


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
