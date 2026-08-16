"""Windows torchaudio stub for speechbrain import safety."""

import sys

from torchaudio_compat import install_torchaudio_stub, prepare_torchaudio_for_speechbrain


def test_stub_has_version_and_marks_itself():
    # Clear any prior torchaudio from this process.
    for name in list(sys.modules):
        if name == "torchaudio" or name.startswith("torchaudio."):
            del sys.modules[name]
    ta = install_torchaudio_stub()
    assert ta.__version__.startswith("2.")
    assert getattr(ta, "_ytj_torchaudio_stub") is True
    import torchaudio

    assert torchaudio is ta


def test_prepare_on_windows_uses_stub(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.delenv("YTJ_USE_TORCHAUDIO", raising=False)
    for name in list(sys.modules):
        if name == "torchaudio" or name.startswith("torchaudio."):
            del sys.modules[name]
    assert prepare_torchaudio_for_speechbrain() == "stub"
    import torchaudio

    assert getattr(torchaudio, "_ytj_torchaudio_stub") is True
