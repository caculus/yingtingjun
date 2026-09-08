"""Translation and Whisper via Yingtingjun transcribe module."""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from yt_decoder.io_util import log_stage
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


def _report_translate_progress(done: int, total: int) -> None:
    if total <= 0:
        log_stage("translate", "0/0")
        return
    if done <= 0:
        log_stage("translate", f"0/{total}（載入翻譯模型中…）")
        return
    pct = int(round(100.0 * done / total))
    log_stage("translate", f"{done}/{total}（{pct}%）")


def translate_turns(
    turns: list[dict[str, Any]],
    *,
    yingtingjun_root: Path | None = None,
) -> None:
    """Fill text_zh on each turn in-place using Yingtingjun NLLB."""
    total = len(turns)
    try:
        from transcribe import translate_turns as _translate_turns
    except ImportError:
        _translate_turns = None

    if _translate_turns is not None:
        real_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            _translate_turns(turns, on_progress=_report_translate_progress)
        finally:
            sys.stdout = real_stdout
        return

    root = _require_yingtingjun_root(yingtingjun_root)
    transcribe_py = root / "transcribe.py"
    if not transcribe_py.is_file():
        raise RuntimeError(f"找不到 {transcribe_py}")

    python = _resolve_python(root)
    # Subprocess fallback: stream progress lines from a thin runner script.
    script = (
        "import json, sys\n"
        "sys.path.insert(0, sys.argv[1])\n"
        "from transcribe import translate_turns\n"
        "turns = json.loads(sys.stdin.read())\n"
        "def on_progress(done, total):\n"
        "    print(f'PROGRESS {done}/{total}', flush=True)\n"
        "translate_turns(turns, on_progress=on_progress)\n"
        "print('RESULT ' + json.dumps(turns, ensure_ascii=False), flush=True)\n"
    )
    payload = json.dumps(turns, ensure_ascii=False)
    proc = subprocess.Popen(
        [str(python), "-u", "-c", script, str(root)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=_transcribe_env(),
    )
    assert proc.stdin is not None
    assert proc.stdout is not None
    proc.stdin.write(payload)
    proc.stdin.close()

    result_json = None
    for line in proc.stdout:
        line = line.rstrip("\n")
        if line.startswith("PROGRESS "):
            parts = line[len("PROGRESS ") :].split("/", 1)
            if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                _report_translate_progress(int(parts[0]), int(parts[1]))
            continue
        if line.startswith("RESULT "):
            result_json = line[len("RESULT ") :]
    stderr = proc.stderr.read() if proc.stderr is not None else ""
    code = proc.wait()
    if code != 0 or not result_json:
        err = (stderr or "translate failed").strip()
        raise RuntimeError(f"翻譯失敗：{err}")

    translated = json.loads(result_json)
    turns.clear()
    turns.extend(translated)
    if total:
        _report_translate_progress(total, total)


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
