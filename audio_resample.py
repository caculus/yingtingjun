#!/usr/bin/env python3
"""Resample mono float audio; torchaudio if available, else torch interpolate."""

from __future__ import annotations

import sys

import numpy as np
import torch


def resample_mono(audio: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
    """Return float32 mono waveform at target_sr."""
    audio = np.asarray(audio, dtype=np.float32)
    if audio.ndim > 1:
        audio = audio.mean(axis=1).astype(np.float32)
    orig_sr = int(orig_sr)
    target_sr = int(target_sr)
    if orig_sr <= 0 or target_sr <= 0:
        raise ValueError(f"Invalid sample rates: {orig_sr} → {target_sr}")
    if orig_sr == target_sr or audio.size == 0:
        return audio

    # Prefer torch interpolate on Windows: real torchaudio often ABI-breaks and
    # pops a modal DLL dialog before Python can catch ImportError.
    use_torchaudio = True
    if sys.platform.startswith("win"):
        from torchaudio_compat import prepare_torchaudio_for_speechbrain, wants_real_torchaudio

        if not wants_real_torchaudio():
            use_torchaudio = False
        else:
            use_torchaudio = prepare_torchaudio_for_speechbrain() == "real"

    if use_torchaudio:
        try:
            import torchaudio

            tensor = torch.from_numpy(audio).unsqueeze(0)
            tensor = torchaudio.functional.resample(tensor, orig_sr, target_sr)
            return tensor.squeeze(0).numpy().astype(np.float32, copy=False)
        except Exception:
            pass

    # Missing or ABI-broken torchaudio (common on Windows) — linear resample.
    x = torch.from_numpy(audio).view(1, 1, -1)
    new_len = max(1, int(round(audio.shape[0] * float(target_sr) / float(orig_sr))))
    y = torch.nn.functional.interpolate(
        x, size=new_len, mode="linear", align_corners=False
    )
    return y.view(-1).numpy().astype(np.float32, copy=False)
