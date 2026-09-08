"""Tests for WebVTT caption parsing and karaoke word timings."""

from __future__ import annotations

from pathlib import Path

from yt_decoder.captions import extract_karaoke_words, parse_vtt


def test_extract_karaoke_words_youtube_auto_style():
    raw = (
        "footwork.<00:00:06.080><c> When</c><00:00:06.319><c> you</c>"
        "<00:00:06.560><c> look</c><00:00:06.879><c> at</c>"
        "<00:00:07.520><c> big</c><00:00:07.759><c> events,</c>"
    )
    words = extract_karaoke_words(raw, cue_start=5.08, cue_end=8.629)
    assert [w["word"] for w in words] == [
        "footwork.",
        "When",
        "you",
        "look",
        "at",
        "big",
        "events,",
    ]
    assert words[0]["start"] == 5.08
    assert words[1]["start"] == 6.08
    assert words[1]["end"] == 6.319
    assert words[-1]["end"] == 8.629


def test_extract_karaoke_words_uses_karaoke_line_only():
    raw = (
        "footwork. When you look at big events,\n"
        "boxing,<00:00:09.200><c> kickboxing,</c><00:00:09.920><c> UFC,</c>"
    )
    words = extract_karaoke_words(raw, cue_start=8.639, cue_end=11.11)
    assert [w["word"] for w in words] == ["boxing,", "kickboxing,", "UFC,"]
    assert words[0]["start"] == 8.639
    assert words[1]["start"] == 9.2


def test_extract_karaoke_words_plain_returns_empty():
    assert extract_karaoke_words("Hello world.", 1.0, 2.0) == []


def test_parse_vtt_plain_manual_captions(tmp_path: Path):
    path = tmp_path / "manual.vtt"
    path.write_text(
        "WEBVTT\n\n"
        "00:00:04.251 --> 00:00:06.920\n"
        "Let's get the obvious\n"
        "out of the way first, shall we?\n\n"
        "00:00:06.962 --> 00:00:08.880\n"
        "Yes, I'm British.\n",
        encoding="utf-8",
    )
    turns = parse_vtt(path)
    assert len(turns) == 2
    assert turns[0].words == []
    assert "obvious" in turns[0].text
    assert turns[1].text.startswith("Yes")


def test_parse_vtt_karaoke_fills_words_and_skips_plain_echo(tmp_path: Path):
    path = tmp_path / "auto.vtt"
    path.write_text(
        "WEBVTT\nKind: captions\nLanguage: en\n\n"
        "00:00:05.080 --> 00:00:08.629 align:start position:0%\n"
        " \n"
        "footwork.<00:00:06.080><c> When</c><00:00:06.319><c> you</c>"
        "<00:00:06.560><c> look</c><00:00:06.879><c> at</c>"
        "<00:00:07.520><c> big</c><00:00:07.759><c> events,</c>\n\n"
        "00:00:08.629 --> 00:00:08.639 align:start position:0%\n"
        "footwork. When you look at big events,\n"
        " \n\n"
        "00:00:08.639 --> 00:00:11.110 align:start position:0%\n"
        "footwork. When you look at big events,\n"
        "boxing,<00:00:09.200><c> kickboxing,</c><00:00:09.920><c> UFC,</c>"
        "<00:00:10.400><c> any</c><00:00:10.559><c> any</c>"
        "<00:00:10.880><c> mixed</c>\n",
        encoding="utf-8",
    )
    turns = parse_vtt(path)
    assert len(turns) == 2
    assert turns[0].start == 5.08
    assert [w["word"] for w in turns[0].words][:3] == ["footwork.", "When", "you"]
    assert turns[1].words[0]["word"] == "boxing,"
    assert turns[1].words[0]["start"] == 8.639
    # Display text follows karaoke tokens, not the rolling plain prefix.
    assert turns[1].text.lower().startswith("boxing")
    assert "footwork" not in turns[1].text.lower()
