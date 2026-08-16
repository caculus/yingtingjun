#!/usr/bin/env python3
"""Avoid broken Windows torchaudio DLLs when importing speechbrain.

speechbrain always ``import torchaudio`` at load time. On some Windows setups
(especially WoA + mismatched wheels) that pops a modal DLL dialog / WinError 127.
Our ECAPA path only needs ``encode_batch`` on tensors, so a lightweight stub is enough.
"""

from __future__ import annotations

import os
import sys
import types
from typing import Any


def wants_real_torchaudio() -> bool:
    return (os.environ.get("YTJ_USE_TORCHAUDIO") or "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def _env_wants_real_torchaudio() -> bool:
    return wants_real_torchaudio()


def _is_stub(mod: Any) -> bool:
    return bool(getattr(mod, "_ytj_torchaudio_stub", False))


def install_torchaudio_stub() -> types.ModuleType:
    """Register a minimal torchaudio in ``sys.modules`` (does not load ``_torchaudio.pyd``)."""
    for name in list(sys.modules):
        if name == "torchaudio" or name.startswith("torchaudio."):
            # Keep an already-installed stub.
            existing = sys.modules.get(name)
            if name == "torchaudio" and existing is not None and _is_stub(existing):
                return existing  # type: ignore[return-value]
            del sys.modules[name]

    ta = types.ModuleType("torchaudio")
    ta.__version__ = "2.9.0"
    ta._ytj_torchaudio_stub = True  # type: ignore[attr-defined]

    functional = types.ModuleType("torchaudio.functional")

    def resample(*_args: Any, **_kwargs: Any) -> Any:
        raise RuntimeError(
            "torchaudio stub: resampling unavailable; use audio_resample.resample_mono"
        )

    functional.resample = resample  # type: ignore[attr-defined]
    ta.functional = functional  # type: ignore[attr-defined]

    transforms = types.ModuleType("torchaudio.transforms")
    ta.transforms = transforms  # type: ignore[attr-defined]

    compliance = types.ModuleType("torchaudio.compliance")
    ta.compliance = compliance  # type: ignore[attr-defined]

    sys.modules["torchaudio"] = ta
    sys.modules["torchaudio.functional"] = functional
    sys.modules["torchaudio.transforms"] = transforms
    sys.modules["torchaudio.compliance"] = compliance
    return ta


def prepare_torchaudio_for_speechbrain() -> str:
    """Ensure ``import torchaudio`` is safe before importing speechbrain.

    Returns
    -------
    str
        ``\"real\"`` if using installed torchaudio, ``\"stub\"`` if stubbed.
    """
    existing = sys.modules.get("torchaudio")
    if existing is not None and _is_stub(existing):
        return "stub"
    if existing is not None and not _is_stub(existing):
        return "real"

    # Prefer stub on Windows unless explicitly overridden — avoids DLL modal dialogs.
    if sys.platform.startswith("win") and not _env_wants_real_torchaudio():
        install_torchaudio_stub()
        return "stub"

    try:
        import torchaudio  # noqa: F401

        return "real"
    except Exception:
        install_torchaudio_stub()
        return "stub"
