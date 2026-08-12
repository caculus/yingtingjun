#!/usr/bin/env python3
"""Pick any recording → detect English → ASR + speaker diarization + ZH translation."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
import torchaudio
from sklearn.cluster import AgglomerativeClustering, SpectralClustering
from sklearn.metrics import silhouette_score

from asr_backend import (
    MLX_DEFAULT_MODEL,
    configure_asr,
    configured_asr_name,
    get_configured_asr,
)

AUDIO_SUFFIXES = {".wav", ".m4a", ".mp3", ".aac", ".flac", ".ogg", ".caf", ".aiff", ".aif"}


def media_stem(path: Path) -> str:
    """meeting.work.wav → meeting；foo.m4a → foo"""
    name = path.name
    if name.endswith(".work.wav"):
        return name[: -len(".work.wav")]
    return path.stem


def format_ts(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"
    return f"{m:02d}:{s:02d}.{ms:03d}"


def pick_audio_file() -> Path | None:
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        try:
            root.attributes("-topmost", True)
        except tk.TclError:
            pass
        path = filedialog.askopenfilename(
            title="選擇錄音檔",
            filetypes=[
                ("Audio", "*.m4a *.wav *.mp3 *.aac *.flac *.ogg *.caf *.aiff *.aif"),
                ("All files", "*.*"),
            ],
        )
        root.destroy()
        return Path(path) if path else None
    except Exception as exc:  # noqa: BLE001
        print(f"無法開啟檔案選擇視窗：{exc}", file=sys.stderr)
        return None


def ensure_work_wav(src: Path, out_dir: Path) -> Path:
    """Convert any supported audio to 16 kHz mono WAV via afconvert/soundfile."""
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = media_stem(src)
    dest = out_dir / f"{stem}.work.wav"
    if src.resolve() == dest.resolve():
        return dest

    if src.suffix.lower() == ".wav":
        try:
            audio, sr = sf.read(str(src), always_2d=False)
            if audio.ndim > 1:
                audio = audio.mean(axis=1)
            if sr == 16000:
                sf.write(str(dest), audio, 16000, subtype="PCM_16")
                return dest
        except Exception:
            pass

    afconvert = Path("/usr/bin/afconvert")
    if afconvert.exists():
        cmd = [
            str(afconvert),
            "-f",
            "WAVE",
            "-d",
            "LEI16@16000",
            "-c",
            "1",
            str(src),
            str(dest),
        ]
        print(f"[0/4] Converting audio → {dest.name} ...", flush=True)
        subprocess.run(cmd, check=True)
        return dest

    # Fallback: soundfile may still open some formats.
    print(f"[0/4] Loading audio via soundfile → {dest.name} ...", flush=True)
    audio, sr = load_audio_mono(src, target_sr=16000)
    sf.write(str(dest), audio, 16000, subtype="PCM_16")
    return dest


def load_audio_mono(path: Path, target_sr: int = 16000) -> tuple[np.ndarray, int]:
    audio, sr = sf.read(str(path), always_2d=False)
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    audio = audio.astype(np.float32)
    if sr != target_sr:
        tensor = torch.from_numpy(audio).unsqueeze(0)
        tensor = torchaudio.functional.resample(tensor, sr, target_sr)
        audio = tensor.squeeze(0).numpy()
        sr = target_sr
    peak = np.max(np.abs(audio)) if audio.size else 0.0
    if peak > 1.0:
        audio = audio / peak
    return audio, sr


def detect_language(audio: np.ndarray, sr: int, model: str, probe_sec: float = 45.0) -> str:
    print("[1/4] Detecting language ...", flush=True)
    lang = get_configured_asr().detect_language(audio, sr, model, probe_sec=probe_sec)
    print(f"       Detected language: {lang or 'unknown'}", flush=True)
    return lang


def transcribe(
    audio: np.ndarray,
    model: str,
    language: str = "en",
    *,
    condition_on_previous_text: bool = True,
    compression_ratio_threshold: float | None = 2.4,
) -> dict:
    backend = configured_asr_name()
    print(
        f"[2/4] Transcribing ({language}) with {model} [{backend}] ...",
        flush=True,
    )
    return get_configured_asr().transcribe(
        audio,
        model,
        language=language,
        condition_on_previous_text=condition_on_previous_text,
        compression_ratio_threshold=compression_ratio_threshold,
    )


def collect_words(segments: list[dict]) -> list[dict]:
    words: list[dict] = []
    for seg in segments:
        seg_words = seg.get("words") or []
        if seg_words:
            for w in seg_words:
                text = (w.get("word") or "").strip()
                if not text:
                    continue
                start = w.get("start")
                end = w.get("end")
                if start is None or end is None:
                    continue
                words.append(
                    {
                        "word": text,
                        "start": float(start),
                        "end": float(end),
                        "probability": float(w.get("probability") or 0.0),
                    }
                )
        else:
            text = (seg.get("text") or "").strip()
            if not text:
                continue
            words.append(
                {
                    "word": text,
                    "start": float(seg.get("start") or 0.0),
                    "end": float(seg.get("end") or 0.0),
                    "probability": 0.0,
                }
            )
    words.sort(key=lambda w: (w["start"], w["end"]))
    return words


def join_texts(left: str, right: str) -> str:
    left = left.rstrip()
    right = right.lstrip()
    if not left:
        return right
    if not right:
        return left
    if right[0] in ",.;:!?":
        return left + right
    return left + " " + right


def choose_num_speakers(embeddings: np.ndarray, min_spk: int, max_spk: int) -> int:
    n = len(embeddings)
    if n < 2:
        return 1
    max_spk = min(max_spk, n)
    min_spk = max(1, min(min_spk, max_spk))
    if min_spk == max_spk:
        return min_spk

    best_k, best_score = min_spk, -1.0
    for k in range(min_spk, max_spk + 1):
        if k == 1:
            return 1
        labels = AgglomerativeClustering(n_clusters=k, metric="cosine", linkage="average").fit_predict(
            embeddings
        )
        if len(set(labels)) < 2:
            continue
        score = silhouette_score(embeddings, labels, metric="cosine")
        if score > best_score:
            best_score = score
            best_k = k
    return best_k


def sliding_window_embeddings(
    classifier,
    audio: np.ndarray,
    sr: int,
    win: float = 1.5,
    hop: float = 0.75,
    min_rms: float = 0.01,
) -> tuple[np.ndarray, np.ndarray]:
    n = len(audio)
    win_n = int(win * sr)
    hop_n = int(hop * sr)
    embs: list[np.ndarray] = []
    centers: list[float] = []

    for start_i in range(0, max(1, n - win_n + 1), hop_n):
        end_i = min(n, start_i + win_n)
        chunk = audio[start_i:end_i]
        if chunk.size < int(0.4 * sr):
            continue
        rms = float(np.sqrt(np.mean(chunk**2)))
        if rms < min_rms:
            continue
        wav = torch.from_numpy(chunk).float().unsqueeze(0)
        with torch.no_grad():
            emb = classifier.encode_batch(wav)
        vec = emb.squeeze().cpu().numpy().astype(np.float32)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        embs.append(vec)
        centers.append((start_i + end_i) / 2.0 / sr)

    if not embs:
        return np.zeros((0, 1), dtype=np.float32), np.zeros((0,), dtype=np.float32)
    return np.vstack(embs), np.asarray(centers, dtype=np.float32)


def assign_words_to_speakers(
    words: list[dict],
    centers: np.ndarray,
    labels: np.ndarray,
) -> list[dict]:
    if len(centers) == 0:
        for w in words:
            w["speaker"] = "SPEAKER_01"
        return words

    order: list[int] = []
    for lab in labels:
        lab_i = int(lab)
        if lab_i not in order:
            order.append(lab_i)
    remap = {old: i + 1 for i, old in enumerate(order)}

    for w in words:
        mid = 0.5 * (w["start"] + w["end"])
        j = int(np.argmin(np.abs(centers - mid)))
        w["speaker"] = f"SPEAKER_{remap[int(labels[j])]:02d}"
    return words


def words_to_speaker_turns(words: list[dict], max_gap: float = 0.8) -> list[dict]:
    turns: list[dict] = []
    for w in words:
        text = (w.get("word") or "").strip()
        if not text:
            continue
        speaker = w.get("speaker", "SPEAKER_01")
        start = float(w["start"])
        end = float(w["end"])

        if turns and turns[-1]["speaker"] == speaker and start - turns[-1]["end"] <= max_gap:
            prev = turns[-1]
            prev["text"] = join_texts(prev["text"], text)
            prev["end"] = end
            prev["words"].append(w)
        else:
            turns.append(
                {
                    "speaker": speaker,
                    "start": start,
                    "end": end,
                    "text": text,
                    "words": [w],
                }
            )
    return turns


_SENTENCE_END_RE = re.compile(r'[.!?。！？]["\'”’)\]]*$')


def word_ends_sentence(word: str) -> bool:
    return bool(_SENTENCE_END_RE.search((word or "").strip()))


def split_text_sentences(text: str) -> list[str]:
    raw = (text or "").strip()
    if not raw:
        return []
    parts = [p.strip() for p in re.split(r"(?<=[.!?。！？])\s*", raw) if p.strip()]
    return parts or [raw]


def split_zh_sentences(text: str) -> list[str]:
    raw = (text or "").strip()
    if not raw:
        return []
    parts = [p.strip() for p in re.split(r"(?<=[。！？.!?])", raw) if p.strip()]
    return parts or [raw]


def group_words_into_sentences(words: list[dict]) -> list[list[dict]]:
    groups: list[list[dict]] = []
    buf: list[dict] = []
    for i, w in enumerate(words):
        buf.append(w)
        if word_ends_sentence(str(w.get("word") or "")) or i == len(words) - 1:
            groups.append(buf)
            buf = []
    if buf:
        groups.append(buf)
    return groups


def join_word_list(words: list[dict]) -> str:
    text = ""
    for w in words:
        piece = (w.get("word") or "").strip()
        if not piece:
            continue
        text = join_texts(text, piece)
    return text.strip()


def zh_slice_for_sentence_range(
    zh_parts: list[str], start_i: int, end_i: int, en_total: int
) -> str:
    if not zh_parts or en_total <= 0 or start_i >= end_i:
        return ""
    if len(zh_parts) == en_total:
        return "".join(zh_parts[start_i:end_i]).strip()
    z0 = int(round(start_i * len(zh_parts) / en_total))
    z1 = int(round(end_i * len(zh_parts) / en_total))
    z0 = max(0, min(len(zh_parts) - 1, z0))
    z1 = max(z0 + 1, min(len(zh_parts), max(z1, z0 + 1)))
    return "".join(zh_parts[z0:z1]).strip()


def split_turns_by_max_sentences(
    turns: list[dict], max_sentences: int = 3
) -> list[dict]:
    """Split long speaker turns so each chunk has at most `max_sentences` sentences."""
    if max_sentences < 1:
        max_sentences = 1
    out: list[dict] = []
    for turn in turns:
        words = [w for w in (turn.get("words") or []) if (w.get("word") or "").strip()]
        speaker = turn.get("speaker", "SPEAKER_01")
        text_zh_full = (turn.get("text_zh") or "").strip()

        if words:
            sentences = group_words_into_sentences(words)
        else:
            # Fallback: no word timestamps — split plain text only.
            en_parts = split_text_sentences(turn.get("text") or "")
            if len(en_parts) <= max_sentences:
                out.append(turn)
                continue
            zh_parts = split_zh_sentences(text_zh_full)
            en_total = len(en_parts)
            span = max(0.05, float(turn.get("end") or 0) - float(turn.get("start") or 0))
            for i in range(0, en_total, max_sentences):
                chunk = en_parts[i : i + max_sentences]
                frac0 = i / en_total
                frac1 = min(en_total, i + max_sentences) / en_total
                start = float(turn.get("start") or 0) + span * frac0
                end = float(turn.get("start") or 0) + span * frac1
                out.append(
                    {
                        "speaker": speaker,
                        "start": start,
                        "end": end,
                        "text": " ".join(chunk).strip(),
                        "text_zh": zh_slice_for_sentence_range(
                            zh_parts, i, min(en_total, i + max_sentences), en_total
                        ),
                        "words": [],
                    }
                )
            continue

        if len(sentences) <= max_sentences:
            out.append(turn)
            continue

        zh_parts = split_zh_sentences(text_zh_full)
        en_total = len(sentences)
        for i in range(0, en_total, max_sentences):
            chunk_sents = sentences[i : i + max_sentences]
            flat = [w for sent in chunk_sents for w in sent]
            text = join_word_list(flat)
            out.append(
                {
                    "speaker": speaker,
                    "start": float(flat[0]["start"]),
                    "end": float(flat[-1]["end"]),
                    "text": text,
                    "text_zh": zh_slice_for_sentence_range(
                        zh_parts, i, min(en_total, i + max_sentences), en_total
                    ),
                    "words": flat,
                }
            )
    return out


ROOT = Path(__file__).resolve().parent


def find_speakrs_bin() -> Path | None:
    env = (os.environ.get("SPEAKRS_BIN") or "").strip()
    candidates = []
    if env:
        candidates.append(Path(env))
    candidates.extend(
        [
            ROOT / "bin" / "speakrs_diarize",
            ROOT / "tools" / "speakrs_cli" / "target" / "release" / "speakrs_diarize",
        ]
    )
    for path in candidates:
        if path.is_file() and os.access(path, os.X_OK):
            return path
    return None


def remap_speaker_labels(raw_labels: list[str]) -> dict[str, str]:
    """Map speakrs SPEAKER_00… to project SPEAKER_01… by first-appearance order."""
    order: list[str] = []
    for lab in raw_labels:
        if lab not in order:
            order.append(lab)
    return {old: f"SPEAKER_{i + 1:02d}" for i, old in enumerate(order)}


def assign_words_from_segments(words: list[dict], segments: list[dict]) -> list[dict]:
    if not segments:
        for w in words:
            w["speaker"] = "SPEAKER_01"
        return words

    mapping = remap_speaker_labels([s["speaker"] for s in segments])
    segs = [
        {
            "start": float(s["start"]),
            "end": float(s["end"]),
            "speaker": mapping[s["speaker"]],
        }
        for s in segments
    ]

    for w in words:
        start = float(w["start"])
        end = float(w["end"])
        best_speaker = None
        best_overlap = 0.0
        for seg in segs:
            overlap = max(0.0, min(seg["end"], end) - max(seg["start"], start))
            if overlap > best_overlap:
                best_overlap = overlap
                best_speaker = seg["speaker"]
        if best_speaker is None:
            mid = 0.5 * (start + end)
            best_speaker = min(
                segs, key=lambda s: abs(0.5 * (s["start"] + s["end"]) - mid)
            )["speaker"]
        w["speaker"] = best_speaker
    return words


def smooth_word_speakers(words: list[dict]) -> list[dict]:
    for i in range(1, len(words) - 1):
        if (
            words[i - 1]["speaker"] == words[i + 1]["speaker"] != words[i]["speaker"]
            and words[i]["end"] - words[i]["start"] < 0.6
        ):
            words[i]["speaker"] = words[i - 1]["speaker"]
    return words


def run_speakrs_diarize(
    wav_path: Path,
    mode: str = "coreml",
    models_dir: Path | None = None,
) -> list[dict]:
    binary = find_speakrs_bin()
    if binary is None:
        raise FileNotFoundError(
            "找不到 speakrs_diarize。請先執行：bash scripts/build_speakrs.sh"
        )

    cmd = [str(binary), "--mode", mode]
    if models_dir is not None:
        cmd.extend(["--models-dir", str(models_dir)])
    cmd.append(str(wav_path))
    print(f"       $ {' '.join(cmd)}", flush=True)
    proc = subprocess.run(
        cmd,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.stderr:
        for line in proc.stderr.splitlines():
            print(f"       {line}", flush=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"speakrs_diarize failed (exit={proc.returncode}): "
            f"{(proc.stderr or proc.stdout or '').strip()[-500:]}"
        )
    raw = (proc.stdout or "").strip()
    if not raw:
        raise RuntimeError("speakrs_diarize returned empty stdout")
    # Binary prints a single JSON object (possibly after logs on stderr only).
    data = json.loads(raw.splitlines()[-1])
    segments = data.get("segments") or []
    if not isinstance(segments, list):
        raise RuntimeError("speakrs_diarize JSON missing segments list")
    return segments


def diarize_words_speakrs(
    words: list[dict],
    wav_path: Path,
    mode: str = "coreml",
    models_dir: Path | None = None,
) -> list[dict]:
    print("[3/4] Estimating speakers (speakrs) ...", flush=True)
    segments = run_speakrs_diarize(wav_path, mode=mode, models_dir=models_dir)
    print(f"       speakrs segments: {len(segments)}", flush=True)
    words = assign_words_from_segments(words, segments)
    words = smooth_word_speakers(words)
    return words_to_speaker_turns(words)


def load_ecapa_window_embeddings(
    audio: np.ndarray, sr: int
) -> tuple[np.ndarray, np.ndarray]:
    """Load ECAPA encoder and compute sliding-window speaker embeddings."""
    from speechbrain.inference.speaker import EncoderClassifier

    classifier = EncoderClassifier.from_hparams(
        source="speechbrain/spkrec-ecapa-voxceleb",
        savedir="models/spkrec-ecapa-voxceleb",
        run_opts={"device": "cpu"},
    )
    return sliding_window_embeddings(classifier, audio, sr)


def estimate_num_speakers_ecapa(
    audio: np.ndarray,
    sr: int,
    min_speakers: int,
    max_speakers: int,
) -> int:
    """Estimate speaker count via ECAPA embeddings + silhouette (no ASR)."""
    print("[estimate] Computing ECAPA embeddings ...", flush=True)
    X, centers = load_ecapa_window_embeddings(audio, sr)
    if len(centers) == 0:
        print("       No usable speech windows; assuming 1 speaker", flush=True)
        return 1

    n_speakers = choose_num_speakers(X, min_speakers, max_speakers)
    if min_speakers >= 2 and n_speakers < 2 and len(centers) >= 4:
        n_speakers = 2
    print(
        f"       Estimated {n_speakers} speaker(s) "
        f"(range {min_speakers}–{max_speakers}, {len(centers)} windows)",
        flush=True,
    )
    return n_speakers


def cluster_speaker_labels(X: np.ndarray, n_speakers: int) -> np.ndarray:
    if n_speakers <= 1 or len(X) == 0:
        return np.zeros(len(X), dtype=int)
    if n_speakers == 2 and len(X) >= 20:
        return SpectralClustering(
            n_clusters=2, affinity="nearest_neighbors", random_state=0
        ).fit_predict(X)
    return AgglomerativeClustering(
        n_clusters=n_speakers, metric="cosine", linkage="average"
    ).fit_predict(X)


def diarize_words_ecapa(
    words: list[dict],
    audio: np.ndarray,
    sr: int,
    min_speakers: int,
    max_speakers: int,
) -> list[dict]:
    print("[3/4] Estimating speakers (ECAPA sliding windows) ...", flush=True)
    X, centers = load_ecapa_window_embeddings(audio, sr)
    if len(centers) == 0:
        for w in words:
            w["speaker"] = "SPEAKER_01"
        return words_to_speaker_turns(words)

    n_speakers = choose_num_speakers(X, min_speakers, max_speakers)
    if min_speakers >= 2 and n_speakers < 2 and len(centers) >= 4:
        n_speakers = 2
    # Cannot cluster into more groups than windows.
    n_speakers = max(1, min(n_speakers, len(centers)))
    if min_speakers == max_speakers:
        print(
            f"       Forced {n_speakers} speaker(s) from {len(centers)} windows",
            flush=True,
        )
    else:
        print(
            f"       Detected {n_speakers} speaker(s) from {len(centers)} windows",
            flush=True,
        )

    labels = cluster_speaker_labels(X, n_speakers)
    words = assign_words_to_speakers(words, centers, labels)
    words = smooth_word_speakers(words)
    return words_to_speaker_turns(words)


def diarize_words(
    words: list[dict],
    audio: np.ndarray,
    sr: int,
    min_speakers: int,
    max_speakers: int,
    *,
    wav_path: Path | None = None,
    diarizer: str = "auto",
    speakrs_mode: str = "coreml",
    speakrs_models_dir: Path | None = None,
    force_num_speakers: bool = False,
) -> list[dict]:
    """Diarize words. Prefer speakrs; fall back to ECAPA when auto/unavailable."""
    choice = (diarizer or "auto").lower()
    if choice not in {"auto", "speakrs", "ecapa"}:
        raise ValueError(f"Unknown diarizer: {diarizer}")

    # Forced speaker count requires ECAPA clustering (speakrs has no num-speakers API).
    if force_num_speakers and choice != "ecapa":
        print(
            f"       --num-speakers={min_speakers} requires ECAPA; "
            f"overriding diarizer={choice} → ecapa",
            flush=True,
        )
        choice = "ecapa"

    if choice in {"auto", "speakrs"}:
        if wav_path is None:
            if choice == "speakrs":
                raise ValueError("speakrs diarizer requires wav_path")
        else:
            try:
                return diarize_words_speakrs(
                    words,
                    wav_path,
                    mode=speakrs_mode,
                    models_dir=speakrs_models_dir,
                )
            except Exception as exc:  # noqa: BLE001
                if choice == "speakrs":
                    raise
                print(
                    f"       speakrs unavailable ({exc}); falling back to ECAPA …",
                    flush=True,
                )

    return diarize_words_ecapa(words, audio, sr, min_speakers, max_speakers)


def ensure_sentence_punctuation(text: str) -> str:
    text = text.strip()
    if not text:
        return text
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r"([,.;:!?])([A-Za-z])", r"\1 \2", text)
    text = re.sub(r"\bMm\s*-\s*hmm\b", "Mm-hmm", text, flags=re.I)
    text = re.sub(r"\s+", " ", text).strip()
    if text[-1] not in ".?!…\"')":
        text += "."
    return text


_translator = None
_TRANSLATOR_MODEL = "facebook/nllb-200-distilled-600M"
_SRC_LANG = "eng_Latn"
_TGT_LANG = "zho_Hant"  # Traditional Chinese

# NLLB (zho_Hant) sometimes emits Taiwan real-estate empty-state copy for
# short backchannels like "Yeah." / "Mm-hmm." — strip and avoid via glossary.
_NLLB_ZH_HALLUCINATION_RES = [
    re.compile(r"沒有任何樓盤符合您的搜尋結果\.?"),
    re.compile(r"沒有任何樓盤符合您的搜尋\s*[-—–-]?\s*"),
    re.compile(r"沒有任何樓盤符合您的搜尋\.?"),
]

_SHORT_BACKCHANNEL_ZH = {
    "yeah": "嗯。",
    "yes": "對。",
    "yep": "對。",
    "yup": "對。",
    "ok": "好。",
    "okay": "好。",
    "right": "對。",
    "oh": "哦。",
    "ah": "啊。",
    "um": "嗯。",
    "uh": "呃。",
    "hmm": "嗯。",
    "mm": "嗯。",
    "mm-hmm": "嗯嗯。",
    "mmhmm": "嗯嗯。",
    "mhm": "嗯嗯。",
    "uh-huh": "嗯嗯。",
    "uhhuh": "嗯嗯。",
    "sure": "好。",
    "thanks": "謝謝。",
    "thank": "謝謝。",  # "Thank you" → thank + you; handle below
    "you": None,  # paired with thank
    "no": "不。",
    "nope": "不。",
    "wow": "哇。",
    "hello": "你好。",
    "hi": "嗨。",
}


def scrub_zh_hallucinations(zh: str) -> str:
    """Remove known NLLB hallucination phrases from Traditional Chinese output."""
    out = (zh or "").strip()
    if not out:
        return ""
    for pat in _NLLB_ZH_HALLUCINATION_RES:
        out = pat.sub("", out)
    # Collapse leftover punctuation / spaces after scrubbing.
    out = re.sub(r"[ \t]{2,}", " ", out)
    out = re.sub(r"^[。，、；：\s]+", "", out)
    out = re.sub(r"[。]{2,}", "。", out)
    out = re.sub(r"\s+([。，、])", r"\1", out)
    return out.strip()


def zh_still_hallucinated(zh: str) -> bool:
    return "樓盤" in (zh or "") or "搜尋結果" in (zh or "")


def try_glossary_translate(text: str) -> str | None:
    """Map pure backchannel utterances to fixed ZH; return None if not applicable."""
    words = re.findall(r"[A-Za-z]+(?:-[A-Za-z]+)?", text or "")
    if not words:
        return None
    keys = [w.lower() for w in words]
    # "thank you" / "thanks you" style
    if keys == ["thank", "you"] or keys == ["thanks"]:
        return "謝謝。"
    mapped: list[str] = []
    for key in keys:
        if key == "you" and mapped and mapped[-1] == "謝謝。":
            continue
        if key not in _SHORT_BACKCHANNEL_ZH:
            return None
        val = _SHORT_BACKCHANNEL_ZH[key]
        if val is None:
            return None
        mapped.append(val)
    if not mapped:
        return None
    # Avoid "嗯。嗯。" → keep natural repetition but compact identical neighbors lightly.
    return "".join(mapped)


def _purge_speechbrain_lazy_modules() -> None:
    """Avoid speechbrain LazyModule breaking linecache during later imports."""
    for name in list(sys.modules):
        mod = sys.modules.get(name)
        if mod is None:
            continue
        if "speechbrain" in name and type(mod).__name__ == "LazyModule":
            del sys.modules[name]


def get_translator():
    global _translator
    if _translator is not None:
        return _translator
    print(f"[4/4] Loading local EN→ZH-Hant translator ({_TRANSLATOR_MODEL}) ...", flush=True)
    _purge_speechbrain_lazy_modules()
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer, pipeline

    tokenizer = AutoTokenizer.from_pretrained(_TRANSLATOR_MODEL)
    model = AutoModelForSeq2SeqLM.from_pretrained(_TRANSLATOR_MODEL)
    _translator = pipeline(
        "translation",
        model=model,
        tokenizer=tokenizer,
        src_lang=_SRC_LANG,
        tgt_lang=_TGT_LANG,
        device=-1,
    )
    return _translator


def translate_en_to_zh(text: str, max_chars: int = 350) -> str:
    text = (text or "").strip()
    if not text:
        return ""

    # Fast path: pure backchannels never go to NLLB (avoids 樓盤 hallucination).
    glossed = try_glossary_translate(text)
    if glossed is not None:
        return glossed

    translator = get_translator()

    # NLLB often drops earlier sentences when given multi-sentence input — translate
    # one sentence at a time (char-chunk only when a single sentence is very long).
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    if not sentences:
        sentences = [text]

    def translate_piece(piece: str) -> str:
        piece = (piece or "").strip()
        if not piece:
            return ""
        gloss = try_glossary_translate(piece)
        if gloss is not None:
            return gloss
        try:
            result = translator(
                piece,
                src_lang=_SRC_LANG,
                tgt_lang=_TGT_LANG,
                max_length=512,
            )
            item = result[0]
            raw = (
                item.get("translation_text") or item.get("translated_text") or ""
            ).strip() or piece
        except Exception as exc:  # noqa: BLE001
            print(f"       translate warn: {exc}", flush=True)
            return piece

        cleaned = scrub_zh_hallucinations(raw)
        if zh_still_hallucinated(cleaned):
            cleaned = scrub_zh_hallucinations(cleaned)
        if zh_still_hallucinated(cleaned) or not cleaned:
            # Retry once; if still bad, drop hallucination and keep remainder / glossary.
            try:
                result = translator(
                    piece,
                    src_lang=_SRC_LANG,
                    tgt_lang=_TGT_LANG,
                    max_length=512,
                )
                raw2 = (
                    result[0].get("translation_text")
                    or result[0].get("translated_text")
                    or ""
                ).strip()
                cleaned = scrub_zh_hallucinations(raw2)
            except Exception:  # noqa: BLE001
                pass
        if zh_still_hallucinated(cleaned):
            cleaned = scrub_zh_hallucinations(re.sub(r"樓盤|搜尋結果", "", cleaned))
            cleaned = scrub_zh_hallucinations(cleaned)
        if not cleaned:
            gloss = try_glossary_translate(piece)
            if gloss is not None:
                return gloss
        return cleaned or piece

    out: list[str] = []
    for sentence in sentences:
        # Per-sentence glossary (e.g. "Yeah. We should go." → 嗯。 + NLLB rest)
        gloss = try_glossary_translate(sentence)
        if gloss is not None:
            out.append(gloss)
            continue
        if len(sentence) <= max_chars:
            out.append(translate_piece(sentence))
            continue
        # Rare: one very long sentence — split by length, not by merging sentences.
        start = 0
        while start < len(sentence):
            end = min(len(sentence), start + max_chars)
            if end < len(sentence):
                space = sentence.rfind(" ", start, end)
                if space > start:
                    end = space
            out.append(translate_piece(sentence[start:end].strip()))
            start = end
    return scrub_zh_hallucinations("".join(out))


def rescrub_turn_zh(turn: dict, *, retranslate_if_needed: bool = True) -> bool:
    """Fix hallucination in an existing turn's text_zh. Returns True if changed."""
    en = (turn.get("text") or "").strip()
    zh = (turn.get("text_zh") or "").strip()
    before = zh

    gloss = try_glossary_translate(en)
    if gloss is not None:
        turn["text_zh"] = gloss
        return gloss != before

    had_hallucination = "樓盤" in zh or zh_still_hallucinated(zh)
    cleaned = scrub_zh_hallucinations(zh)

    if had_hallucination and retranslate_if_needed and en:
        # Mixed sentences often need a full retranslate after scrubbing.
        turn["text_zh"] = translate_en_to_zh(en)
    else:
        turn["text_zh"] = cleaned

    return (turn.get("text_zh") or "") != before


def translate_turns(turns: list[dict]) -> None:
    print("[4/4] Translating turns to Chinese ...", flush=True)
    try:
        get_translator()
    except Exception as exc:  # noqa: BLE001
        print(f"       Translator unavailable ({exc}); writing English only.", flush=True)
        for turn in turns:
            turn["text_zh"] = turn.get("text_zh") or ""
        return

    for i, turn in enumerate(turns, start=1):
        en = turn.get("text") or ""
        try:
            turn["text_zh"] = translate_en_to_zh(en)
        except Exception as exc:  # noqa: BLE001
            print(f"       turn {i} translate failed: {exc}", flush=True)
            turn["text_zh"] = ""
        if i == 1 or i % 10 == 0 or i == len(turns):
            print(f"       translated {i}/{len(turns)}", flush=True)


def range_backup_path(json_path: Path) -> Path:
    return json_path.with_name(json_path.name + ".bak-range")


def range_meta_path(json_path: Path) -> Path:
    return json_path.with_name(json_path.name + ".range-meta.json")


def resolve_work_audio_for_stem(stem: str, workdir: Path, audio: Path | None = None) -> Path:
    if audio is not None:
        path = Path(audio)
        if path.exists():
            return path
        raise FileNotFoundError(f"Audio not found: {path}")
    candidate = workdir / f"{stem}.work.wav"
    if candidate.exists():
        return candidate
    raise FileNotFoundError(
        f"找不到音檔：請提供 --audio，或確認存在 {candidate}"
    )


def _interval_overlap(a0: float, a1: float, b0: float, b1: float) -> float:
    return max(0.0, min(a1, b1) - max(a0, b0))


def inherit_speaker_for_word(words_start: float, words_end: float, old_turns: list[dict]) -> str:
    """Pick speaker from old turns by max time overlap; else nearest turn."""
    best_spk = "SPEAKER_01"
    best_ov = 0.0
    for turn in old_turns:
        ov = _interval_overlap(
            words_start, words_end, float(turn["start"]), float(turn["end"])
        )
        if ov > best_ov:
            best_ov = ov
            best_spk = turn.get("speaker") or "SPEAKER_01"
    if best_ov > 0:
        return best_spk

    mid = 0.5 * (words_start + words_end)
    best_dist = float("inf")
    for turn in old_turns:
        tmid = 0.5 * (float(turn["start"]) + float(turn["end"]))
        dist = abs(tmid - mid)
        if dist < best_dist:
            best_dist = dist
            best_spk = turn.get("speaker") or "SPEAKER_01"
    return best_spk


def splice_turns_for_range(
    old_turns: list[dict],
    new_turns: list[dict],
    start: float,
    end: float,
) -> list[dict]:
    """Remove old turns overlapping [start, end]; insert new_turns sorted by time."""
    kept = [
        t
        for t in old_turns
        if _interval_overlap(float(t["start"]), float(t["end"]), start, end) <= 0
    ]
    merged = kept + list(new_turns)
    merged.sort(key=lambda t: (float(t["start"]), float(t["end"])))
    return merged


def retranscribe_time_range(
    json_path: Path,
    *,
    start: float,
    end: float,
    audio_path: Path | None = None,
    workdir: Path = Path("workdir"),
    outdir: Path | None = None,
    model: str = "mlx-community/whisper-large-v3-turbo",
    padding: float = 0.75,
    max_sentences: int = 3,
    skip_translate: bool = False,
) -> dict:
    """Re-ASR + re-translate only turns overlapping [start, end]; snapshot for restore."""
    json_path = Path(json_path)
    if not json_path.exists():
        raise FileNotFoundError(f"Transcript not found: {json_path}")
    if end <= start:
        raise ValueError(f"Invalid range: start={start} end={end}")

    data = json.loads(json_path.read_text(encoding="utf-8"))
    old_turns = data.get("turns") or []
    if not old_turns:
        raise ValueError("No turns in JSON")

    stem = media_stem(json_path)
    out_dir = Path(outdir) if outdir is not None else json_path.parent
    work_audio = resolve_work_audio_for_stem(stem, Path(workdir), audio_path)
    audio, sr = load_audio_mono(work_audio, target_sr=16000)
    duration = float(len(audio) / sr) if sr else 0.0

    pad = max(0.0, float(padding))
    clip_start = max(0.0, float(start) - pad)
    clip_end = min(duration, float(end) + pad)
    if clip_end <= clip_start:
        raise ValueError(f"Empty audio clip for range {start}-{end} (duration={duration})")

    i0 = int(clip_start * sr)
    i1 = int(clip_end * sr)
    clip = audio[i0:i1]
    print(
        f"[range] Re-ASR {format_ts(start)} → {format_ts(end)} "
        f"(pad={pad:.2f}s, clip={format_ts(clip_start)}–{format_ts(clip_end)}, "
        f"audio={work_audio.name})",
        flush=True,
    )

    # Anti-loop settings for short problematic clips.
    result = transcribe(
        clip,
        model=model,
        language="en",
        condition_on_previous_text=False,
        compression_ratio_threshold=2.4,
    )
    words = collect_words(result.get("segments") or [])
    for w in words:
        w["start"] = float(w["start"]) + clip_start
        w["end"] = float(w["end"]) + clip_start

    # Keep words whose midpoint falls in the user range (ignore padding bleed).
    kept_words: list[dict] = []
    for w in words:
        mid = 0.5 * (float(w["start"]) + float(w["end"]))
        if start <= mid <= end:
            w["speaker"] = inherit_speaker_for_word(
                float(w["start"]), float(w["end"]), old_turns
            )
            kept_words.append(w)

    print(
        f"       Whisper words in clip={len(words)}; kept in range={len(kept_words)}",
        flush=True,
    )
    if not kept_words:
        raise ValueError(
            "此區間沒有辨識到詞（或時間對不上），未修改文稿。可微調起迄或加大 --range-padding。"
        )

    new_turns = words_to_speaker_turns(kept_words)
    for t in new_turns:
        t["text"] = ensure_sentence_punctuation(t.get("text") or "")
        t["text_zh"] = ""
    new_turns = split_turns_by_max_sentences(new_turns, max_sentences=max_sentences)

    if not skip_translate and new_turns:
        translate_turns(new_turns)
    elif new_turns:
        for t in new_turns:
            t["text_zh"] = t.get("text_zh") or ""

    replaced = [
        t
        for t in old_turns
        if _interval_overlap(float(t["start"]), float(t["end"]), start, end) > 0
    ]
    merged = splice_turns_for_range(old_turns, new_turns, start, end)

    bak = range_backup_path(json_path)
    bak.write_text(json_path.read_text(encoding="utf-8"), encoding="utf-8")
    meta = {
        "stem": stem,
        "start": float(start),
        "end": float(end),
        "padding": pad,
        "replaced_turns": len(replaced),
        "new_turns": len(new_turns),
        "backup": bak.name,
        "audio": str(work_audio),
    }
    range_meta_path(json_path).write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"       Snapshot → {bak.name}; replaced {len(replaced)} turn(s) "
        f"with {len(new_turns)} new turn(s)",
        flush=True,
    )

    # Preserve top-level text loosely: rebuild from turns.
    data_out = dict(data)
    data_out["text"] = " ".join((t.get("text") or "").strip() for t in merged).strip()
    write_outputs(merged, out_dir, stem, data_out)
    print(f"[range] Done. Updated {out_dir / (stem + '.json')}", flush=True)
    return {
        "ok": True,
        "stem": stem,
        "start": float(start),
        "end": float(end),
        "replaced_turns": len(replaced),
        "new_turns": len(new_turns),
        "backup": str(bak),
        "transcript": str(out_dir / f"{stem}.json"),
    }


def restore_range_backup(json_path: Path, outdir: Path | None = None) -> dict:
    """Restore transcript from *.json.bak-range and rewrite sibling outputs."""
    json_path = Path(json_path)
    bak = range_backup_path(json_path)
    if not bak.exists():
        raise FileNotFoundError(f"找不到還原快照：{bak.name}")
    data = json.loads(bak.read_text(encoding="utf-8"))
    turns = data.get("turns") or []
    if not turns:
        raise ValueError("Backup has no turns")
    stem = media_stem(json_path)
    out_dir = Path(outdir) if outdir is not None else json_path.parent
    write_outputs(turns, out_dir, stem, data)
    meta_path = range_meta_path(json_path)
    if meta_path.exists():
        meta_path.unlink()
    print(f"[range] Restored from {bak.name} → {out_dir / (stem + '.json')}", flush=True)
    return {"ok": True, "stem": stem, "transcript": str(out_dir / f"{stem}.json"), "from": str(bak)}


def write_outputs(turns: list[dict], out_dir: Path, stem: str, raw: dict) -> None:
    print("Writing outputs ...", flush=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    md_lines = [
        f"# Transcript: {stem}",
        "",
        f"- Language: {raw.get('language', 'en')}",
        f"- Speakers: {len({t['speaker'] for t in turns})}",
        f"- Segments: {len(turns)}",
        f"- Bilingual: English + 中文翻譯",
        "",
        "---",
        "",
    ]
    txt_lines: list[str] = []
    srt_lines: list[str] = []
    srt_i = 1

    for turn in turns:
        start = turn["start"]
        end = turn["end"]
        speaker = turn["speaker"]
        text = ensure_sentence_punctuation(turn["text"])
        turn["text"] = text
        text_zh = (turn.get("text_zh") or "").strip()
        turn["text_zh"] = text_zh

        header = f"[{format_ts(start)} → {format_ts(end)}] {speaker}"
        md_lines.extend([f"### {header}", "", text, ""])
        if text_zh:
            md_lines.extend([text_zh, ""])

        txt_lines.extend([header, text])
        if text_zh:
            txt_lines.append(text_zh)
        txt_lines.append("")

        srt_body = f"{speaker}: {text}"
        if text_zh:
            srt_body += f"\n{text_zh}"
        srt_lines.extend(
            [
                str(srt_i),
                f"{format_ts(start).replace('.', ',')} --> {format_ts(end).replace('.', ',')}",
                srt_body,
                "",
            ]
        )
        srt_i += 1

    (out_dir / f"{stem}.md").write_text("\n".join(md_lines).rstrip() + "\n", encoding="utf-8")
    (out_dir / f"{stem}.txt").write_text("\n".join(txt_lines).rstrip() + "\n", encoding="utf-8")
    (out_dir / f"{stem}.srt").write_text("\n".join(srt_lines).rstrip() + "\n", encoding="utf-8")

    payload = {
        "language": raw.get("language"),
        "bilingual": True,
        "text": raw.get("text"),
        "turns": [
            {
                "speaker": t["speaker"],
                "start": t["start"],
                "end": t["end"],
                "text": t["text"],
                "text_zh": t.get("text_zh") or "",
                "words": t.get("words") or [],
            }
            for t in turns
        ],
    }
    (out_dir / f"{stem}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="英聽君（yingtingjun）：select audio → English transcript + ZH + speakers/timestamps"
    )
    parser.add_argument(
        "audio",
        nargs="?",
        type=Path,
        default=None,
        help="Audio path (wav/m4a/mp3...). Omit to open a file picker.",
    )
    parser.add_argument("--pick", action="store_true", help="Force file picker dialog")
    parser.add_argument(
        "--asr",
        choices=["auto", "mlx", "faster"],
        default="auto",
        help="ASR backend: auto (macOS→mlx, Windows/Linux→faster-whisper), mlx, or faster",
    )
    parser.add_argument(
        "--model",
        default=MLX_DEFAULT_MODEL,
        help="Whisper model id (MLX HF repo or faster-whisper name; auto-mapped by --asr)",
    )
    parser.add_argument("--min-speakers", type=int, default=2)
    parser.add_argument("--max-speakers", type=int, default=4)
    parser.add_argument(
        "--num-speakers",
        type=int,
        default=None,
        metavar="N",
        help="Force exactly N speakers (overrides min/max; uses ECAPA)",
    )
    parser.add_argument(
        "--estimate-speakers-only",
        action="store_true",
        help="Only estimate speaker count via ECAPA (no ASR/translate); print N and exit",
    )
    parser.add_argument(
        "--diarizer",
        choices=["auto", "speakrs", "ecapa"],
        default="auto",
        help="Speaker diarization backend (default: auto → speakrs, else ECAPA)",
    )
    parser.add_argument(
        "--speakrs-mode",
        choices=["coreml", "coreml-fast", "cpu"],
        default="coreml",
        help="speakrs execution mode (macOS default: coreml)",
    )
    parser.add_argument(
        "--speakrs-models-dir",
        type=Path,
        default=None,
        help="Optional local speakrs models directory (otherwise download/cache)",
    )
    parser.add_argument("--outdir", type=Path, default=Path("output"))
    parser.add_argument("--workdir", type=Path, default=Path("workdir"))
    parser.add_argument(
        "--whisper-json",
        type=Path,
        default=None,
        help="Reuse a previous Whisper JSON and skip ASR",
    )
    parser.add_argument(
        "--from-json",
        type=Path,
        default=None,
        help="Reuse an existing turns JSON (only translate / rewrite outputs)",
    )
    parser.add_argument(
        "--retranscribe-range",
        nargs=2,
        type=float,
        metavar=("START", "END"),
        default=None,
        help="With --from-json: re-ASR + re-translate only [START,END] seconds (keeps .bak-range)",
    )
    parser.add_argument(
        "--restore-range",
        action="store_true",
        help="With --from-json: restore transcript from *.json.bak-range",
    )
    parser.add_argument(
        "--range-padding",
        type=float,
        default=0.75,
        help="Seconds of audio padding around --retranscribe-range (default: 0.75)",
    )
    parser.add_argument(
        "--skip-translate",
        action="store_true",
        help="Skip Chinese translation",
    )
    parser.add_argument(
        "--scrub-zh",
        action="store_true",
        help=(
            "With --from-json: scrub NLLB 樓盤 hallucinations and map Yeah/Mm-hmm via glossary; "
            "retranslate only contaminated turns (use --skip-translate to scrub without NLLB)"
        ),
    )
    parser.add_argument(
        "--max-sentences",
        type=int,
        default=3,
        help="Split long speaker turns to at most N sentences each (default: 3)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Continue even if detected language is not English",
    )
    args = parser.parse_args()

    if args.num_speakers is not None and args.num_speakers < 1:
        print("--num-speakers must be >= 1", file=sys.stderr)
        return 1
    if args.num_speakers is not None and args.estimate_speakers_only:
        print(
            "--num-speakers 與 --estimate-speakers-only 不可同時使用"
            "（估人數請用 --min-speakers/--max-speakers 限定範圍）。",
            file=sys.stderr,
        )
        return 1
    if args.retranscribe_range and args.restore_range:
        print("--retranscribe-range 與 --restore-range 不可同時使用", file=sys.stderr)
        return 1
    if (args.retranscribe_range or args.restore_range) and not args.from_json:
        print("--retranscribe-range / --restore-range 需要搭配 --from-json", file=sys.stderr)
        return 1
    if args.from_json and (args.num_speakers is not None or args.estimate_speakers_only):
        print(
            "--from-json 不會重跑話者區分；"
            "請勿搭配 --num-speakers / --estimate-speakers-only。"
            "若要重分說話人，請對音檔重新轉寫（可加 --whisper-json 跳過 ASR）。",
            file=sys.stderr,
        )
        return 1

    force_num_speakers = False
    if args.num_speakers is not None:
        force_num_speakers = True
        args.min_speakers = args.num_speakers
        args.max_speakers = args.num_speakers
        if args.diarizer != "ecapa":
            print(
                f"       --num-speakers={args.num_speakers} → diarizer=ecapa",
                flush=True,
            )
            args.diarizer = "ecapa"

    # Fast path: translate existing structured transcript.
    if args.from_json:
        if args.restore_range:
            try:
                restore_range_backup(args.from_json, outdir=args.outdir)
            except Exception as exc:  # noqa: BLE001
                print(f"還原失敗：{exc}", file=sys.stderr)
                return 1
            print(f"\nDone. Restored bilingual outputs in {args.outdir.resolve()}/")
            return 0
        if args.retranscribe_range:
            start_s, end_s = args.retranscribe_range
            asr_name, args.model = configure_asr(args.asr, args.model)
            print(f"       ASR backend={asr_name} model={args.model}", flush=True)
            try:
                retranscribe_time_range(
                    args.from_json,
                    start=float(start_s),
                    end=float(end_s),
                    audio_path=args.audio,
                    workdir=args.workdir,
                    outdir=args.outdir,
                    model=args.model,
                    padding=args.range_padding,
                    max_sentences=args.max_sentences,
                    skip_translate=args.skip_translate,
                )
            except Exception as exc:  # noqa: BLE001
                print(f"局部重辨失敗：{exc}", file=sys.stderr)
                return 1
            print(f"\nDone. Updated bilingual outputs in {args.outdir.resolve()}/")
            return 0

        data = json.loads(args.from_json.read_text(encoding="utf-8"))
        turns = data.get("turns") or []
        if not turns:
            print("No turns in JSON", file=sys.stderr)
            return 1
        for t in turns:
            t["text"] = ensure_sentence_punctuation(t.get("text") or "")
        before = len(turns)
        turns = split_turns_by_max_sentences(turns, max_sentences=args.max_sentences)
        if len(turns) != before:
            print(
                f"       Split turns by max {args.max_sentences} sentences: "
                f"{before} → {len(turns)}",
                flush=True,
            )
        if args.scrub_zh:
            retranslate = not args.skip_translate
            contaminated = sum(
                1
                for t in turns
                if "樓盤" in (t.get("text_zh") or "")
                or zh_still_hallucinated(t.get("text_zh") or "")
                or try_glossary_translate(t.get("text") or "") is not None
            )
            print(
                f"       Scrubbing ZH hallucinations "
                f"(candidates≈{contaminated}, retranslate={retranslate}) ...",
                flush=True,
            )
            if retranslate and contaminated:
                try:
                    get_translator()
                except Exception as exc:  # noqa: BLE001
                    print(f"       Translator unavailable ({exc}); scrub-only.", flush=True)
                    retranslate = False
            changed = 0
            for i, t in enumerate(turns, start=1):
                if rescrub_turn_zh(t, retranslate_if_needed=retranslate):
                    changed += 1
                if i == 1 or i % 25 == 0 or i == len(turns):
                    print(f"       scrubbed {i}/{len(turns)} (changed={changed})", flush=True)
            left = sum(1 for t in turns if "樓盤" in (t.get("text_zh") or ""))
            print(f"       Done scrub: changed={changed}, remaining 樓盤={left}", flush=True)
        elif not args.skip_translate:
            # Re-translate after split so each short chunk gets its own ZH.
            for t in turns:
                t["text_zh"] = ""
            translate_turns(turns)
        stem = media_stem(args.from_json)
        write_outputs(turns, args.outdir, stem, data)
        print(f"\nDone. Updated bilingual outputs in {args.outdir.resolve()}/")
        return 0

    audio_path = args.audio
    if args.pick or audio_path is None:
        audio_path = pick_audio_file()
        if audio_path is None:
            print("未選擇錄音檔。", file=sys.stderr)
            return 1

    audio_path = Path(audio_path)
    if not audio_path.exists():
        print(f"Audio not found: {audio_path}", file=sys.stderr)
        return 1
    if audio_path.suffix.lower() not in AUDIO_SUFFIXES:
        print(f"警告：副檔名 {audio_path.suffix} 可能不受支援，仍嘗試處理…", flush=True)

    work_audio = ensure_work_wav(audio_path, args.workdir)
    audio, sr = load_audio_mono(work_audio, target_sr=16000)

    if args.estimate_speakers_only:
        n = estimate_num_speakers_ecapa(
            audio, sr, args.min_speakers, args.max_speakers
        )
        print(f"\nEstimated speakers: {n}")
        return 0

    stem = media_stem(audio_path)
    cache_path = args.outdir / f"{stem}.whisper.json"
    args.outdir.mkdir(parents=True, exist_ok=True)

    if args.whisper_json and args.whisper_json.exists():
        print(f"[2/4] Loading cached transcript {args.whisper_json} ...", flush=True)
        result = json.loads(args.whisper_json.read_text(encoding="utf-8"))
        lang = (result.get("language") or "en").lower()
    elif cache_path.exists():
        print(f"[2/4] Reusing cached Whisper result {cache_path.name} ...", flush=True)
        result = json.loads(cache_path.read_text(encoding="utf-8"))
        lang = (result.get("language") or "en").lower()
    else:
        asr_name, args.model = configure_asr(args.asr, args.model)
        print(f"       ASR backend={asr_name} model={args.model}", flush=True)
        lang = detect_language(audio, sr, args.model)
        if lang not in {"en", "english"} and not args.force:
            print(
                f"\n此錄音偵測為「{lang or 'unknown'}」，不是英文對話。\n"
                "依需求僅處理英文對話。若仍要強制處理，請加 --force。",
                file=sys.stderr,
            )
            return 2
        if lang not in {"en", "english"} and args.force:
            print(f"       --force：以英文流程繼續（偵測語種={lang})", flush=True)

        result = transcribe(audio, args.model, language="en")
        result["language"] = "en"
        cache_path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        print(f"       Cached Whisper result → {cache_path}", flush=True)

    segments = result.get("segments") or []
    if not segments and result.get("text"):
        segments = [{"start": 0.0, "end": 0.0, "text": result["text"], "words": []}]

    # Load translator BEFORE speechbrain diarization to avoid LazyModule/linecache clash.
    # (Only needed when ECAPA fallback may run.)
    if not args.skip_translate:
        try:
            get_translator()
        except Exception as exc:  # noqa: BLE001
            print(f"       Preload translator failed ({exc}); will retry later.", flush=True)

    words = collect_words(segments)
    turns = diarize_words(
        words,
        audio,
        sr,
        args.min_speakers,
        args.max_speakers,
        wav_path=work_audio,
        diarizer=args.diarizer,
        speakrs_mode=args.speakrs_mode,
        speakrs_models_dir=args.speakrs_models_dir,
        force_num_speakers=force_num_speakers,
    )
    for t in turns:
        t["text"] = ensure_sentence_punctuation(t.get("text") or "")

    before = len(turns)
    turns = split_turns_by_max_sentences(turns, max_sentences=args.max_sentences)
    if len(turns) != before:
        print(
            f"       Split turns by max {args.max_sentences} sentences: "
            f"{before} → {len(turns)}",
            flush=True,
        )

    # Persist diarized turns before translation so a later crash can resume.
    turns_cache = args.outdir / f"{stem}.turns.json"
    turns_cache.write_text(
        json.dumps({"language": result.get("language", "en"), "turns": turns}, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"       Cached diarized turns → {turns_cache}", flush=True)

    if not args.skip_translate:
        translate_turns(turns)
    else:
        for t in turns:
            t["text_zh"] = t.get("text_zh") or ""

    write_outputs(turns, args.outdir, stem, result)

    speakers = sorted({t["speaker"] for t in turns})
    print(f"\nDone. Files written to {args.outdir.resolve()}/")
    print(f"  Speakers: {', '.join(speakers)} | Turns: {len(turns)}")
    print(f"  - {stem}.md / .txt / .srt / .json  (英文 + 下一行中文)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
