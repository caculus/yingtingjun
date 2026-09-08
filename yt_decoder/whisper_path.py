"""Whisper fallback via Yingtingjun transcribe.py."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from yt_decoder.captions import download_caption_tracks
from yt_decoder.errors import ProbeError
from yt_decoder.export import build_source_metadata, inject_source_metadata
from yt_decoder.fetch import download_audio
from yt_decoder.io_util import log_stage
from yt_decoder.probe import ProbeResult, pick_zh_caption_track
from yt_decoder.translate import run_yingtingjun_transcribe, translate_turns
from yt_decoder.types import ImportOptions, ImportResult
from yt_decoder.util import resolve_import_stem
from yt_decoder.zh_captions import try_apply_youtube_zh_captions


def run_whisper_import(
    url: str,
    probe: ProbeResult,
    raw_info: dict,
    options: ImportOptions,
) -> ImportResult:
    stem = resolve_import_stem(probe, options)
    options.workdir.mkdir(parents=True, exist_ok=True)
    options.uploads_dir.mkdir(parents=True, exist_ok=True)

    scratch_root = options.workdir.parent / ".work"
    scratch_dir = scratch_root / stem
    scratch_dir.mkdir(parents=True, exist_ok=True)

    zh_track = None if options.skip_translate else pick_zh_caption_track(probe.zh_caption_tracks)
    zh_vtt = None
    if zh_track is not None:
        log_stage("zh_caption", f"預先下載 {zh_track.kind} / {zh_track.lang_code}")
        downloaded = download_caption_tracks(
            url,
            [zh_track],
            scratch_dir,
            stem,
            file_stem=probe.video_id or stem,
            raw_info=raw_info or probe.raw_info,
        )
        zh_vtt = downloaded.get(zh_track.lang_code)
        if zh_vtt is None:
            log_stage("zh_caption", f"預先下載未含 {zh_track.lang_code}")

    # Source audio stays in uploads/ only. Whisper/transcribe writes
    # workdir/{stem}.work.wav — putting m4a in workdir would create a
    # duplicate dropdown item (英聽君 lists every file in workdir).
    log_stage("audio", stem)
    source_audio = download_audio(url, options.uploads_dir / stem)

    prefer_youtube_zh = zh_vtt is not None and zh_vtt.is_file()
    # Skip NLLB inside transcribe when we already have a ZH VTT to apply.
    skip_in_transcribe = options.skip_translate or prefer_youtube_zh

    log_stage("whisper", f"{stem}（英聽君 transcribe.py，可能需數分鐘）")
    run_yingtingjun_transcribe(
        source_audio,
        options.output_dir,
        options.workdir,
        yingtingjun_root=options.yingtingjun_root,
        skip_translate=skip_in_transcribe,
    )

    work_wav = options.workdir / f"{stem}.work.wav"
    if work_wav.is_file():
        audio_path = work_wav
        remove_same_stem_audio(options.workdir, stem, keep=work_wav)
    else:
        # Fallback if transcribe did not produce work.wav
        playable = options.workdir / source_audio.name
        if not playable.is_file():
            playable.write_bytes(source_audio.read_bytes())
        audio_path = playable

    json_path = options.output_dir / f"{stem}.json"
    if not json_path.is_file():
        raise ProbeError(
            f"Whisper 完成但未找到 output/{stem}.json",
            code="unavailable",
        )

    translation: dict
    if options.skip_translate:
        translation = {"source": "skipped"}
    elif prefer_youtube_zh:
        data = json.loads(json_path.read_text(encoding="utf-8"))
        turns = data.get("turns") or []
        zh_result = try_apply_youtube_zh_captions(
            url,
            turns,
            probe.zh_caption_tracks,
            dest_vtt=scratch_dir / f"{stem}.zh.vtt",
            zh_vtt=zh_vtt,
            track=zh_track,
        )
        if zh_result and zh_result.get("ok"):
            translation = {
                "source": "youtube_caption",
                "kind": zh_result.get("kind"),
                "lang_code": zh_result.get("lang_code"),
                "coverage": zh_result.get("coverage"),
                "filled": zh_result.get("filled"),
                "total": zh_result.get("total"),
            }
            data["turns"] = turns
            json_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        else:
            translate_turns(turns, yingtingjun_root=options.yingtingjun_root)
            translation = {"source": "nllb"}
            if zh_result is not None:
                translation["youtube_caption_attempt"] = {
                    "kind": zh_result.get("kind"),
                    "lang_code": zh_result.get("lang_code"),
                    "reason": zh_result.get("reason"),
                    "coverage": zh_result.get("coverage"),
                }
            data["turns"] = turns
            json_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
    else:
        # transcribe already ran NLLB (or skip was false and no ZH file).
        translation = {"source": "nllb"}
        if zh_track is not None:
            translation["youtube_caption_attempt"] = {
                "kind": zh_track.kind,
                "lang_code": zh_track.lang_code,
                "reason": "missing_from_batch_download",
            }

    source = build_source_metadata(
        source_type="youtube_whisper",
        url=url,
        video_id=probe.video_id,
        title=probe.title,
        duration_sec=probe.duration_sec,
        translation=translation,
    )
    inject_source_metadata(json_path, source)

    if raw_info:
        sidecar = options.output_dir / f"{stem}.source.json"
        sidecar.write_text(
            json.dumps(raw_info, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    data = json.loads(json_path.read_text(encoding="utf-8"))
    turns_count = len(data.get("turns") or [])
    log_stage("done", f"output/{stem}.json ({turns_count} turns, whisper)")

    print(
        f"\n完成（Whisper 路徑）。若英聽君已開啟請先重新整理（Cmd+R），"
        f"再在下拉選單選：{audio_path.name}",
        file=sys.stderr,
        flush=True,
    )

    return ImportResult(
        stem=stem,
        json_path=json_path,
        audio_path=audio_path,
        caption_kind="whisper",
        turns_count=turns_count,
    )


def remove_same_stem_audio(workdir: Path, stem: str, *, keep: Path) -> None:
    """Drop workdir audio siblings that share stem (avoid duplicate library rows)."""
    keep_resolved = keep.resolve()
    for path in list(workdir.iterdir()):
        if not path.is_file():
            continue
        if path.resolve() == keep_resolved:
            continue
        name = path.name
        if name == f"{stem}.m4a" or name == f"{stem}.mp3" or name == f"{stem}.wav":
            path.unlink(missing_ok=True)
