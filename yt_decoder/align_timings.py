"""Forced-style timing alignment: keep caption text, attach ASR word times.

YouTube karaoke timestamps are often rough. After caption import we:
1. Run Whisper with word timestamps on short audio windows
2. Map those times onto the existing caption tokens (text unchanged)
3. Interpolate gaps so every caption word gets start/end for 光棒
"""

from __future__ import annotations

import re
from collections.abc import Callable
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from yt_decoder.io_util import log_stage

_PUNCT_STRIP_RE = re.compile(r"[^a-z0-9']+")
ProgressCb = Callable[[int, int], None]


def tokenize_caption_text(text: str) -> list[str]:
    return [p for p in str(text or "").split() if p]


def normalize_align_key(token: str) -> str:
    return _PUNCT_STRIP_RE.sub("", str(token or "").lower())


def _interpolate_gaps(
    assigned: list[tuple[float, float] | None],
    *,
    fallback_start: float,
    fallback_end: float,
) -> list[tuple[float, float]]:
    n = len(assigned)
    if n == 0:
        return []
    out: list[tuple[float, float] | None] = list(assigned)

    def _equal_slice(i0: int, i1: int, t0: float, t1: float) -> None:
        count = i1 - i0
        if count <= 0:
            return
        width = max(0.05, t1 - t0)
        for k, i in enumerate(range(i0, i1)):
            s = t0 + width * k / count
            e = t0 + width * (k + 1) / count
            out[i] = (s, e)

    matched = [i for i, v in enumerate(out) if v is not None]
    if not matched:
        _equal_slice(0, n, fallback_start, fallback_end)
    else:
        if matched[0] > 0:
            t1 = out[matched[0]][0]  # type: ignore[index]
            _equal_slice(0, matched[0], fallback_start, float(t1))
        if matched[-1] < n - 1:
            t0 = out[matched[-1]][1]  # type: ignore[index]
            _equal_slice(matched[-1] + 1, n, float(t0), fallback_end)

        i = 0
        while i < n:
            if out[i] is not None:
                i += 1
                continue
            j = i
            while j < n and out[j] is None:
                j += 1
            left = out[i - 1] if i > 0 else None
            right = out[j] if j < n else None
            t0 = float(left[1]) if left is not None else fallback_start
            t1 = float(right[0]) if right is not None else fallback_end
            _equal_slice(i, j, t0, t1)
            i = j

    result: list[tuple[float, float]] = []
    for pair in out:
        assert pair is not None
        result.append((float(pair[0]), float(pair[1])))
    return result


def map_asr_times_to_caption_tokens(
    caption_tokens: list[str],
    asr_words: list[dict[str, Any]],
    *,
    fallback_start: float,
    fallback_end: float,
) -> list[dict[str, Any]]:
    """Align ASR timed words onto caption token strings; keep caption spelling."""
    if not caption_tokens:
        return []

    cap_keys = [normalize_align_key(t) for t in caption_tokens]
    asr_keys = [normalize_align_key(str(w.get("word") or "")) for w in asr_words]

    # Drop empty normalized ASR keys but keep index mapping.
    asr_index: list[int] = []
    asr_keys_nz: list[str] = []
    for j, key in enumerate(asr_keys):
        if key:
            asr_index.append(j)
            asr_keys_nz.append(key)

    assigned: list[tuple[float, float] | None] = [None] * len(caption_tokens)
    if asr_keys_nz:
        matcher = SequenceMatcher(a=cap_keys, b=asr_keys_nz, autojunk=False)
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                for i, jj in zip(range(i1, i2), range(j1, j2)):
                    src = asr_words[asr_index[jj]]
                    assigned[i] = (float(src["start"]), float(src["end"]))
            elif tag == "replace" and j1 < j2 and i1 < i2:
                t0 = float(asr_words[asr_index[j1]]["start"])
                t1 = float(asr_words[asr_index[j2 - 1]]["end"])
                count = i2 - i1
                width = max(0.05, t1 - t0)
                for k, i in enumerate(range(i1, i2)):
                    s = t0 + width * k / count
                    e = t0 + width * (k + 1) / count
                    assigned[i] = (s, e)

    timed = _interpolate_gaps(
        assigned,
        fallback_start=fallback_start,
        fallback_end=fallback_end,
    )
    words: list[dict[str, Any]] = []
    for token, (start, end) in zip(caption_tokens, timed):
        if end < start:
            end = start
        words.append(
            {
                "word": token,
                "start": start,
                "end": end,
                "probability": 1.0,
            }
        )
    # Close small gaps between neighbors for smoother 光棒.
    for i in range(len(words) - 1):
        gap = words[i + 1]["start"] - words[i]["end"]
        if 0 < gap < 0.45:
            words[i]["end"] = words[i + 1]["start"]
    return words


def _group_turn_windows(
    turns: list[dict[str, Any]],
    *,
    max_window_sec: float = 30.0,
) -> list[list[int]]:
    """Group turn indices into ~max_window_sec windows by cue timeline."""
    if not turns:
        return []
    windows: list[list[int]] = []
    current: list[int] = []
    win_start = float(turns[0].get("start") or 0.0)
    for idx, turn in enumerate(turns):
        t0 = float(turn.get("start") or 0.0)
        t1 = float(turn.get("end") or t0)
        if not current:
            current = [idx]
            win_start = t0
            continue
        if (t1 - win_start) > max_window_sec and len(current) >= 1:
            windows.append(current)
            current = [idx]
            win_start = t0
        else:
            current.append(idx)
    if current:
        windows.append(current)
    return windows


def align_caption_turns(
    turns: list[dict[str, Any]],
    audio_path: Path,
    *,
    workdir: Path,
    model: str | None = None,
    max_window_sec: float = 30.0,
    pad_sec: float = 0.35,
    on_progress: ProgressCb | None = None,
) -> dict[str, Any]:
    """In-place: set turns[*].words from Whisper times while keeping turn.text.

    Returns stats dict for logging / source metadata.
    """
    from asr_backend import configure_asr, default_model_for, get_configured_asr
    from transcribe import collect_words, ensure_work_wav, load_audio_mono, media_stem

    if not turns:
        return {"aligned_turns": 0, "windows": 0, "backend": "", "model": ""}

    backend, resolved_model = configure_asr("auto", model)
    if not resolved_model:
        resolved_model = default_model_for(backend)

    stem = media_stem(Path(audio_path))
    work_wav = workdir / f"{stem}.work.wav"
    if not work_wav.exists():
        log_stage("align", "轉成 work.wav 供對齊…")
        work_wav = ensure_work_wav(Path(audio_path), Path(workdir))

    log_stage("align", f"載入音檔（{backend} / {resolved_model}）…")
    audio, sr = load_audio_mono(work_wav, target_sr=16000)
    duration = float(len(audio) / sr) if sr else 0.0
    asr = get_configured_asr()

    windows = _group_turn_windows(turns, max_window_sec=max_window_sec)
    total_windows = len(windows)
    if on_progress:
        on_progress(0, total_windows)
    else:
        log_stage("align", f"0/{total_windows}（Whisper 對齊字幕時間）")

    aligned_turns = 0
    for w_i, indices in enumerate(windows, start=1):
        first = turns[indices[0]]
        last = turns[indices[-1]]
        clip_start = max(0.0, float(first.get("start") or 0.0) - pad_sec)
        clip_end = min(duration, float(last.get("end") or 0.0) + pad_sec)
        if clip_end <= clip_start:
            clip_end = min(duration, clip_start + 0.5)
        i0 = int(clip_start * sr)
        i1 = max(i0 + 1, int(clip_end * sr))
        clip = audio[i0:i1]

        result = asr.transcribe(
            clip,
            resolved_model,
            language="en",
            condition_on_previous_text=False,
            compression_ratio_threshold=2.4,
        )
        asr_words = collect_words(result.get("segments") or [])
        for w in asr_words:
            w["start"] = float(w["start"]) + clip_start
            w["end"] = float(w["end"]) + clip_start

        # Align each turn separately against ASR words overlapping its span
        # (plus a little slack) so cue text stays authoritative.
        for idx in indices:
            turn = turns[idx]
            text = (turn.get("text") or "").strip()
            tokens = tokenize_caption_text(text)
            if not tokens:
                turn["words"] = []
                continue
            t0 = float(turn.get("start") or clip_start)
            t1 = float(turn.get("end") or t0)
            local_asr = [
                w
                for w in asr_words
                if float(w["end"]) >= (t0 - 0.2) and float(w["start"]) <= (t1 + 0.2)
            ]
            if not local_asr:
                local_asr = asr_words
            turn["words"] = map_asr_times_to_caption_tokens(
                tokens,
                local_asr,
                fallback_start=t0,
                fallback_end=max(t1, t0 + 0.05),
            )
            # Keep turn bounds covering words.
            if turn["words"]:
                turn["start"] = float(turn["words"][0]["start"])
                turn["end"] = float(turn["words"][-1]["end"])
            aligned_turns += 1

        if on_progress:
            on_progress(w_i, total_windows)
        else:
            pct = int(round(100.0 * w_i / total_windows)) if total_windows else 100
            log_stage("align", f"{w_i}/{total_windows}（{pct}%）")

    return {
        "aligned_turns": aligned_turns,
        "windows": total_windows,
        "backend": backend,
        "model": resolved_model,
        "method": "whisper_window_align",
    }


def report_align_progress(done: int, total: int) -> None:
    if total <= 0:
        log_stage("align", "0/0")
        return
    if done <= 0:
        log_stage("align", f"0/{total}（Whisper 對齊字幕時間）")
        return
    pct = int(round(100.0 * done / total))
    log_stage("align", f"{done}/{total}（{pct}%）")
