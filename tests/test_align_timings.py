"""Tests for caption-text-preserving Whisper timing alignment."""

from __future__ import annotations

from yt_decoder.align_timings import (
    _group_turn_windows,
    map_asr_times_to_caption_tokens,
    normalize_align_key,
    tokenize_caption_text,
)


def test_normalize_and_tokenize():
    assert tokenize_caption_text("Hello, world!") == ["Hello,", "world!"]
    assert normalize_align_key("Hello,") == "hello"
    assert normalize_align_key("don't") == "dont" or normalize_align_key("don't") == "don't"


def test_map_asr_times_keeps_caption_spelling():
    caption = ["footwork.", "When", "you", "look"]
    asr = [
        {"word": "Footwork", "start": 5.0, "end": 5.4},
        {"word": "when", "start": 5.5, "end": 5.7},
        {"word": "you", "start": 5.7, "end": 5.9},
        {"word": "look", "start": 6.0, "end": 6.3},
    ]
    words = map_asr_times_to_caption_tokens(
        caption, asr, fallback_start=5.0, fallback_end=6.5
    )
    assert [w["word"] for w in words] == caption
    assert words[0]["start"] == 5.0
    assert words[1]["start"] == 5.5
    assert words[-1]["end"] == 6.3


def test_map_asr_times_interpolates_unmatched_middle():
    caption = ["alpha", "beta", "gamma"]
    asr = [
        {"word": "alpha", "start": 1.0, "end": 1.2},
        {"word": "gamma", "start": 2.0, "end": 2.3},
    ]
    words = map_asr_times_to_caption_tokens(
        caption, asr, fallback_start=1.0, fallback_end=2.3
    )
    assert words[0]["word"] == "alpha"
    assert words[2]["word"] == "gamma"
    assert words[1]["start"] >= words[0]["end"] - 1e-6
    assert words[1]["end"] <= words[2]["start"] + 1e-6


def test_map_asr_times_equal_stretch_when_no_asr():
    caption = ["one", "two"]
    words = map_asr_times_to_caption_tokens(
        caption, [], fallback_start=10.0, fallback_end=12.0
    )
    assert words[0]["start"] == 10.0
    assert words[1]["end"] == 12.0
    assert words[0]["end"] == words[1]["start"]


def test_group_turn_windows_respects_max_duration():
    turns = [
        {"start": 0.0, "end": 10.0, "text": "a"},
        {"start": 10.0, "end": 20.0, "text": "b"},
        {"start": 20.0, "end": 35.0, "text": "c"},
        {"start": 35.0, "end": 40.0, "text": "d"},
    ]
    windows = _group_turn_windows(turns, max_window_sec=30.0)
    assert windows[0] == [0, 1]
    assert 2 in windows[1]
