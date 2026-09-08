"""Tests for YouTube Chinese caption selection and time-overlap mapping."""

from __future__ import annotations

from yt_decoder.captions import Turn
from yt_decoder.probe import (
    CaptionTrack,
    _extract_zh_caption_tracks,
    pick_zh_caption_track,
    zh_lang_rank,
)
from yt_decoder.zh_captions import map_zh_turns_to_en_turns


def test_zh_lang_rank_prefers_traditional_taiwan():
    assert zh_lang_rank("zh-TW") < zh_lang_rank("zh-CN")
    assert zh_lang_rank("zh-Hant") < zh_lang_rank("zh-Hans")
    assert zh_lang_rank("zh-TW") < zh_lang_rank("zh-Hant")
    assert zh_lang_rank("zh-Hans") < zh_lang_rank("zh")


def test_pick_zh_manual_before_auto_even_if_auto_is_tw():
    tracks = [
        CaptionTrack(lang="zh", kind="auto", name="zh-TW", lang_code="zh-TW"),
        CaptionTrack(lang="zh", kind="manual", name="zh-CN", lang_code="zh-CN"),
    ]
    picked = pick_zh_caption_track(tracks)
    assert picked is not None
    assert picked.kind == "manual"
    assert picked.lang_code == "zh-CN"


def test_pick_zh_prefers_tw_over_cn_when_same_kind():
    tracks = [
        CaptionTrack(lang="zh", kind="manual", name="Simplified", lang_code="zh-Hans"),
        CaptionTrack(lang="zh", kind="manual", name="Taiwan", lang_code="zh-TW"),
        CaptionTrack(lang="zh", kind="manual", name="China", lang_code="zh-CN"),
    ]
    picked = pick_zh_caption_track(tracks)
    assert picked is not None
    assert picked.lang_code == "zh-TW"


def test_pick_zh_auto_traditional_before_auto_simplified():
    tracks = [
        CaptionTrack(lang="zh", kind="auto", name="zh", lang_code="zh"),
        CaptionTrack(lang="zh", kind="auto", name="zh-Hant", lang_code="zh-Hant"),
    ]
    picked = pick_zh_caption_track(tracks)
    assert picked is not None
    assert picked.lang_code == "zh-Hant"


def test_extract_zh_caption_tracks_from_info():
    info = {
        "subtitles": {
            "en": [{"ext": "vtt"}],
            "zh-TW": [{"ext": "vtt", "name": "Chinese (Taiwan)"}],
        },
        "automatic_captions": {
            "zh-Hans": [{"ext": "vtt"}],
            "ja": [{"ext": "vtt"}],
        },
    }
    tracks = _extract_zh_caption_tracks(info)
    assert [t.lang_code for t in tracks] == ["zh-TW", "zh-Hans"]
    assert tracks[0].kind == "manual"
    assert tracks[1].kind == "auto"


def test_map_zh_turns_by_overlap():
    en = [
        {"start": 0.0, "end": 2.0, "text": "Hello"},
        {"start": 2.0, "end": 4.0, "text": "World"},
    ]
    zh = [
        Turn(speaker="A", start=0.0, end=2.1, text="你好"),
        Turn(speaker="A", start=2.0, end=4.0, text="世界"),
    ]
    stats = map_zh_turns_to_en_turns(en, zh, min_coverage=0.5)
    assert stats["ok"] is True
    assert en[0]["text_zh"] == "你好"
    assert en[1]["text_zh"] == "世界"


def test_map_zh_turns_rejects_low_coverage():
    en = [
        {"start": 0.0, "end": 1.0, "text": "a"},
        {"start": 1.0, "end": 2.0, "text": "b"},
        {"start": 2.0, "end": 3.0, "text": "c"},
        {"start": 3.0, "end": 4.0, "text": "d"},
    ]
    zh = [Turn(speaker="A", start=0.0, end=1.0, text="甲")]
    stats = map_zh_turns_to_en_turns(en, zh, min_coverage=0.45)
    assert stats["ok"] is False
    assert stats["reason"] == "low_coverage"
    assert all(t["text_zh"] == "" for t in en)


def test_map_zh_joins_multiple_overlapping_cues():
    en = [{"start": 0.0, "end": 5.0, "text": "Long English turn"}]
    zh = [
        Turn(speaker="A", start=0.0, end=2.0, text="第一段"),
        Turn(speaker="A", start=2.0, end=5.0, text="第二段"),
    ]
    stats = map_zh_turns_to_en_turns(en, zh, min_coverage=0.5)
    assert stats["ok"] is True
    assert en[0]["text_zh"] == "第一段第二段"


def test_find_downloaded_vtt_matches_lang_suffix(tmp_path: Path):
    from yt_decoder.captions import _find_downloaded_vtt

    stem = "talk"
    (tmp_path / f"{stem}.en.vtt").write_text("WEBVTT\n", encoding="utf-8")
    (tmp_path / f"{stem}.zh-Hant.vtt").write_text("WEBVTT\n", encoding="utf-8")
    (tmp_path / f"{stem}.zh-Hans.vtt").write_text("WEBVTT\n", encoding="utf-8")

    assert _find_downloaded_vtt(tmp_path, stem, "zh-Hant").name.endswith("zh-Hant.vtt")
    assert _find_downloaded_vtt(tmp_path, stem, "en").name.endswith("en.vtt")
    assert _find_downloaded_vtt(tmp_path, stem, "ja") is None


def test_download_caption_tracks_fetches_zh_before_en(tmp_path, monkeypatch):
    """Chinese must be requested before English to avoid YouTube 429."""
    from yt_decoder import captions as cap
    from yt_decoder.probe import CaptionTrack

    en = CaptionTrack(lang="en", kind="auto", name="English", lang_code="en")
    zh = CaptionTrack(lang="zh", kind="auto", name="zh-Hant", lang_code="zh-Hant")
    stem = "talk"
    calls: list[list[str]] = []

    def fake_write(url, tracks, dest_dir, out_stem, info_json=None, ignore_errors=False):
        langs = [t.lang_code for t in tracks]
        calls.append(langs)
        out: dict = {}
        for lang in langs:
            path = dest_dir / f"{out_stem}.{lang}.vtt"
            path.write_text("WEBVTT\n", encoding="utf-8")
            out[lang] = path
        return out

    monkeypatch.setattr(cap, "_ytdlp_write_subs", fake_write)
    found = cap.download_caption_tracks(
        "https://youtu.be/x", [en, zh], tmp_path, stem, file_stem="vid"
    )
    assert calls[0] == ["zh-Hant"]
    assert "en" in calls[1]
    assert "en" in found and "zh-Hant" in found
    assert found["en"].name == f"{stem}.en.vtt"


def test_probe_url_cached_reuses_within_ttl(monkeypatch):
    from yt_decoder import probe as probe_mod
    from yt_decoder.probe import CaptionTrack, ProbeResult, probe_url_cached

    calls = {"n": 0}

    def fake_probe(url, *, max_duration_sec=2700):
        calls["n"] += 1
        return ProbeResult(
            ok=True,
            video_id="abc",
            title="T",
            duration_sec=10.0,
            caption_tracks=[CaptionTrack(lang="en", kind="auto", name="en")],
            url=url,
        )

    monkeypatch.setattr(probe_mod, "probe_url", fake_probe)
    probe_mod._probe_cache.clear()
    a = probe_url_cached("https://youtu.be/abc")
    b = probe_url_cached("https://youtu.be/abc")
    assert calls["n"] == 1
    assert a is b
    c = probe_url_cached("https://youtu.be/abc", force=True)
    assert calls["n"] == 2
    assert c is not a


def test_apply_zh_vtt_to_turns(tmp_path: Path):
    from yt_decoder.probe import CaptionTrack
    from yt_decoder.zh_captions import apply_zh_vtt_to_turns

    zh_path = tmp_path / "zh.vtt"
    zh_path.write_text(
        "WEBVTT\n\n"
        "00:00:00.000 --> 00:00:02.000\n你好\n\n"
        "00:00:02.000 --> 00:00:04.000\n世界\n",
        encoding="utf-8",
    )
    en = [
        {"start": 0.0, "end": 2.0, "text": "Hello"},
        {"start": 2.0, "end": 4.0, "text": "World"},
    ]
    track = CaptionTrack(lang="zh", kind="auto", name="zh-Hant", lang_code="zh-Hant")
    stats = apply_zh_vtt_to_turns(en, zh_path, track)
    assert stats["ok"] is True
    assert "你好" in en[0]["text_zh"]
    assert "世界" in en[1]["text_zh"]
