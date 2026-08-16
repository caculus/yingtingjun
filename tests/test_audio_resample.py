"""Resample helper tests (no torchaudio required)."""

import numpy as np

from audio_resample import resample_mono


def test_resample_mono_changes_length():
    sr0, sr1 = 8000, 16000
    x = np.zeros(8000, dtype=np.float32)
    y = resample_mono(x, sr0, sr1)
    assert y.dtype == np.float32
    assert abs(len(y) - 16000) <= 1


def test_resample_mono_same_rate_noop_length():
    x = np.linspace(-0.2, 0.2, 1000, dtype=np.float32)
    y = resample_mono(x, 16000, 16000)
    assert len(y) == len(x)
    assert np.allclose(x, y)
