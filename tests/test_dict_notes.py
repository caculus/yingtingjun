"""Dictionary query + note lemma helpers."""

from pathlib import Path

from serve_player import (
    compact_lemma_entry,
    find_audio,
    lemma_lookup_variants,
    merge_lemma_into_note,
    normalize_dict_query,
    note_lemmas_list,
    remove_lemma_from_note,
    resolve_venv_python,
)


def test_normalize_dict_query_single_word_only():
    assert normalize_dict_query("  Reluctant! ") == "reluctant"
    assert normalize_dict_query("don't") == "don't"
    assert normalize_dict_query("well-known") == "well-known"
    assert normalize_dict_query("look up") is None
    assert normalize_dict_query("") is None
    assert normalize_dict_query("123") is None


def test_lemma_lookup_variants_ing_and_plural():
    ing = lemma_lookup_variants("running")
    assert ing[0] == "running"
    assert "run" in ing or "running" in ing
    assert "pastries" in lemma_lookup_variants("pastries")
    assert "pastry" in lemma_lookup_variants("pastries")


def test_merge_and_remove_lemmas_keeps_compat_fields():
    note = {"word": "", "lemmas": []}
    merge_lemma_into_note(
        note,
        {
            "lemma": "reluctant",
            "phonetic": "/x/",
            "senses": [{"pos": "adj", "zh": "不情願的"}],
            "source": "ecdict",
        },
        "reluctant",
    )
    merge_lemma_into_note(
        note,
        {
            "lemma": "expensive",
            "phonetic": "/y/",
            "senses": [{"pos": "adj", "zh": "昂貴的"}],
            "source": "ecdict",
        },
        "expensive",
    )
    lemmas = note_lemmas_list(note)
    assert [x["lemma"] for x in lemmas] == ["reluctant", "expensive"]
    assert note["word"] == "expensive"

    assert remove_lemma_from_note(note, "expensive") is True
    assert note["word"] == "reluctant"
    assert remove_lemma_from_note(note, "missing") is False


def test_compact_lemma_entry_fallback_word():
    entry = compact_lemma_entry(None, "hello")
    assert entry == {"lemma": "hello", "phonetic": "", "senses": [], "source": ""}
    assert compact_lemma_entry({}, "") is None


def test_find_audio_prefers_workdir_not_recording_wav(tmp_path: Path):
    workdir = tmp_path / "workdir"
    workdir.mkdir()
    leftover = tmp_path / "recording.wav"
    leftover.write_bytes(b"RIFF")
    lesson = workdir / "meeting.work.wav"
    lesson.write_bytes(b"RIFF")
    found = find_audio(tmp_path, workdir)
    assert found == lesson


def test_find_audio_ignores_root_recording_when_workdir_empty(tmp_path: Path):
    workdir = tmp_path / "workdir"
    workdir.mkdir()
    leftover = tmp_path / "recording.wav"
    leftover.write_bytes(b"RIFF")
    assert find_audio(tmp_path, workdir) is None


def test_resolve_venv_python_returns_existing_path():
    py = resolve_venv_python()
    assert py.exists()
