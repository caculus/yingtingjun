#!/usr/bin/env python3
"""ASR backends: MLX Whisper (macOS) or faster-whisper (Windows / CPU / CUDA)."""

from __future__ import annotations

import os
import sys
from typing import Any, Protocol

import numpy as np

from progress_log import asr_progress_pct, heartbeat, log_line, should_emit_progress

MLX_DEFAULT_MODEL = "mlx-community/whisper-large-v3-turbo"
FASTER_DEFAULT_MODEL = "large-v3-turbo"

# Map common MLX HF repos → faster-whisper CTranslate2 names.
_MLX_TO_FASTER = {
    "mlx-community/whisper-large-v3-turbo": "large-v3-turbo",
    "mlx-community/whisper-large-v3": "large-v3",
    "mlx-community/whisper-medium": "medium",
    "mlx-community/whisper-small": "small",
    "mlx-community/whisper-base": "base",
    "mlx-community/whisper-tiny": "tiny",
}

_FASTER_TO_MLX = {v: k for k, v in _MLX_TO_FASTER.items()}

_session_name: str | None = None
_session_backend: "AsrBackend | None" = None
_faster_models: dict[tuple[str, str, str], Any] = {}


class AsrBackend(Protocol):
    name: str

    def detect_language(
        self,
        audio: np.ndarray,
        sr: int,
        model: str,
        probe_sec: float = 45.0,
    ) -> str: ...

    def transcribe(
        self,
        audio: np.ndarray,
        model: str,
        language: str = "en",
        *,
        condition_on_previous_text: bool = True,
        compression_ratio_threshold: float | None = 2.4,
    ) -> dict: ...


def resolve_asr_name(
    requested: str = "auto",
    *,
    platform: str | None = None,
    mlx_importable: bool | None = None,
) -> str:
    """Pick mlx | faster. auto: Windows/Linux → faster; macOS → mlx if importable."""
    choice = (requested or "auto").strip().lower()
    if choice not in {"auto", "mlx", "faster"}:
        raise ValueError(f"Unknown ASR backend: {requested}")
    if choice != "auto":
        return choice

    plat = (platform or sys.platform).lower()
    if plat.startswith("win") or plat.startswith("linux"):
        return "faster"

    if mlx_importable is None:
        mlx_importable = _module_importable("mlx_whisper")
    return "mlx" if mlx_importable else "faster"


def default_model_for(backend: str) -> str:
    return FASTER_DEFAULT_MODEL if backend == "faster" else MLX_DEFAULT_MODEL


def resolve_model_name(backend: str, model: str | None) -> str:
    """Translate model id between MLX HF repos and faster-whisper names."""
    backend = (backend or "mlx").strip().lower()
    raw = (model or "").strip()
    if not raw:
        return default_model_for(backend)

    if backend == "faster":
        if raw in _MLX_TO_FASTER:
            return _MLX_TO_FASTER[raw]
        if raw.startswith("mlx-community/whisper-"):
            return raw.rsplit("/", 1)[-1].removeprefix("whisper-")
        return raw

    if backend == "mlx":
        if raw in _FASTER_TO_MLX:
            return _FASTER_TO_MLX[raw]
        if "/" not in raw and not raw.startswith("mlx-"):
            slug = raw if raw.startswith("whisper-") else f"whisper-{raw}"
            mapped = f"mlx-community/{slug}"
            if mapped in _MLX_TO_FASTER or slug.replace("whisper-", "") in _FASTER_TO_MLX:
                return mapped
            return mapped
        return raw

    return raw


def faster_whisper_result_to_dict(segments: list[Any], language: str) -> dict:
    """Normalize faster-whisper segments into openai/mlx-whisper-like JSON."""
    out_segs: list[dict] = []
    texts: list[str] = []
    for seg in segments:
        words_out: list[dict] = []
        for w in getattr(seg, "words", None) or []:
            token = str(getattr(w, "word", "") or "").strip()
            start = getattr(w, "start", None)
            end = getattr(w, "end", None)
            if not token or start is None or end is None:
                continue
            words_out.append(
                {
                    "word": token,
                    "start": float(start),
                    "end": float(end),
                    "probability": float(getattr(w, "probability", 0.0) or 0.0),
                }
            )
        text = str(getattr(seg, "text", "") or "").strip()
        texts.append(text)
        out_segs.append(
            {
                "start": float(getattr(seg, "start", 0.0) or 0.0),
                "end": float(getattr(seg, "end", 0.0) or 0.0),
                "text": text,
                "words": words_out,
            }
        )
    lang = (language or "").strip().lower()
    return {
        "language": lang,
        "text": " ".join(t for t in texts if t).strip(),
        "segments": out_segs,
    }


def configure_asr(requested: str = "auto", model: str | None = None) -> tuple[str, str]:
    """Set process-wide ASR backend. Returns (backend_name, resolved_model)."""
    global _session_name, _session_backend
    name = resolve_asr_name(requested)
    resolved_model = resolve_model_name(name, model)
    _session_name = name
    _session_backend = get_asr_backend(name)
    return name, resolved_model


def get_configured_asr() -> AsrBackend:
    global _session_name, _session_backend
    if _session_backend is None:
        name = resolve_asr_name("auto")
        _session_name = name
        _session_backend = get_asr_backend(name)
    return _session_backend


def configured_asr_name() -> str:
    if _session_name is None:
        return resolve_asr_name("auto")
    return _session_name


def get_asr_backend(name: str) -> AsrBackend:
    choice = resolve_asr_name(name) if name == "auto" else name.strip().lower()
    if choice == "mlx":
        return MlxWhisperBackend()
    if choice == "faster":
        return FasterWhisperBackend()
    raise ValueError(f"Unknown ASR backend: {name}")


def _module_importable(mod: str) -> bool:
    try:
        __import__(mod)
        return True
    except Exception:
        return False


class MlxWhisperBackend:
    name = "mlx"

    def detect_language(
        self,
        audio: np.ndarray,
        sr: int,
        model: str,
        probe_sec: float = 45.0,
    ) -> str:
        import mlx_whisper

        n = min(len(audio), int(probe_sec * sr))
        probe = audio[:n].astype(np.float32)
        result = mlx_whisper.transcribe(
            probe,
            path_or_hf_repo=model,
            word_timestamps=False,
            verbose=False,
        )
        return (result.get("language") or "").strip().lower()

    def transcribe(
        self,
        audio: np.ndarray,
        model: str,
        language: str = "en",
        *,
        condition_on_previous_text: bool = True,
        compression_ratio_threshold: float | None = 2.4,
    ) -> dict:
        import mlx_whisper

        kwargs: dict[str, Any] = {
            "path_or_hf_repo": model,
            "language": language,
            "word_timestamps": True,
            "verbose": False,
            "condition_on_previous_text": condition_on_previous_text,
        }
        if compression_ratio_threshold is not None:
            kwargs["compression_ratio_threshold"] = compression_ratio_threshold
        result = mlx_whisper.transcribe(audio.astype(np.float32), **kwargs)
        if not isinstance(result, dict):
            raise TypeError("mlx_whisper.transcribe returned non-dict")
        return result


class FasterWhisperBackend:
    name = "faster"

    def _load(self, model: str) -> Any:
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise RuntimeError(
                "faster-whisper 未安裝。Windows 請執行："
                "python -m pip install -r requirements-windows.txt"
            ) from exc

        device = (os.environ.get("YTJ_FASTER_WHISPER_DEVICE") or "").strip().lower()
        compute = (os.environ.get("YTJ_FASTER_WHISPER_COMPUTE") or "").strip()
        if not device:
            try:
                import torch

                device = "cuda" if torch.cuda.is_available() else "cpu"
            except Exception:
                device = "cpu"
        if not compute:
            compute = "float16" if device == "cuda" else "int8"
        key = (model, device, compute)
        cached = _faster_models.get(key)
        if cached is None:
            with heartbeat(
                f"載入／下載 faster-whisper 模型「{model}」（{device}/{compute}；"
                "首次可能需數分鐘）…"
            ):
                cached = WhisperModel(model, device=device, compute_type=compute)
            _faster_models[key] = cached
            log_line(f"模型就緒：{model}")
        return cached

    def detect_language(
        self,
        audio: np.ndarray,
        sr: int,
        model: str,
        probe_sec: float = 45.0,
    ) -> str:
        n = min(len(audio), int(probe_sec * sr))
        probe = audio[:n].astype(np.float32)
        fw = self._load(model)
        detect = getattr(fw, "detect_language", None)
        if callable(detect):
            try:
                result = detect(probe)
                if isinstance(result, tuple) and result:
                    return str(result[0] or "").strip().lower()
                if isinstance(result, str):
                    return result.strip().lower()
            except Exception:
                pass
        segments, info = fw.transcribe(
            probe,
            language=None,
            word_timestamps=False,
            vad_filter=False,
        )
        list(segments)
        return (getattr(info, "language", None) or "").strip().lower()

    def transcribe(
        self,
        audio: np.ndarray,
        model: str,
        language: str = "en",
        *,
        condition_on_previous_text: bool = True,
        compression_ratio_threshold: float | None = 2.4,
    ) -> dict:
        fw = self._load(model)
        kwargs: dict[str, Any] = {
            "language": language,
            "word_timestamps": True,
            "condition_on_previous_text": condition_on_previous_text,
            "vad_filter": False,
        }
        if compression_ratio_threshold is not None:
            kwargs["compression_ratio_threshold"] = compression_ratio_threshold
        duration = float(len(audio)) / 16000.0 if len(audio) else 0.0
        segments_iter, info = fw.transcribe(audio.astype(np.float32), **kwargs)
        segments: list[Any] = []
        last_pct = -1
        for seg in segments_iter:
            segments.append(seg)
            end = float(getattr(seg, "end", 0.0) or 0.0)
            pct = asr_progress_pct(end, duration)
            if should_emit_progress(last_pct, pct, step=5):
                log_line(f"ASR {pct}%（{end:.1f}s / {duration:.1f}s）")
                last_pct = pct
        if duration > 0 and last_pct < 100:
            log_line(f"ASR 100%（{duration:.1f}s / {duration:.1f}s）")
        lang = (language or getattr(info, "language", None) or "").strip().lower()
        return faster_whisper_result_to_dict(segments, lang)
