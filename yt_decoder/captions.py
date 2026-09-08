"""Download and parse YouTube captions (VTT / json3) into turns."""

from __future__ import annotations

import html
import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from yt_decoder.constants import DEFAULT_SPEAKER
from yt_decoder.io_util import log_stage
from yt_decoder.probe import CaptionTrack
from yt_decoder.ytdlp import run_ytdlp

_MIN_CUE_DURATION = 0.3
_TIMESTAMP_RE = re.compile(
    r"(?P<start>\d{1,2}:\d{2}(?::\d{2})?\.\d{3})\s*-->\s*(?P<end>\d{1,2}:\d{2}(?::\d{2})?\.\d{3})"
)
_TAG_RE = re.compile(r"<[^>]+>")
# YouTube karaoke auto-captions: footwork.<00:00:06.080><c> When</c>
_KARAOKE_TS_RE = re.compile(r"<(\d{1,2}:\d{2}(?::\d{2})?\.\d{3})>")
_C_TAG_RE = re.compile(r"</?c>", re.IGNORECASE)


@dataclass
class Turn:
    speaker: str
    start: float
    end: float
    text: str
    text_zh: str = ""
    words: list[dict[str, Any]] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "speaker": self.speaker,
            "start": self.start,
            "end": self.end,
            "text": self.text,
            "text_zh": self.text_zh,
            "words": self.words if self.words is not None else [],
        }


@dataclass
class _Cue:
    start: float
    end: float
    text: str
    words: list[dict[str, Any]] = field(default_factory=list)


def ensure_sentence_punctuation(text: str) -> str:
    text = text.strip()
    if not text:
        return text
    # YouTube auto ZH often spaces every CJK glyph; collapse those.
    text = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", text)
    text = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[，。！？；：、])", "", text)
    text = re.sub(r"(?<=[，。！？；：、])\s+(?=[\u4e00-\u9fff])", "", text)
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r"([,.;:!?])([A-Za-z])", r"\1 \2", text)
    text = re.sub(r"\bMm\s*-\s*hmm\b", "Mm-hmm", text, flags=re.I)
    text = re.sub(r"\s+", " ", text).strip()
    cjk = len(re.findall(r"[\u4e00-\u9fff]", text))
    if cjk >= max(1, len(re.findall(r"[A-Za-z]", text))):
        # Chinese (or CJK-dominant) cue — keep 。！？ ; do not append English ".".
        return text
    if text[-1] not in ".?!…\"')":
        text += "."
    return text


def _parse_timestamp(value: str) -> float:
    parts = value.strip().split(":")
    if len(parts) == 2:
        minutes, seconds = parts
        hours = 0.0
    elif len(parts) == 3:
        hours, minutes, seconds = parts
    else:
        raise ValueError(f"invalid timestamp: {value}")
    sec_parts = seconds.split(".")
    whole = int(sec_parts[0])
    millis = int(sec_parts[1]) if len(sec_parts) > 1 else 0
    return int(hours) * 3600 + int(minutes) * 60 + whole + millis / 1000.0


def clean_vtt_text(text: str) -> str:
    text = _TAG_RE.sub("", text)
    text = html.unescape(text)
    text = text.replace("\u00a0", " ").replace("&nbsp;", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _clean_fragment(text: str) -> str:
    text = _C_TAG_RE.sub("", text)
    text = html.unescape(text)
    text = text.replace("\u00a0", " ").replace("&nbsp;", " ")
    text = _TAG_RE.sub("", text)
    return re.sub(r"\s+", " ", text).strip()


def _expand_untimed_prefix(text: str, start: float, end: float) -> list[tuple[float, str]]:
    """Split an untimed leading phrase across [start, end)."""
    parts = [p for p in text.split() if p]
    if not parts:
        return []
    if len(parts) == 1:
        return [(start, parts[0])]
    span = max(0.01, end - start)
    return [
        (start + span * i / len(parts), part)
        for i, part in enumerate(parts)
    ]


def extract_karaoke_words(raw_payload: str, cue_start: float, cue_end: float) -> list[dict[str, Any]]:
    """Parse YouTube karaoke VTT payload into word timings.

    Returns [] when the cue has no karaoke timestamps / <c> tags.
    For multi-line auto-captions (plain previous line + karaoke line), only
    karaoke-bearing lines are used so rolling prefixes are not duplicated.
    """
    lines = [ln.rstrip() for ln in raw_payload.replace("\r\n", "\n").split("\n")]
    karaoke_lines = [
        ln for ln in lines
        if ln.strip() and (_KARAOKE_TS_RE.search(ln) or "<c>" in ln.lower())
    ]
    if not karaoke_lines:
        return []

    timed: list[tuple[float, str]] = []
    for line in karaoke_lines:
        parts = _KARAOKE_TS_RE.split(line)
        leading = _clean_fragment(parts[0])
        first_ts = cue_end
        if len(parts) >= 2:
            try:
                first_ts = _parse_timestamp(parts[1])
            except ValueError:
                first_ts = cue_end
        if leading:
            timed.extend(_expand_untimed_prefix(leading, cue_start, first_ts))
        for i in range(1, len(parts), 2):
            try:
                ts = _parse_timestamp(parts[i])
            except ValueError:
                continue
            frag = _clean_fragment(parts[i + 1] if i + 1 < len(parts) else "")
            if not frag:
                continue
            # Each <c>…</c> chunk is usually one token; keep punctuation attached.
            tokens = frag.split()
            if len(tokens) <= 1:
                timed.append((ts, frag))
            else:
                # Rare multi-word <c> chunk: keep same start, tiny stagger for end calc.
                for tok in tokens:
                    timed.append((ts, tok))

    if not timed:
        return []

    words: list[dict[str, Any]] = []
    for idx, (start, token) in enumerate(timed):
        if idx + 1 < len(timed):
            end = timed[idx + 1][0]
        else:
            end = cue_end
        if end < start:
            end = start
        words.append(
            {
                "word": token,
                "start": float(start),
                "end": float(end),
                "probability": 1.0,
            }
        )
    return words


def _text_from_words(words: list[dict[str, Any]]) -> str:
    return ensure_sentence_punctuation(
        " ".join(str(w.get("word") or "").strip() for w in words if str(w.get("word") or "").strip())
    )


def _parse_vtt_cues(content: str) -> list[_Cue]:
    """Line-scan WebVTT cues (blank lines inside YouTube cues are tolerated)."""
    lines = content.replace("\r\n", "\n").split("\n")
    cues: list[_Cue] = []
    i = 0
    while i < len(lines):
        raw = lines[i]
        line = raw.strip()
        i += 1
        if not line:
            continue
        upper = line.upper()
        if upper.startswith("WEBVTT") or upper.startswith("NOTE"):
            continue
        if line.startswith("Kind:") or line.startswith("Language:"):
            continue
        if line.isdigit():
            continue
        match = _TIMESTAMP_RE.match(line)
        if not match:
            continue
        start = _parse_timestamp(match.group("start"))
        end = _parse_timestamp(match.group("end"))

        payload_lines: list[str] = []
        while i < len(lines):
            nxt = lines[i]
            stripped = nxt.strip()
            if _TIMESTAMP_RE.match(stripped):
                break
            if not stripped:
                if payload_lines:
                    i += 1
                    break
                i += 1
                continue
            payload_lines.append(nxt)
            i += 1

        if not payload_lines:
            continue

        raw_payload = "\n".join(payload_lines)
        words = extract_karaoke_words(raw_payload, start, end)
        if words:
            text = _text_from_words(words)
        else:
            text = clean_vtt_text(" ".join(payload_lines))
            text = ensure_sentence_punctuation(text) if text else ""
        if not text:
            continue
        cues.append(_Cue(start=start, end=end, text=text, words=words))
    return cues


def _prefer_words(left: list[dict[str, Any]], right: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not left:
        return list(right)
    if not right:
        return list(left)
    return list(left) if len(left) >= len(right) else list(right)


def _merge_short_cues(cues: list[_Cue]) -> list[_Cue]:
    if not cues:
        return cues
    merged: list[_Cue] = []
    for cue in cues:
        if merged and (cue.end - cue.start) < _MIN_CUE_DURATION:
            prev = merged[-1]
            if cue.text == prev.text:
                prev.end = cue.end
                prev.words = _prefer_words(prev.words, cue.words)
            elif cue.words and not prev.words:
                # Tiny karaoke echo: keep previous span text, absorb end only.
                prev.end = cue.end
            elif not cue.words:
                # Plain 10ms finalize line — extend previous cue, keep its words/text.
                prev.end = cue.end
                prev.words = _prefer_words(prev.words, cue.words)
            else:
                prev.end = cue.end
                if prev.words and cue.words:
                    prev.words = list(prev.words) + list(cue.words)
                    prev.text = _text_from_words(prev.words)
                else:
                    prev.text = f"{prev.text} {cue.text}".strip()
                    prev.words = _prefer_words(prev.words, cue.words)
        else:
            merged.append(
                _Cue(start=cue.start, end=cue.end, text=cue.text, words=list(cue.words))
            )
    return merged


def _merge_duplicate_lines(cues: list[_Cue]) -> list[_Cue]:
    if not cues:
        return cues
    merged: list[_Cue] = [
        _Cue(start=cues[0].start, end=cues[0].end, text=cues[0].text, words=list(cues[0].words))
    ]
    for cue in cues[1:]:
        prev = merged[-1]
        if cue.text == prev.text:
            prev.end = cue.end
            prev.words = _prefer_words(prev.words, cue.words)
        else:
            merged.append(
                _Cue(start=cue.start, end=cue.end, text=cue.text, words=list(cue.words))
            )
    return merged


def _drop_plain_echoes_when_karaoke(cues: list[_Cue]) -> list[_Cue]:
    """If the file has karaoke timings, keep timed cues and drop plain echoes."""
    if not any(c.words for c in cues):
        return cues
    timed = [c for c in cues if c.words]
    return timed or cues


def parse_vtt(path: Path, *, speaker: str = DEFAULT_SPEAKER) -> list[Turn]:
    """Parse WebVTT into turn list with HTML cleanup, karaoke words, and cue merging."""
    content = path.read_text(encoding="utf-8")
    cues = _parse_vtt_cues(content)
    cues = _drop_plain_echoes_when_karaoke(cues)
    cues = _merge_short_cues(cues)
    cues = _merge_duplicate_lines(cues)
    return [
        Turn(
            speaker=speaker,
            start=cue.start,
            end=cue.end,
            text=cue.text,
            words=list(cue.words) if cue.words else [],
        )
        for cue in cues
    ]


def download_caption(url: str, track: CaptionTrack, dest: Path) -> Path:
    """Download a single caption track via yt-dlp. Returns path to VTT."""
    file_stem = dest.stem
    # Prefer short stable basename when dest looks like ``…/video_id.zh``.
    paths = download_caption_tracks(
        url,
        [track],
        dest.parent,
        dest.stem,
        file_stem=file_stem,
    )
    path = paths.get(track.lang_code) or next(iter(paths.values()), None)
    if path is None:
        raise FileNotFoundError(f"yt-dlp 未產生 VTT 字幕：{dest}")
    if path != dest:
        dest.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
        if path.name != dest.name:
            try:
                path.unlink()
            except OSError:
                pass
        return dest
    return path


def download_caption_tracks(
    url: str,
    tracks: list[CaptionTrack],
    dest_dir: Path,
    stem: str,
    *,
    file_stem: str | None = None,
    raw_info: dict[str, Any] | None = None,
) -> dict[str, Path]:
    """Download caption langs via yt-dlp.

    Prefer ``raw_info`` from an earlier probe (``--load-info-json``) so we do not
    re-extract the watch page before each subtitle fetch.

    Important order: finish Chinese (secondary) attempts **before** English.
    YouTube often HTTP 429s ``zh-*`` after an English timedtext fetch.

    Returns map of requested lang_code → VTT path.
    """
    if not tracks:
        return {}

    dest_dir.mkdir(parents=True, exist_ok=True)
    out_stem = (file_stem or stem).strip() or stem
    _clear_caption_artifacts(dest_dir, stem, out_stem)

    info_json = _write_info_json(dest_dir, raw_info) if raw_info else None
    current_info = raw_info

    primary, *rest = tracks
    found: dict[str, Path] = {}

    # --- Secondary (ZH) first, with refresh retry, all before English ---
    if rest:
        found.update(
            _ytdlp_write_subs(
                url,
                rest,
                dest_dir,
                out_stem,
                info_json=info_json,
                ignore_errors=True,
            )
        )
        missing_rest = [t for t in rest if t.lang_code not in found]
        if missing_rest:
            log_stage("zh_caption", "中文字幕未寫入，刷新 metadata 後重試…")
            try:
                from yt_decoder.ytdlp import dump_json

                current_info = dump_json(url)
                info_json = _write_info_json(dest_dir, current_info)
            except Exception as exc:  # noqa: BLE001
                log_stage("zh_caption", f"刷新 metadata 失敗：{exc}")
            else:
                found.update(
                    _ytdlp_write_subs(
                        url,
                        missing_rest,
                        dest_dir,
                        out_stem,
                        info_json=info_json,
                        ignore_errors=True,
                    )
                )
            missing_rest = [t for t in rest if t.lang_code not in found]
            if missing_rest:
                # Live extract (no load-info) as last ZH attempt before English.
                found.update(
                    _ytdlp_write_subs(
                        url,
                        missing_rest,
                        dest_dir,
                        out_stem,
                        info_json=None,
                        ignore_errors=True,
                    )
                )
            missing_rest = [t for t in rest if t.lang_code not in found]
            if missing_rest and current_info:
                found.update(
                    _download_subs_via_timedtext_urls(
                        current_info,
                        missing_rest,
                        dest_dir,
                        out_stem,
                    )
                )

    # --- English after ZH attempts ---
    found.update(
        _ytdlp_write_subs(
            url,
            [primary],
            dest_dir,
            out_stem,
            info_json=info_json,
        )
    )

    if primary.lang_code not in found:
        log_stage(
            "caption",
            f"主軌道 {primary.lang_code} 未寫入，重試；目錄："
            f"{sorted(p.name for p in dest_dir.glob('*.vtt'))}",
        )
        found.update(
            _ytdlp_write_subs(
                url,
                [primary],
                dest_dir,
                out_stem,
                info_json=info_json,
            )
        )
        if primary.lang_code not in found:
            found.update(
                _ytdlp_write_subs(
                    url,
                    [primary],
                    dest_dir,
                    out_stem,
                    info_json=None,
                )
            )

    # Normalize to ``{stem}.{lang}.vtt`` when yt-dlp used a shorter out_stem.
    normalized: dict[str, Path] = {}
    for lang_code, path in found.items():
        target = dest_dir / f"{stem}.{lang_code}.vtt"
        if path.resolve() != target.resolve():
            target.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
            normalized[lang_code] = target
        else:
            normalized[lang_code] = path
    return normalized


def _download_subs_via_timedtext_urls(
    raw_info: dict[str, Any],
    tracks: list[CaptionTrack],
    dest_dir: Path,
    out_stem: str,
) -> dict[str, Path]:
    """Last-resort: GET the VTT URL embedded in probe dump (no yt-dlp extract)."""
    from urllib.error import HTTPError, URLError
    from urllib.request import Request, urlopen

    found: dict[str, Path] = {}
    for track in tracks:
        bucket = (
            raw_info.get("subtitles")
            if track.kind == "manual"
            else raw_info.get("automatic_captions")
        ) or {}
        formats = bucket.get(track.lang_code) or []
        vtt = next((f for f in formats if f.get("ext") == "vtt" and f.get("url")), None)
        if vtt is None:
            continue
        req = Request(
            vtt["url"],
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
            },
        )
        try:
            data = urlopen(req, timeout=30).read()
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            log_stage("zh_caption", f"直接下載 {track.lang_code} 失敗：{exc}")
            continue
        if not data or b"WEBVTT" not in data[:64] and b"webvtt" not in data[:64].lower():
            # Some responses are valid VTT without BOM; still accept non-empty.
            if len(data) < 32:
                continue
        path = dest_dir / f"{out_stem}.{track.lang_code}.vtt"
        path.write_bytes(data)
        found[track.lang_code] = path
        log_stage("zh_caption", f"直接下載 {track.lang_code} 成功（{len(data)} bytes）")
    return found


def _write_info_json(dest_dir: Path, raw_info: dict[str, Any]) -> Path:
    path = dest_dir / ".ytdlp-info.json"
    path.write_text(json.dumps(raw_info, ensure_ascii=False), encoding="utf-8")
    return path


def _clear_caption_artifacts(dest_dir: Path, stem: str, out_stem: str) -> None:
    patterns = (
        f"{stem}.vtt",
        f"{stem}.*.vtt",
        f"{out_stem}.vtt",
        f"{out_stem}.*.vtt",
    )
    seen: set[Path] = set()
    for pattern in patterns:
        for path in dest_dir.glob(pattern):
            if path in seen:
                continue
            seen.add(path)
            try:
                path.unlink()
            except OSError:
                pass


def _ytdlp_write_subs(
    url: str,
    tracks: list[CaptionTrack],
    dest_dir: Path,
    out_stem: str,
    *,
    info_json: Path | None = None,
    ignore_errors: bool = False,
) -> dict[str, Path]:
    langs: list[str] = []
    for track in tracks:
        if track.lang_code and track.lang_code not in langs:
            langs.append(track.lang_code)

    out_template = str(dest_dir / out_stem) + ".%(ext)s"
    args: list[str] = [
        "--skip-download",
        "--sub-format",
        "vtt/best",
        "-o",
        out_template,
        "--sub-langs",
        ",".join(langs),
    ]
    if ignore_errors:
        args.insert(0, "-i")
    if any(t.kind == "manual" for t in tracks):
        args.append("--write-subs")
    if any(t.kind == "auto" for t in tracks):
        args.append("--write-auto-subs")

    if info_json is not None and info_json.is_file():
        # Reuse probe dump — avoids a second watch-page extract (common 429 cause).
        result = _run_ytdlp_args(
            "--load-info-json",
            str(info_json),
            *args,
            check=False,
        )
    else:
        result = run_ytdlp(url, *args, check=False)

    found: dict[str, Path] = {}
    for track in tracks:
        path = _find_downloaded_vtt(dest_dir, out_stem, track.lang_code)
        if path is not None:
            found[track.lang_code] = path

    if not found:
        err = result.stderr or result.stdout or ""
        summary = _ytdlp_err_summary(err, result.returncode)
        # With ignore_errors (secondary ZH fetch) keep the log quiet unless it
        # looks like a real rate-limit / hard failure — empty exit=0 is common
        # and often recovered by a later retry.
        if ignore_errors and summary.startswith("exit="):
            pass
        else:
            log_stage(
                "caption",
                f"yt-dlp 未寫入 {'/'.join(langs)}（{summary}）",
            )
    return found


def _ytdlp_err_summary(err: str, returncode: int) -> str:
    """Prefer real ERROR/429 lines over Python deprecation noise."""
    lines = [ln.strip() for ln in (err or "").splitlines() if ln.strip()]
    for ln in reversed(lines):
        low = ln.lower()
        if "deprecated feature" in low or "notopensslwarning" in low:
            continue
        if any(k in ln for k in ("ERROR", "Unable", "429", "HTTP Error")):
            return ln[:160]
    for ln in reversed(lines):
        low = ln.lower()
        if "deprecated feature" in low or "urllib3" in low or "warnings.warn" in low:
            continue
        return ln[:160]
    return f"exit={returncode}"


def _run_ytdlp_args(*args: str, check: bool = True):
    """Run yt-dlp with an explicit argv (no trailing URL). Used with --load-info-json."""
    from yt_decoder.ytdlp import (
        _YOUTUBE_EXTRACTOR_ARGS,
        _ffmpeg_args,
        _map_ytdlp_error,
        ytdlp_argv,
    )

    cmd = [
        *ytdlp_argv(),
        "--no-playlist",
        "--no-warnings",
        *_YOUTUBE_EXTRACTOR_ARGS,
        *_ffmpeg_args(),
        *args,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if check and result.returncode != 0:
        raise _map_ytdlp_error(result.stderr or result.stdout)
    return result


def _normalize_lang_token(value: str) -> str:
    return value.strip().lower().replace("_", "-")


def _find_downloaded_vtt(dest_dir: Path, stem: str, lang_code: str) -> Path | None:
    """Locate yt-dlp output like ``stem.zh-Hant.vtt`` / ``stem.en.vtt`` / ``stem.vtt``."""
    lang_key = _normalize_lang_token(lang_code)

    plain = dest_dir / f"{stem}.vtt"
    candidates = sorted(dest_dir.glob(f"{stem}.*.vtt"))
    if plain.is_file():
        candidates = [plain, *candidates]

    exact: list[Path] = []
    prefix: list[Path] = []
    plain_hits: list[Path] = []
    for path in candidates:
        name = path.name
        if name == f"{stem}.vtt":
            plain_hits.append(path)
            continue
        if not name.startswith(stem + ".") or not name.endswith(".vtt"):
            continue
        suffix = name[len(stem) + 1 : -4]
        if not suffix:
            continue
        token = _normalize_lang_token(suffix)
        if token == lang_key:
            exact.append(path)
        elif token.startswith(lang_key) or lang_key.startswith(token):
            prefix.append(path)
    if exact:
        return exact[0]
    if prefix:
        return prefix[0]
    # Single-lang downloads sometimes omit the lang infix.
    if plain_hits:
        return plain_hits[0]
    return None


def vtt_turns_to_dicts(turns: list[Turn]) -> list[dict[str, Any]]:
    return [t.to_dict() for t in turns]
