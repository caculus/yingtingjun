"""Shared stderr logging and file publish helpers."""

from __future__ import annotations

import shutil
import sys
import threading
from collections.abc import Callable
from pathlib import Path

_thread_state = threading.local()
LogHook = Callable[[str, str], None]


def set_log_hook(hook: LogHook | None) -> None:
    """Attach a per-thread stage log listener (used by web SSE)."""
    _thread_state.hook = hook


def log_stage(stage: str, message: str) -> None:
    line = f"[{stage}] {message}"
    print(line, file=sys.stderr, flush=True)
    hook = getattr(_thread_state, "hook", None)
    if hook is not None:
        try:
            hook(stage, message)
        except Exception:  # noqa: BLE001
            pass


def publish_audio_copy(audio_path: Path, uploads_dir: Path) -> Path:
    """Keep a copy in uploads/ (yingtingjun import convention)."""
    uploads_dir.mkdir(parents=True, exist_ok=True)
    uploads_copy = uploads_dir / audio_path.name
    if uploads_copy.resolve() != audio_path.resolve():
        shutil.copy2(audio_path, uploads_copy)
    return uploads_copy
