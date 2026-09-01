"""Translation and Whisper via Yingtingjun transcribe module."""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from yt_decoder.util import resolve_yingtingjun_root


def _resolve_python(root: Path) -> Path:
    for rel in (".venv/bin/python", ".venv/bin/python3", ".venv/Scripts/python.exe"):
        candidate = root / rel
        if candidate.is_file():
            return candidate
    return Path(sys.executable)


def _transcribe_env() -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONUTF8"] = "1"
    env.setdefault("PYTHONIOENCODING", "utf-8")
    models = str(env.get("YTJ_MODELS_DIR") or "").strip()
    if models:
        models_path = Path(models).expanduser()
        hub = str(models_path / "hub")
        env.setdefault("HF_HOME", str(models_path))
        env.setdefault("HUGGINGFACE_HUB_CACHE", hub)
        env.setdefault("TRANSFORMERS_CACHE", hub)
    return env


def _require_yingtingjun_root(yingtingjun_root: Path | None) -> Path:
    root = yingtingjun_root or resolve_yingtingjun_root()
    if root is None:
        raise RuntimeError(
            "找不到英聽君路徑；請設定 YT_DECODER_YINGTINGJUN 或 --yingtingjun"
        )
    return root


def translate_turns(
    turns: list[dict[str, Any]],
    *,
    yingtingjun_root: Path | None = None,
) -> None:
    """Fill text_zh on each turn in-place using Yingtingjun NLLB."""
    try:
        from transcribe import translate_turns as _translate_turns
    except ImportError:
        _translate_turns = None

    if _translate_turns is not None:
        real_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            _translate_turns(turns)
        finally:
            sys.stdout = real_stdout
        return

    root = _require_yingtingjun_root(yingtingjun_root)
    transcribe_py = root / "transcribe.py"
    if not transcribe_py.is_file():
        raise RuntimeError(f"找不到 {transcribe_py}")

    python = _resolve_python(root)
    script = (
        "import io, json, sys\n"
        "sys.path.insert(0, sys.argv[1])\n"
        "from transcribe import translate_turns\n"
        "turns = json.loads(sys.stdin.read())\n"
        "real_stdout = sys.stdout\n"
        "sys.stdout = io.StringIO()\n"
        "try:\n"
        "    translate_turns(turns)\n"
        "finally:\n"
        "    sys.stdout = real_stdout\n"
        "json.dump(turns, real_stdout, ensure_ascii=False)\n"
    )
    payload = json.dumps(turns, ensure_ascii=False)
    result = subprocess.run(
        [str(python), "-u", "-c", script, str(root)],
        input=payload,
        capture_output=True,
        text=True,
        check=False,
        env=_transcribe_env(),
    )
    if result.returncode != 0:
        err = (result.stderr or result.stdout or "translate failed").strip()
        raise RuntimeError(f"翻譯失敗：{err}")

    translated = json.loads(result.stdout)
    turns.clear()
    turns.extend(translated)


def run_yingtingjun_transcribe(
    audio_path: Path,
    outdir: Path,
    workdir: Path,
    *,
    yingtingjun_root: Path | None = None,
    skip_translate: bool = False,
) -> None:
    """Whisper fallback: subprocess yingtingjun/transcribe.py."""
    root = _require_yingtingjun_root(yingtingjun_root)
    transcribe_py = root / "transcribe.py"
    if not transcribe_py.is_file():
        raise RuntimeError(f"找不到 {transcribe_py}")

    python = _resolve_python(root)
    cmd = [
        str(python),
        "-u",
        str(transcribe_py),
        str(audio_path),
        "--outdir",
        str(outdir),
        "--workdir",
        str(workdir),
    ]
    if skip_translate:
        cmd.append("--skip-translate")

    result = subprocess.run(
        cmd,
        check=False,
        env=_transcribe_env(),
        cwd=str(root),
    )
    if result.returncode != 0:
        raise RuntimeError(f"Whisper 轉寫失敗（exit {result.returncode}）")
