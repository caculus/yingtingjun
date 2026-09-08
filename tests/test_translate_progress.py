"""Translate progress callback for YouTube import / CLI."""

from __future__ import annotations

from unittest.mock import patch

from transcribe import translate_turns


def test_translate_turns_reports_progress():
    turns = [
        {"text": "Hello.", "text_zh": ""},
        {"text": "World.", "text_zh": ""},
        {"text": "Again.", "text_zh": ""},
        {"text": "More.", "text_zh": ""},
        {"text": "Done.", "text_zh": ""},
    ]
    seen: list[tuple[int, int]] = []

    def fake_translate_en_to_zh(text: str, max_chars: int = 350) -> str:
        return f"ZH:{text}"

    with (
        patch("transcribe.get_translator", return_value=object()),
        patch("transcribe.translate_en_to_zh", side_effect=fake_translate_en_to_zh),
    ):
        translate_turns(turns, on_progress=lambda done, total: seen.append((done, total)))

    assert seen[0] == (0, 5)
    assert (1, 5) in seen
    assert (5, 5) in seen
    assert turns[0]["text_zh"].startswith("ZH:")


def test_yt_decoder_translate_forwards_progress_to_log_stage():
    from yt_decoder import translate as yt_translate

    turns = [{"text": "Hi.", "text_zh": ""}]
    logs: list[tuple[str, str]] = []

    def fake_translate_turns(turns_arg, *, on_progress=None):
        if on_progress:
            on_progress(0, 1)
            on_progress(1, 1)
        turns_arg[0]["text_zh"] = "嗨。"

    with (
        patch("transcribe.translate_turns", side_effect=fake_translate_turns),
        patch("yt_decoder.translate.log_stage", side_effect=lambda s, m: logs.append((s, m))),
    ):
        yt_translate.translate_turns(turns)

    assert any(s == "translate" and "0/1" in m for s, m in logs)
    assert any(s == "translate" and "1/1" in m for s, m in logs)
    assert turns[0]["text_zh"] == "嗨。"
