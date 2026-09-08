"""Import orchestration: probe → caption / whisper → export."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from yt_decoder.align_timings import align_caption_turns, report_align_progress
from yt_decoder.captions import (
    download_caption_tracks,
    parse_vtt,
    vtt_turns_to_dicts,
)
from yt_decoder.errors import ProbeError
from yt_decoder.export import build_source_metadata, build_transcript_payload, write_outputs
from yt_decoder.fetch import download_audio
from yt_decoder.io_util import log_stage, publish_audio_copy
from yt_decoder.probe import (
    english_caption_candidates,
    pick_caption_track,
    pick_zh_caption_track,
    probe_url,
)
from yt_decoder.quality import emit_caption_warnings
from yt_decoder.translate import translate_turns
from yt_decoder.types import ImportOptions, ImportResult
from yt_decoder.util import resolve_import_stem
from yt_decoder.whisper_path import run_whisper_import
from yt_decoder.zh_captions import try_apply_youtube_zh_captions


def run_import(
    url: str,
    options: ImportOptions,
    *,
    probe=None,
) -> ImportResult:
    if probe is None:
        log_stage("probe", url)
        probe = probe_url(url, max_duration_sec=options.max_duration_sec)
    else:
        log_stage("probe", f"{probe.video_id}（重用預檢）")
    raw_info = probe.raw_info or {}

    use_whisper = options.mode == "whisper"
    track = None
    if not use_whisper:
        track = pick_caption_track(probe.caption_tracks, options.caption_pref)
        if track is None:
            if options.mode == "caption":
                raise ProbeError("未偵測到英文字幕", code="no_caption")
            use_whisper = True
            log_stage(
                "whisper",
                "無英文字幕，fallback 至 Whisper（英聽君 transcribe.py）",
            )

    if use_whisper:
        return run_whisper_import(url, probe, raw_info, options)

    return _run_caption_import(url, probe, raw_info, options, track)


def _translation_meta_from_zh(zh_result: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": "youtube_caption",
        "kind": zh_result.get("kind"),
        "lang_code": zh_result.get("lang_code"),
        "coverage": zh_result.get("coverage"),
        "filled": zh_result.get("filled"),
        "total": zh_result.get("total"),
    }


def _fallback_nllb(
    turn_dicts: list[dict[str, Any]],
    options: ImportOptions,
    zh_result: dict[str, Any] | None,
) -> dict[str, Any]:
    translate_turns(turn_dicts, yingtingjun_root=options.yingtingjun_root)
    meta: dict[str, Any] = {"source": "nllb"}
    if zh_result is not None:
        meta["youtube_caption_attempt"] = {
            "kind": zh_result.get("kind"),
            "lang_code": zh_result.get("lang_code"),
            "reason": zh_result.get("reason"),
            "coverage": zh_result.get("coverage"),
        }
    return meta


def _run_caption_import(url, probe, raw_info, options, track):
    stem = resolve_import_stem(probe, options)
    scratch_root = options.workdir.parent / ".work"
    scratch_dir = scratch_root / stem
    scratch_dir.mkdir(parents=True, exist_ok=True)

    zh_track = None if options.skip_translate else pick_zh_caption_track(probe.zh_caption_tracks)
    en_candidates = english_caption_candidates(probe.caption_tracks, options.caption_pref)
    if not en_candidates:
        en_candidates = [track]

    # Short yt-dlp basename — long title stems intermittently produce empty writes.
    file_stem = probe.video_id or stem

    downloaded: dict = {}
    chosen_en = track
    for candidate in en_candidates:
        lang_note = candidate.lang_code
        if zh_track is not None:
            lang_note = f"{candidate.lang_code}+{zh_track.lang_code}"
        log_stage("caption", f"{candidate.kind} / {lang_note}")
        to_fetch = [candidate]
        if zh_track is not None:
            to_fetch.append(zh_track)
        downloaded = download_caption_tracks(
            url,
            to_fetch,
            scratch_dir,
            stem,
            file_stem=file_stem,
            raw_info=raw_info or probe.raw_info,
        )
        if candidate.lang_code in downloaded:
            chosen_en = candidate
            break
        log_stage("caption", f"{candidate.lang_code} 失敗，嘗試下一條英文字幕…")

    en_path = downloaded.get(chosen_en.lang_code)
    if en_path is None:
        raise ProbeError("字幕下載後找不到英文字幕檔", code="no_caption")

    caption_dest = scratch_dir / f"{stem}.vtt"
    if en_path != caption_dest:
        caption_dest.write_text(en_path.read_text(encoding="utf-8"), encoding="utf-8")

    turns = parse_vtt(caption_dest)
    if not turns:
        raise ProbeError("字幕解析後沒有內容", code="no_caption")
    emit_caption_warnings(chosen_en, turns)
    turn_dicts = vtt_turns_to_dicts(turns)

    zh_vtt = downloaded.get(zh_track.lang_code) if zh_track is not None else None
    zh_result = None
    if zh_track is not None and zh_vtt is not None:
        zh_result = try_apply_youtube_zh_captions(
            url,
            turn_dicts,
            probe.zh_caption_tracks,
            dest_vtt=scratch_dir / f"{stem}.zh.vtt",
            zh_vtt=zh_vtt,
            track=zh_track,
        )
    elif zh_track is not None:
        log_stage("zh_caption", f"同批下載未含 {zh_track.lang_code}")
        zh_result = {
            "ok": False,
            "kind": zh_track.kind,
            "lang_code": zh_track.lang_code,
            "reason": "missing_from_batch_download",
        }

    log_stage("audio", stem)
    audio_path = download_audio(url, options.workdir / stem)
    publish_audio_copy(audio_path, options.uploads_dir)

    timing_alignment = None
    if options.align_timings:
        try:
            timing_alignment = align_caption_turns(
                turn_dicts,
                audio_path,
                workdir=options.workdir,
                on_progress=report_align_progress,
            )
            log_stage(
                "align",
                f"完成 {timing_alignment.get('aligned_turns', 0)} turns／"
                f"{timing_alignment.get('windows', 0)} windows",
            )
        except Exception as exc:  # noqa: BLE001
            # Keep caption import usable if alignment fails (karaoke words still there).
            log_stage("align", f"略過（對齊失敗：{exc}）")
            timing_alignment = {"method": "skipped", "error": str(exc)}
    else:
        log_stage("align", "skipped")

    if options.skip_translate:
        log_stage("translate", "skipped")
        translation: dict[str, Any] = {"source": "skipped"}
    elif zh_result and zh_result.get("ok"):
        translation = _translation_meta_from_zh(zh_result)
    else:
        translation = _fallback_nllb(turn_dicts, options, zh_result)

    source = build_source_metadata(
        source_type="youtube_caption",
        url=url,
        video_id=probe.video_id,
        title=probe.title,
        duration_sec=probe.duration_sec,
        caption_kind=chosen_en.kind,
        caption_format="vtt",
        timing_alignment=timing_alignment,
        translation=translation,
    )
    payload = build_transcript_payload(turn_dicts, source=source)

    log_stage("write", stem)
    json_path = write_outputs(
        options.output_dir,
        stem,
        payload,
        probe_data=raw_info,
        caption_vtt=caption_dest,
    )

    log_stage("done", f"output/{stem}.json")
    print(
        f"\n完成。若英聽君已開啟請先重新整理（Cmd+R），"
        f"再在下拉選單選：{audio_path.name}",
        file=sys.stderr,
        flush=True,
    )

    return ImportResult(
        stem=stem,
        json_path=json_path,
        audio_path=audio_path,
        caption_kind=chosen_en.kind,
        turns_count=len(turn_dicts),
    )
