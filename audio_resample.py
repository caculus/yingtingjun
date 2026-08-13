#!/usr/bin/env python3
"""Resample mono float audio; torchaudio if available, else torch interpolate."""

from __future__ import annotations

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

    try:
        import torchaudio  # noqa: F401

        tensor = torch.from_numpy(audio).unsqueeze(0)
        tensor = torchaudio.functional.resample(tensor, orig_sr, target_sr)
        return tensor.squeeze(0).numpy().astype(np.float32, copy=False)
    except Exception:
        # Missing or ABI-broken torchaudio (common on Windows) — linear resample.
        x = torch.from_numpy(audio).view(1, 1, -1)
        new_len = max(1, int(round(audio.shape[0] * float(target_sr) / float(orig_sr))))
        y = torch.nn.functional.interpolate(
            x, size=new_len, mode="linear", align_corners=False
        )
        return y.view(-1).numpy().astype(np.float32, copy=False)
