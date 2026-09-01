"""Import orchestration: probe → caption / whisper → export."""

from __future__ import annotations

import sys

from yt_decoder.captions import download_caption, parse_vtt, vtt_turns_to_dicts
from yt_decoder.errors import ProbeError
from yt_decoder.export import build_source_metadata, build_transcript_payload, write_outputs
from yt_decoder.fetch import download_audio
from yt_decoder.io_util import log_stage, publish_audio_copy
from yt_decoder.probe import pick_caption_track, probe_url
from yt_decoder.quality import emit_caption_warnings
from yt_decoder.translate import translate_turns
from yt_decoder.types import ImportOptions, ImportResult
from yt_decoder.util import resolve_import_stem
from yt_decoder.whisper_path import run_whisper_import
from yt_decoder.ytdlp import dump_json


def run_import(url: str, options: ImportOptions) -> ImportResult:
    log_stage("probe", url)
    probe = probe_url(url, max_duration_sec=options.max_duration_sec)
    raw_info = dump_json(url)

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


def _run_caption_import(url, probe, raw_info, options, track):
    stem = resolve_import_stem(probe, options)
    scratch_root = options.workdir.parent / ".work"
    scratch_dir = scratch_root / stem
    scratch_dir.mkdir(parents=True, exist_ok=True)

    caption_dest = scratch_dir / f"{stem}.vtt"
    log_stage("caption", f"{track.kind} / {track.lang_code}")
    download_caption(url, track, caption_dest)
    turns = parse_vtt(caption_dest)
    if not turns:
        raise ProbeError("字幕解析後沒有內容", code="no_caption")
    emit_caption_warnings(track, turns)
    turn_dicts = vtt_turns_to_dicts(turns)

    log_stage("audio", stem)
    audio_path = download_audio(url, options.workdir / stem)
    publish_audio_copy(audio_path, options.uploads_dir)

    if not options.skip_translate:
        log_stage("translate", f"{len(turn_dicts)} turns")
        translate_turns(turn_dicts, yingtingjun_root=options.yingtingjun_root)
    else:
        log_stage("translate", "skipped")

    source = build_source_metadata(
        source_type="youtube_caption",
        url=url,
        video_id=probe.video_id,
        title=probe.title,
        duration_sec=probe.duration_sec,
        caption_kind=track.kind,
        caption_format="vtt",
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
        caption_kind=track.kind,
        turns_count=len(turn_dicts),
    )
