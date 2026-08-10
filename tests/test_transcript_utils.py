"""Pure helpers in transcribe.py (no ASR / NLLB)."""

from transcribe import (
    ensure_sentence_punctuation,
    format_ts,
    inherit_speaker_for_word,
    media_stem,
    scrub_zh_hallucinations,
    splice_turns_for_range,
    split_turns_by_max_sentences,
    try_glossary_translate,
    zh_still_hallucinated,
)


def test_media_stem_strips_work_wav():
    from pathlib import Path

    assert media_stem(Path("meeting.work.wav")) == "meeting"
    assert media_stem(Path("interview.m4a")) == "interview"


def test_format_ts_under_one_hour():
    assert format_ts(0) == "00:00.000"
    assert format_ts(717.25).startswith("11:57")


def test_glossary_backchannels():
    assert try_glossary_translate("Yeah.") == "嗯。"
    assert try_glossary_translate("Mm-hmm") == "嗯嗯。"
    assert try_glossary_translate("Thank you.") == "謝謝。"
    assert try_glossary_translate("That sounds expensive.") is None


def test_scrub_zh_hallucinations():
    dirty = "嗯。沒有任何樓盤符合您的搜尋結果。"
    cleaned = scrub_zh_hallucinations(dirty)
    assert "樓盤" not in cleaned
    assert zh_still_hallucinated("沒有任何樓盤符合您的搜尋結果")
    assert not zh_still_hallucinated(cleaned)


def test_ensure_sentence_punctuation():
    assert ensure_sentence_punctuation("hello") == "hello."
    assert ensure_sentence_punctuation("Hello!") == "Hello!"


def test_split_turns_by_max_sentences_keeps_speaker_and_words():
    words = [
        {"word": "One.", "start": 0.0, "end": 0.4},
        {"word": "Two.", "start": 0.5, "end": 0.9},
        {"word": "Three.", "start": 1.0, "end": 1.4},
        {"word": "Four.", "start": 1.5, "end": 2.0},
    ]
    turns = [
        {
            "speaker": "SPEAKER_02",
            "start": 0.0,
            "end": 2.0,
            "text": "One. Two. Three. Four.",
            "text_zh": "一。二。三。四。",
            "words": words,
        }
    ]
    out = split_turns_by_max_sentences(turns, max_sentences=3)
    assert len(out) == 2
    assert all(t["speaker"] == "SPEAKER_02" for t in out)
    assert out[0]["text"].startswith("One")
    assert "Four" in out[1]["text"]
    assert out[0]["end"] <= out[1]["start"] + 1e-9


def test_splice_turns_for_range_replaces_overlap():
    old = [
        {"speaker": "SPEAKER_01", "start": 0.0, "end": 2.0, "text": "A"},
        {"speaker": "SPEAKER_01", "start": 2.0, "end": 5.0, "text": "B"},
        {"speaker": "SPEAKER_02", "start": 5.0, "end": 8.0, "text": "C"},
    ]
    new = [{"speaker": "SPEAKER_01", "start": 2.1, "end": 4.8, "text": "B2"}]
    merged = splice_turns_for_range(old, new, start=2.0, end=5.0)
    texts = [t["text"] for t in merged]
    assert texts == ["A", "B2", "C"]


def test_inherit_speaker_by_overlap():
    old = [
        {"speaker": "SPEAKER_01", "start": 0.0, "end": 3.0},
        {"speaker": "SPEAKER_02", "start": 3.0, "end": 6.0},
    ]
    assert inherit_speaker_for_word(3.2, 4.0, old) == "SPEAKER_02"
    assert inherit_speaker_for_word(0.1, 0.5, old) == "SPEAKER_01"
