#!/usr/bin/env python3
"""Local sync player: audio + transcript highlight, import & switch recordings."""

from __future__ import annotations

import argparse
import cgi
import csv
import io
import json
import mimetypes
import os
import re
import sqlite3
import subprocess
import sys
import threading
import time
import uuid
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parent
PLAYER_DIR = ROOT / "player"


def resolve_venv_python() -> Path:
    unix = ROOT / ".venv" / "bin" / "python"
    windows = ROOT / ".venv" / "Scripts" / "python.exe"
    if unix.exists():
        return unix
    if windows.exists():
        return windows
    return Path(sys.executable)


VENV_PYTHON = resolve_venv_python()
TRANSCRIBE_PY = ROOT / "transcribe.py"
DICT_API_URL = "https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
ECDICT_DB_DEFAULT = ROOT / "models" / "ecdict.db"
_DICT_QUERY_RE = re.compile(r"^[a-z]+(?:'[a-z]+)?(?:-[a-z]+)*$")
_ecdict_conn: sqlite3.Connection | None = None
_ecdict_lock = threading.Lock()


def normalize_dict_query(q: str) -> str | None:
    """Single English lemma only (v1). Reject phrases / empty."""
    raw = (q or "").strip()
    if not raw or any(ch.isspace() for ch in raw):
        return None
    cleaned = re.sub(r"^[^A-Za-z']+|[^A-Za-z']+$", "", raw)
    cleaned = cleaned.replace("\u2019", "'").lower().strip("'")
    if not cleaned or not _DICT_QUERY_RE.fullmatch(cleaned):
        return None
    return cleaned


def lemma_lookup_variants(lemma: str) -> list[str]:
    """Exact form first, then light morphology fallbacks for ECDICT."""
    out: list[str] = []
    seen: set[str] = set()

    def add(w: str) -> None:
        w = (w or "").strip().lower()
        if not w or w in seen or not _DICT_QUERY_RE.fullmatch(w):
            return
        seen.add(w)
        out.append(w)

    add(lemma)
    if lemma.endswith("ies") and len(lemma) > 4:
        add(lemma[:-3] + "y")
    if lemma.endswith("ing") and len(lemma) > 5:
        stem = lemma[:-3]
        add(stem)
        add(stem + "e")
        if len(stem) >= 2 and stem[-1] == stem[-2]:
            add(stem[:-1])
    if lemma.endswith("ed") and len(lemma) > 4:
        stem = lemma[:-2]
        add(stem)
        add(stem + "e")
        if len(stem) >= 2 and stem[-1] == stem[-2]:
            add(stem[:-1])
    if lemma.endswith("es") and len(lemma) > 3:
        add(lemma[:-2])
        add(lemma[:-1])
    elif lemma.endswith("s") and len(lemma) > 3 and not lemma.endswith("ss"):
        add(lemma[:-1])
    return out


def split_dict_lines(text: str) -> list[str]:
    raw = (text or "").replace("\\n", "\n").strip()
    if not raw:
        return []
    return [ln.strip() for ln in re.split(r"[\r\n]+", raw) if ln.strip()]


def compact_ecdict_row(query_lemma: str, row: sqlite3.Row) -> dict | None:
    translation = (row["translation"] or "").strip() if row["translation"] else ""
    if not translation:
        return None
    phonetic = (row["phonetic"] or "").strip() if row["phonetic"] else ""
    pos_field = (row["pos"] or "").strip() if row["pos"] else ""
    primary_pos = ""
    if pos_field:
        primary_pos = pos_field.split("/")[0].split(":")[0].strip()

    senses: list[dict] = []
    for line in split_dict_lines(translation)[:6]:
        pos = primary_pos
        text = line
        m = re.match(r"^([a-z]{1,5}\.?)\s+(.*)$", line, flags=re.I)
        if m and m.group(2).strip():
            pos = m.group(1).rstrip(".")
            text = m.group(2).strip()
        senses.append({"pos": pos, "zh": text, "en": "", "example": ""})
    if not senses:
        return None

    definition = (row["definition"] or "").strip() if row["definition"] else ""
    en_lines = split_dict_lines(definition)
    if en_lines:
        senses[0]["en"] = en_lines[0][:240]

    headword = (row["word"] or query_lemma or "").strip()
    return {
        "lemma": headword or query_lemma,
        "phonetic": phonetic,
        "senses": senses,
        "source": "ecdict",
    }


def resolve_ecdict_path() -> Path | None:
    env = (os.environ.get("ECDICT_DB") or "").strip()
    path = Path(env).expanduser() if env else ECDICT_DB_DEFAULT
    return path if path.exists() else None


def get_ecdict_conn() -> sqlite3.Connection | None:
    global _ecdict_conn
    path = resolve_ecdict_path()
    if path is None:
        return None
    with _ecdict_lock:
        if _ecdict_conn is not None:
            return _ecdict_conn
        try:
            conn = sqlite3.connect(
                f"file:{path}?mode=ro",
                uri=True,
                check_same_thread=False,
            )
            conn.row_factory = sqlite3.Row
            # Verify table exists
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='stardict'"
            ).fetchone()
            if not row:
                conn.close()
                return None
            _ecdict_conn = conn
            return _ecdict_conn
        except sqlite3.Error:
            return None


def lookup_ecdict(lemma: str) -> dict | None:
    conn = get_ecdict_conn()
    if conn is None:
        return None
    sql = (
        "SELECT word, phonetic, definition, translation, pos "
        "FROM stardict WHERE word = ? COLLATE NOCASE LIMIT 1"
    )
    try:
        with _ecdict_lock:
            for candidate in lemma_lookup_variants(lemma):
                row = conn.execute(sql, (candidate,)).fetchone()
                if row is None:
                    continue
                compact = compact_ecdict_row(lemma, row)
                if compact:
                    return compact
    except sqlite3.Error:
        return None
    return None


def compact_lemma_entry(dict_payload: dict | None, fallback_word: str = "") -> dict | None:
    """Normalize one saved vocab item for note.lemmas."""
    src = dict_payload if isinstance(dict_payload, dict) else {}
    lemma = (src.get("lemma") or fallback_word or "").strip()
    if not lemma:
        return None
    senses = src.get("senses") if isinstance(src.get("senses"), list) else []
    return {
        "lemma": lemma,
        "phonetic": (src.get("phonetic") or "").strip(),
        "senses": senses,
        "source": (src.get("source") or "").strip(),
    }


def note_lemmas_list(note: dict) -> list[dict]:
    out: list[dict] = []
    seen: set[str] = set()
    raw = note.get("lemmas") if isinstance(note, dict) else None
    if isinstance(raw, list):
        for item in raw:
            entry = compact_lemma_entry(item if isinstance(item, dict) else None)
            if not entry:
                continue
            key = entry["lemma"].lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(entry)
    if out:
        return out
    entry = compact_lemma_entry(
        note.get("dict") if isinstance(note.get("dict"), dict) else None,
        (note.get("word") or "").strip(),
    )
    return [entry] if entry else []


def merge_lemma_into_note(note: dict, dict_payload: dict | None, word: str = "") -> None:
    lemmas = note_lemmas_list(note)
    entry = compact_lemma_entry(dict_payload, word)
    if not entry:
        note["lemmas"] = lemmas
        return
    key = entry["lemma"].lower()
    replaced = False
    for i, existing in enumerate(lemmas):
        if (existing.get("lemma") or "").lower() == key:
            lemmas[i] = entry
            replaced = True
            break
    if not replaced:
        lemmas.append(entry)
    note["lemmas"] = lemmas
    note["word"] = entry["lemma"]
    note["dict"] = {
        "lemma": entry["lemma"],
        "phonetic": entry["phonetic"],
        "senses": entry["senses"],
        "source": entry["source"],
    }


def remove_lemma_from_note(note: dict, lemma: str) -> bool:
    key = (lemma or "").strip().lower()
    if not key:
        return False
    lemmas = note_lemmas_list(note)
    kept = [x for x in lemmas if (x.get("lemma") or "").lower() != key]
    if len(kept) == len(lemmas):
        return False
    note["lemmas"] = kept
    if kept:
        last = kept[-1]
        note["word"] = last.get("lemma") or ""
        note["dict"] = last
    else:
        note["word"] = ""
        note.pop("dict", None)
    return True


def compact_dictionary_entry(lemma: str, payload: list) -> dict:
    phonetic = ""
    senses: list[dict] = []
    for entry in payload:
        if not isinstance(entry, dict):
            continue
        if not phonetic:
            phonetic = (entry.get("phonetic") or "").strip()
            if not phonetic:
                for p in entry.get("phonetics") or []:
                    if isinstance(p, dict) and (p.get("text") or "").strip():
                        phonetic = p["text"].strip()
                        break
        for meaning in entry.get("meanings") or []:
            if not isinstance(meaning, dict):
                continue
            pos = (meaning.get("partOfSpeech") or "").strip()
            for d in meaning.get("definitions") or []:
                if not isinstance(d, dict):
                    continue
                en = (d.get("definition") or "").strip()
                if not en:
                    continue
                senses.append(
                    {
                        "pos": pos,
                        "zh": "",
                        "en": en,
                        "example": (d.get("example") or "").strip(),
                    }
                )
                if len(senses) >= 6:
                    break
            if len(senses) >= 6:
                break
        if len(senses) >= 6:
            break
    return {
        "lemma": lemma,
        "phonetic": phonetic,
        "senses": senses,
        "source": "free-dictionary",
    }


def media_stem(path: Path) -> str:
    """meeting.work.wav → meeting"""
    name = path.name
    if name.endswith(".work.wav"):
        return name[: -len(".work.wav")]
    return path.stem


def find_transcript_for_stem(outdir: Path, stem: str) -> Path | None:
    candidates = [
        outdir / f"{stem}.json",
        outdir / f"{stem}.work.json",
    ]
    for path in candidates:
        if not path.exists():
            continue
        if path.name.endswith(".whisper.json") or path.name.endswith(".turns.json"):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and data.get("turns"):
            return path
    # Fuzzy: any json whose stem matches after stripping suffixes
    for path in sorted(outdir.glob("*.json")):
        if path.name.endswith(".whisper.json") or path.name.endswith(".turns.json"):
            continue
        if media_stem(path) == stem or path.stem == stem:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict) and data.get("turns"):
                return path
    return None


def find_transcript(output_dir: Path) -> Path | None:
    jsons = sorted(output_dir.glob("*.json"))
    jsons = [
        p
        for p in jsons
        if not p.name.endswith(".whisper.json") and not p.name.endswith(".turns.json")
    ]
    for path in jsons:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and data.get("turns"):
            return path
    return None


def find_audio(root: Path, workdir: Path) -> Path | None:
    """Prefer workdir wavs. Ignore leftover root recording.wav (old default copy)."""
    if workdir.exists():
        wavs = sorted(p for p in workdir.glob("*.wav") if p.is_file())
        if wavs:
            return wavs[0]
    for pattern in ("*.wav", "*.m4a", "*.mp3"):
        hits = sorted(
            p
            for p in root.glob(pattern)
            if p.is_file() and p.name != "recording.wav"
        )
        if hits:
            return hits[0]
    return None


class AppState:
    def __init__(
        self,
        audio: Path | None,
        transcript: Path | None,
        outdir: Path,
        workdir: Path,
        uploads: Path,
        notesdir: Path,
    ) -> None:
        self.audio = audio
        self.transcript = transcript
        self.outdir = outdir
        self.workdir = workdir
        self.uploads = uploads
        self.notesdir = notesdir
        self.lock = threading.Lock()
        self.job: dict | None = None

    def busy(self) -> bool:
        with self.lock:
            return bool(self.job and self.job.get("status") == "running")

    def job_snapshot(self) -> dict:
        with self.lock:
            if not self.job:
                return {"status": "idle", "logs": [], "message": ""}
            return dict(self.job)

    def append_log(self, line: str) -> None:
        with self.lock:
            if not self.job:
                return
            logs = list(self.job.get("logs") or [])
            logs.append(line.rstrip("\n"))
            # Keep last N lines for UI.
            self.job["logs"] = logs[-400:]

    def start_job(self, kind: str, source: Path, message: str) -> dict:
        with self.lock:
            if self.job and self.job.get("status") == "running":
                return {"ok": False, "error": "處理中，請稍候再試。"}
            self.job = {
                "status": "running",
                "kind": kind,
                "source": str(source),
                "message": message,
                "logs": [message],
                "returncode": None,
                "started_at": time.time(),
                "finished_at": None,
                "result_audio": None,
                "result_transcript": None,
            }
        thread = threading.Thread(
            target=self._run_transcribe, args=(source,), daemon=True
        )
        thread.start()
        return {"ok": True, "job": self.job_snapshot()}

    def start_retranscribe_range_job(self, start: float, end: float) -> dict:
        if self.busy():
            return {"ok": False, "error": "處理中，請稍候再試。"}
        if not self.transcript or not Path(self.transcript).exists():
            return {"ok": False, "error": "尚未載入文稿"}
        if not self.audio or not Path(self.audio).exists():
            return {"ok": False, "error": "尚未載入音檔"}
        try:
            start_f = float(start)
            end_f = float(end)
        except (TypeError, ValueError):
            return {"ok": False, "error": "起迄時間格式錯誤"}
        if end_f <= start_f:
            return {"ok": False, "error": "終點必須大於起點"}
        if end_f - start_f > 180:
            return {"ok": False, "error": "第一版限制單次最多 180 秒，請縮小範圍"}

        transcript = Path(self.transcript)
        audio = Path(self.audio)
        msg = f"局部重辨 {start_f:.1f}s → {end_f:.1f}s …"
        with self.lock:
            if self.job and self.job.get("status") == "running":
                return {"ok": False, "error": "處理中，請稍候再試。"}
            self.job = {
                "status": "running",
                "kind": "retranscribe-range",
                "source": str(transcript),
                "message": msg,
                "logs": [msg],
                "returncode": None,
                "started_at": time.time(),
                "finished_at": None,
                "result_audio": str(audio),
                "result_transcript": str(transcript),
                "range_start": start_f,
                "range_end": end_f,
            }
        thread = threading.Thread(
            target=self._run_retranscribe_range,
            args=(transcript, audio, start_f, end_f),
            daemon=True,
        )
        thread.start()
        return {"ok": True, "job": self.job_snapshot()}

    def restore_retranscribe_range(self) -> dict:
        if self.busy():
            return {"ok": False, "error": "處理中，請稍候再試。"}
        if not self.transcript or not Path(self.transcript).exists():
            return {"ok": False, "error": "尚未載入文稿"}
        transcript = Path(self.transcript)
        bak = Path(str(transcript) + ".bak-range")
        if not bak.exists():
            return {"ok": False, "error": f"找不到還原快照：{bak.name}"}

        py = str(VENV_PYTHON if VENV_PYTHON.exists() else sys.executable)
        cmd = [
            py,
            str(TRANSCRIBE_PY),
            "--from-json",
            str(transcript),
            "--outdir",
            str(self.outdir),
            "--workdir",
            str(self.workdir),
            "--restore-range",
        ]
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                check=False,
            )
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"還原失敗：{exc}"}
        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or "").strip() or f"exit={proc.returncode}"
            return {"ok": False, "error": f"還原失敗：{err}"}
        return {
            "ok": True,
            "message": "已還原上次局部重辨前的文稿",
            "has_range_backup": False,
        }

    def has_range_backup(self) -> bool:
        if not self.transcript:
            return False
        return Path(str(self.transcript) + ".bak-range").exists()

    def _run_retranscribe_range(
        self, transcript: Path, audio: Path, start: float, end: float
    ) -> None:
        py = str(VENV_PYTHON if VENV_PYTHON.exists() else sys.executable)
        cmd = [
            py,
            str(TRANSCRIBE_PY),
            "--from-json",
            str(transcript),
            str(audio),
            "--outdir",
            str(self.outdir),
            "--workdir",
            str(self.workdir),
            "--retranscribe-range",
            f"{start}",
            f"{end}",
        ]
        self.append_log(f"$ {' '.join(cmd)}")
        final_message = None
        try:
            proc = subprocess.Popen(
                cmd,
                cwd=str(ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            assert proc.stdout is not None
            for line in proc.stdout:
                self.append_log(line)
            code = proc.wait()
        except Exception as exc:  # noqa: BLE001
            self.append_log(f"ERROR: {exc}")
            with self.lock:
                if self.job:
                    self.job["status"] = "error"
                    self.job["returncode"] = 1
                    self.job["finished_at"] = time.time()
                    self.job["message"] = f"局部重辨失敗：{exc}"
            return

        with self.lock:
            if not self.job:
                return
            self.job["returncode"] = code
            self.job["finished_at"] = time.time()
            if code == 0 and Path(transcript).exists():
                self.transcript = transcript
                if Path(audio).exists():
                    self.audio = audio
                self.job["status"] = "done"
                self.job["result_audio"] = str(self.audio) if self.audio else None
                self.job["result_transcript"] = str(transcript)
                final_message = "局部重辨完成，已重新載入文稿。"
                self.job["message"] = final_message
            else:
                self.job["status"] = "error"
                final_message = f"局部重辨失敗（exit={code}）。"
                self.job["message"] = final_message
        if final_message:
            self.append_log(final_message)

    def _run_transcribe(self, source: Path) -> None:
        py = str(VENV_PYTHON if VENV_PYTHON.exists() else sys.executable)
        cmd = [py, str(TRANSCRIBE_PY), str(source)]
        self.append_log(f"$ {' '.join(cmd)}")
        final_message = None
        try:
            proc = subprocess.Popen(
                cmd,
                cwd=str(ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            assert proc.stdout is not None
            for line in proc.stdout:
                self.append_log(line)
            code = proc.wait()
        except Exception as exc:  # noqa: BLE001
            self.append_log(f"ERROR: {exc}")
            with self.lock:
                if self.job:
                    self.job["status"] = "error"
                    self.job["returncode"] = 1
                    self.job["finished_at"] = time.time()
                    self.job["message"] = f"轉寫失敗：{exc}"
            return

        stem = media_stem(source)
        # Prefer workdir wav produced by transcribe.
        result_audio = self.workdir / f"{stem}.work.wav"
        if not result_audio.exists():
            # Fallback: source itself if already wav in workdir
            if source.exists():
                result_audio = source
        result_transcript = find_transcript_for_stem(self.outdir, stem)

        with self.lock:
            if not self.job:
                return
            self.job["returncode"] = code
            self.job["finished_at"] = time.time()
            if code == 0 and result_transcript and result_audio.exists():
                self.audio = result_audio
                self.transcript = result_transcript
                self.job["status"] = "done"
                self.job["result_audio"] = str(result_audio)
                self.job["result_transcript"] = str(result_transcript)
                final_message = "轉寫完成，已自動載入。"
                self.job["message"] = final_message
            else:
                self.job["status"] = "error"
                final_message = (
                    f"轉寫結束但找不到完整輸出（code={code}）。"
                    if code == 0
                    else f"轉寫失敗（exit={code}）。"
                )
                self.job["message"] = final_message
        if final_message:
            self.append_log(final_message)

    def list_workdir(self) -> list[dict]:
        self.workdir.mkdir(parents=True, exist_ok=True)
        items = []
        for path in sorted(self.workdir.iterdir(), key=lambda p: p.name.lower()):
            if not path.is_file():
                continue
            stem = media_stem(path)
            transcript = find_transcript_for_stem(self.outdir, stem)
            items.append(
                {
                    "name": path.name,
                    "stem": stem,
                    "path": str(path),
                    "has_transcript": transcript is not None,
                    "transcript_name": transcript.name if transcript else None,
                    "selected": bool(
                        self.audio and path.resolve() == Path(self.audio).resolve()
                    ),
                }
            )
        return items

    def select_workdir_file(self, name: str) -> dict:
        if self.busy():
            return {"ok": False, "error": "處理中，請稍候再試。"}
        target = (self.workdir / name).resolve()
        if not target.exists() or not target.is_file():
            return {"ok": False, "error": f"找不到檔案：{name}"}
        # Prevent path escape
        try:
            target.relative_to(self.workdir.resolve())
        except ValueError:
            return {"ok": False, "error": "非法路徑"}

        stem = media_stem(target)
        transcript = find_transcript_for_stem(self.outdir, stem)
        if transcript is None:
            msg = f"「{name}」尚未匯入過（找不到對應文稿），開始執行轉寫…"
            started = self.start_job("select-import", target, msg)
            if not started.get("ok"):
                return started
            return {
                "ok": True,
                "started_job": True,
                "message": msg,
                "job": self.job_snapshot(),
            }

        with self.lock:
            self.audio = target
            self.transcript = transcript
        return {
            "ok": True,
            "started_job": False,
            "message": f"已切換：{target.name} + {transcript.name}",
            "meta": self.meta(),
        }

    def _same_stem(self, path: Path, stem: str) -> bool:
        return media_stem(path) == stem or path.stem == stem or path.name.startswith(stem + ".")

    def delete_workdir_file(self, name: str) -> dict:
        if self.busy():
            return {"ok": False, "error": "處理中，請稍候再試。"}
        target = (self.workdir / name).resolve()
        if not target.exists() or not target.is_file():
            return {"ok": False, "error": f"找不到檔案：{name}"}
        try:
            target.relative_to(self.workdir.resolve())
        except ValueError:
            return {"ok": False, "error": "非法路徑"}

        stem = media_stem(target)
        deleted: list[str] = []

        def _unlink(path: Path) -> None:
            if not path.is_file():
                return
            # Never touch shared root recording.wav
            if path.resolve() == (ROOT / "recording.wav").resolve():
                return
            try:
                path.unlink()
                try:
                    rel = str(path.relative_to(ROOT))
                except ValueError:
                    rel = str(path)
                deleted.append(rel)
            except OSError as exc:
                deleted.append(f"{path.name}（刪除失敗：{exc}）")

        for path in list(self.workdir.iterdir()):
            if path.is_file() and self._same_stem(path, stem):
                _unlink(path)

        if self.outdir.exists():
            for path in list(self.outdir.iterdir()):
                if path.is_file() and self._same_stem(path, stem):
                    _unlink(path)

        if self.uploads.exists():
            for path in list(self.uploads.iterdir()):
                if path.is_file() and self._same_stem(path, stem):
                    _unlink(path)

        notes_path = self.notes_path_for_stem(stem)
        if notes_path.exists():
            _unlink(notes_path)

        cleared = False
        with self.lock:
            audio_match = bool(
                self.audio and self._same_stem(Path(self.audio), stem)
            )
            transcript_match = bool(
                self.transcript and self._same_stem(Path(self.transcript), stem)
            )
            if audio_match or transcript_match:
                self.audio = None
                self.transcript = None
                cleared = True

        return {
            "ok": True,
            "cleared": cleared,
            "stem": stem,
            "deleted": deleted,
            "message": f"已刪除「{stem}」相關檔案（{len(deleted)} 個）",
        }

    def current_stem(self) -> str | None:
        if self.transcript and Path(self.transcript).exists():
            return media_stem(Path(self.transcript))
        if self.audio and Path(self.audio).exists():
            return media_stem(Path(self.audio))
        return None

    def notes_path_for_stem(self, stem: str) -> Path:
        safe = Path(stem).name
        return self.notesdir / f"{safe}.json"

    def load_notes(self, stem: str | None = None) -> dict:
        stem = stem or self.current_stem()
        if not stem:
            return {"stem": "", "notes": []}
        path = self.notes_path_for_stem(stem)
        if not path.exists():
            return {"stem": stem, "notes": []}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"stem": stem, "notes": []}
        notes = data.get("notes") if isinstance(data, dict) else None
        if not isinstance(notes, list):
            notes = []
        return {"stem": stem, "notes": notes}

    def save_notes_doc(self, stem: str, notes: list[dict]) -> Path:
        self.notesdir.mkdir(parents=True, exist_ok=True)
        path = self.notes_path_for_stem(stem)
        payload = {"stem": stem, "notes": notes, "updated_at": time.time()}
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def add_note(self, body: dict) -> dict:
        stem = (body.get("stem") or self.current_stem() or "").strip()
        if not stem:
            return {"ok": False, "error": "尚未載入錄音，無法存筆記"}
        text_en = (body.get("text_en") or "").strip()
        text_zh = (body.get("text_zh") or "").strip()
        if not text_en and not text_zh:
            return {"ok": False, "error": "請至少填寫英文句或中譯"}

        start = body.get("start")
        end = body.get("end")
        try:
            start_f = float(start) if start is not None and start != "" else None
        except (TypeError, ValueError):
            start_f = None
        try:
            end_f = float(end) if end is not None and end != "" else None
        except (TypeError, ValueError):
            end_f = None

        note_id = (body.get("id") or "").strip()
        doc = self.load_notes(stem)
        notes = list(doc.get("notes") or [])
        dict_payload = body.get("dict")
        if dict_payload is not None and not isinstance(dict_payload, dict):
            dict_payload = None
        word = (body.get("word") or "").strip()
        remove_lemma = (body.get("remove_lemma") or "").strip()

        # Update existing note when id is provided.
        if note_id:
            for note in notes:
                if note.get("id") != note_id:
                    continue
                note["text_en"] = text_en
                note["text_zh"] = text_zh
                note["start"] = start_f
                note["end"] = end_f
                if body.get("source"):
                    note["source"] = str(body.get("source")).strip() or note.get("source") or "manual"
                if remove_lemma:
                    if not remove_lemma_from_note(note, remove_lemma):
                        return {"ok": False, "error": f"此則沒有生字「{remove_lemma}」"}
                elif "dict" in body:
                    merge_lemma_into_note(note, dict_payload, word)
                elif "word" in body:
                    note["word"] = word
                    if not note.get("lemmas"):
                        note["lemmas"] = note_lemmas_list(note)
                else:
                    note["word"] = word or (note.get("word") or "")
                    if not note.get("lemmas"):
                        note["lemmas"] = note_lemmas_list(note)
                note["updated_at"] = time.time()
                notes.sort(
                    key=lambda n: (
                        n.get("start") is None,
                        n.get("start") or 0,
                        n.get("created_at") or 0,
                    )
                )
                self.save_notes_doc(stem, notes)
                return {"ok": True, "note": note, "stem": stem, "notes": notes, "updated": True}
            return {"ok": False, "error": "找不到該筆記"}

        note = {
            "id": str(uuid.uuid4()),
            "word": word,
            "text_en": text_en,
            "text_zh": text_zh,
            "start": start_f,
            "end": end_f,
            "source": (body.get("source") or "manual").strip() or "manual",
            "created_at": time.time(),
            "lemmas": [],
        }
        if dict_payload or word:
            merge_lemma_into_note(note, dict_payload, word)
        notes.append(note)
        notes.sort(key=lambda n: (n.get("start") is None, n.get("start") or 0, n.get("created_at") or 0))
        self.save_notes_doc(stem, notes)
        return {"ok": True, "note": note, "stem": stem, "notes": notes, "updated": False}

    def dict_cache_path(self) -> Path:
        self.notesdir.mkdir(parents=True, exist_ok=True)
        return self.notesdir / "_dict_cache.json"

    def _load_dict_cache(self) -> dict:
        path = self.dict_cache_path()
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}

    def _save_dict_cache(self, cache: dict) -> None:
        path = self.dict_cache_path()
        path.write_text(json.dumps(cache, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def lookup_dictionary(self, query: str) -> dict:
        lemma = normalize_dict_query(query)
        if not lemma:
            return {
                "ok": False,
                "error": "請提供單一英文單字（第一版不支援片語）",
            }

        with self.lock:
            cache = self._load_dict_cache()
            hit = cache.get(lemma)
            if isinstance(hit, dict) and hit.get("lemma") and hit.get("senses"):
                # If we only cached EN gloss before ECDICT was installed, try upgrade.
                if hit.get("source") == "free-dictionary" and resolve_ecdict_path():
                    upgraded = lookup_ecdict(lemma)
                    if upgraded:
                        cache[lemma] = {
                            "lemma": upgraded.get("lemma") or lemma,
                            "phonetic": upgraded.get("phonetic") or "",
                            "senses": upgraded.get("senses") or [],
                            "source": upgraded.get("source") or "ecdict",
                        }
                        self._save_dict_cache(cache)
                        out = dict(upgraded)
                        out["ok"] = True
                        out["cached"] = False
                        return out
                out = dict(hit)
                out["ok"] = True
                out["cached"] = True
                return out

        # 1) ECDICT local EN→ZH
        compact = lookup_ecdict(lemma)

        # 2) Free Dictionary EN fallback
        if compact is None:
            url = DICT_API_URL.format(word=urllib.parse.quote(lemma))
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "yingtingjun-local-player/1.0",
                    "Accept": "application/json",
                },
                method="GET",
            )
            try:
                with urllib.request.urlopen(req, timeout=8) as resp:
                    raw = json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                if exc.code == 404:
                    return {"ok": False, "error": f"詞典沒有「{lemma}」", "lemma": lemma}
                return {
                    "ok": False,
                    "error": f"詞典查詢失敗（HTTP {exc.code}）",
                    "lemma": lemma,
                }
            except Exception as exc:  # noqa: BLE001
                return {"ok": False, "error": f"詞典查詢失敗：{exc}", "lemma": lemma}

            if not isinstance(raw, list) or not raw:
                return {"ok": False, "error": f"詞典沒有「{lemma}」", "lemma": lemma}

            compact = compact_dictionary_entry(lemma, raw)
            if not compact.get("senses"):
                return {
                    "ok": False,
                    "error": f"詞典沒有可用釋義：「{lemma}」",
                    "lemma": lemma,
                }

        with self.lock:
            cache = self._load_dict_cache()
            cache[lemma] = {
                "lemma": compact.get("lemma") or lemma,
                "phonetic": compact.get("phonetic") or "",
                "senses": compact.get("senses") or [],
                "source": compact.get("source") or "",
            }
            if len(cache) > 2000:
                for key in list(cache.keys())[: max(0, len(cache) - 2000)]:
                    cache.pop(key, None)
            self._save_dict_cache(cache)

        out = dict(compact)
        out["ok"] = True
        out["cached"] = False
        return out

    def delete_note(self, note_id: str, stem: str | None = None) -> dict:
        stem = (stem or self.current_stem() or "").strip()
        if not stem:
            return {"ok": False, "error": "尚未載入錄音"}
        if not note_id:
            return {"ok": False, "error": "缺少筆記 id"}
        doc = self.load_notes(stem)
        notes = [n for n in (doc.get("notes") or []) if n.get("id") != note_id]
        if len(notes) == len(doc.get("notes") or []):
            return {"ok": False, "error": "找不到該筆記"}
        self.save_notes_doc(stem, notes)
        return {"ok": True, "stem": stem, "notes": notes}

    def notes_csv(self, stem: str | None = None) -> tuple[str, str]:
        doc = self.load_notes(stem)
        stem = doc.get("stem") or "notes"
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(
            [
                "stem",
                "word",
                "text_en",
                "text_zh",
                "dict_lemma",
                "dict_gloss",
                "start",
                "end",
                "source",
                "created_at",
            ]
        )
        for n in doc.get("notes") or []:
            lemmas = note_lemmas_list(n)
            lemma_join = "; ".join((x.get("lemma") or "").strip() for x in lemmas if x.get("lemma"))
            glosses = []
            for item in lemmas:
                senses = item.get("senses") if isinstance(item.get("senses"), list) else []
                if senses and isinstance(senses[0], dict):
                    g = (senses[0].get("zh") or senses[0].get("en") or "").strip()
                    if g:
                        glosses.append(g)
            writer.writerow(
                [
                    stem,
                    n.get("word") or "",
                    n.get("text_en") or "",
                    n.get("text_zh") or "",
                    lemma_join,
                    " | ".join(glosses),
                    "" if n.get("start") is None else n.get("start"),
                    "" if n.get("end") is None else n.get("end"),
                    n.get("source") or "",
                    n.get("created_at") or "",
                ]
            )
        return f"{stem}.notes.csv", buf.getvalue()

    def meta(self) -> dict:
        audio = self.audio
        transcript = self.transcript
        stem = self.current_stem() or ""
        return {
            "title": transcript.stem if transcript else "（尚未載入文稿）",
            "stem": stem,
            "audio_url": "/audio",
            "transcript_url": "/api/transcript",
            "audio_name": audio.name if audio else "",
            "transcript_name": transcript.name if transcript else "",
            "has_audio": bool(audio and Path(audio).exists()),
            "has_transcript": bool(transcript and Path(transcript).exists()),
            "has_range_backup": self.has_range_backup(),
            "has_ecdict": resolve_ecdict_path() is not None,
            "busy": self.busy(),
        }


class PlayerHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, state: AppState, **kwargs):
        self.state = state
        super().__init__(*args, directory=str(PLAYER_DIR), **kwargs)

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))

    def _read_json_body(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            return json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return {}

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        if path in ("/", "/index.html"):
            return self._send_file(PLAYER_DIR / "index.html", "text/html; charset=utf-8")
        if path == "/api/meta":
            return self._send_json(self.state.meta())
        if path == "/api/library":
            return self._send_json({"files": self.state.list_workdir()})
        if path == "/api/job":
            return self._send_json(self.state.job_snapshot())
        if path == "/api/transcript":
            if not self.state.transcript or not Path(self.state.transcript).exists():
                return self._send_json({"error": "no transcript", "turns": []}, status=404)
            return self._send_file(self.state.transcript, "application/json; charset=utf-8")
        if path == "/api/notes":
            qs = parse_qs(parsed.query)
            stem = (qs.get("stem") or [None])[0]
            return self._send_json(self.state.load_notes(stem))
        if path == "/api/dict":
            qs = parse_qs(parsed.query)
            q = (qs.get("q") or [""])[0]
            result = self.state.lookup_dictionary(q)
            if result.get("ok"):
                status = 200
            elif "失敗" in (result.get("error") or ""):
                status = 502
            elif "片語" in (result.get("error") or "") or "單一" in (result.get("error") or ""):
                status = 400
            else:
                status = 404
            return self._send_json(result, status=status)
        if path == "/api/notes/export.csv":
            qs = parse_qs(parsed.query)
            stem = (qs.get("stem") or [None])[0]
            filename, csv_text = self.state.notes_csv(stem)
            body = csv_text.encode("utf-8-sig")
            self.send_response(200)
            self.send_header("Content-Type", "text/csv; charset=utf-8")
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self._safe_write(body)
            return
        if path == "/audio":
            if not self.state.audio or not Path(self.state.audio).exists():
                self.send_error(404, "No audio loaded")
                return
            mime, _ = mimetypes.guess_type(str(self.state.audio))
            return self._send_file(self.state.audio, mime or "audio/wav")
        return super().do_GET()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        if path == "/api/select":
            body = self._read_json_body()
            name = (body.get("name") or "").strip()
            if not name:
                return self._send_json({"ok": False, "error": "缺少檔名"}, status=400)
            result = self.state.select_workdir_file(name)
            status = 200 if result.get("ok") else 409 if "處理中" in (result.get("error") or "") else 400
            return self._send_json(result, status=status)

        if path == "/api/delete":
            body = self._read_json_body()
            name = (body.get("name") or "").strip()
            if not name:
                return self._send_json({"ok": False, "error": "缺少檔名"}, status=400)
            result = self.state.delete_workdir_file(name)
            status = 200 if result.get("ok") else 409 if "處理中" in (result.get("error") or "") else 400
            return self._send_json(result, status=status)

        if path == "/api/import":
            if self.state.busy():
                return self._send_json({"ok": False, "error": "處理中，請稍候再試。"}, status=409)
            try:
                saved = self._save_upload()
            except Exception as exc:  # noqa: BLE001
                return self._send_json({"ok": False, "error": f"上傳失敗：{exc}"}, status=400)
            msg = f"已匯入「{saved.name}」，開始執行轉寫…"
            started = self.state.start_job("import", saved, msg)
            status = 200 if started.get("ok") else 409
            return self._send_json(started, status=status)

        if path == "/api/notes":
            body = self._read_json_body()
            result = self.state.add_note(body)
            status = 200 if result.get("ok") else 400
            return self._send_json(result, status=status)

        if path == "/api/notes/delete":
            body = self._read_json_body()
            result = self.state.delete_note(
                (body.get("id") or "").strip(),
                (body.get("stem") or "").strip() or None,
            )
            status = 200 if result.get("ok") else 400
            return self._send_json(result, status=status)

        if path == "/api/translate":
            body = self._read_json_body()
            text = (body.get("text") or "").strip()
            if not text:
                return self._send_json({"ok": False, "error": "缺少 text"}, status=400)
            try:
                # Reuse the same local NLLB path as transcribe.py.
                from transcribe import translate_en_to_zh

                zh = translate_en_to_zh(text)
                return self._send_json({"ok": True, "text_en": text, "text_zh": zh})
            except Exception as exc:  # noqa: BLE001
                return self._send_json(
                    {"ok": False, "error": f"翻譯失敗：{exc}"}, status=500
                )

        if path == "/api/retranscribe-range":
            body = self._read_json_body()
            result = self.state.start_retranscribe_range_job(
                body.get("start"), body.get("end")
            )
            status = 200 if result.get("ok") else 400
            return self._send_json(result, status=status)

        if path == "/api/retranscribe-restore":
            result = self.state.restore_retranscribe_range()
            status = 200 if result.get("ok") else 400
            return self._send_json(result, status=status)

        self.send_error(404, "Unknown endpoint")

    def _save_upload(self) -> Path:
        ctype = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in ctype:
            raise ValueError("需要 multipart/form-data")
        environ = {
            "REQUEST_METHOD": "POST",
            "CONTENT_TYPE": ctype,
            "CONTENT_LENGTH": self.headers.get("Content-Length", "0"),
        }
        form = cgi.FieldStorage(
            fp=self.rfile, headers=self.headers, environ=environ, keep_blank_values=True
        )
        if "file" not in form:
            raise ValueError("缺少 file 欄位")
        field = form["file"]
        if isinstance(field, list):
            field = field[0]
        filename = Path(getattr(field, "filename", None) or "upload.bin").name
        if not filename or filename in {".", ".."}:
            raise ValueError("無效檔名")
        self.state.uploads.mkdir(parents=True, exist_ok=True)
        dest = self.state.uploads / filename
        # Avoid overwrite collisions
        if dest.exists():
            dest = self.state.uploads / f"{dest.stem}-{int(time.time())}{dest.suffix}"
        data = field.file.read()
        dest.write_bytes(data)
        return dest

    def _send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self._safe_write(body)

    def _safe_write(self, data: bytes) -> None:
        """Write body; ignore client disconnect (seek / reload / cancel)."""
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass
        except OSError as exc:
            # macOS / some stacks surface EPIPE as OSError errno 32
            if getattr(exc, "errno", None) in (32, 104):
                return
            raise

    def _parse_byte_range(self, size: int) -> tuple[int, int] | None:
        """Return inclusive (start, end) from Range header, or None for full body."""
        header = (self.headers.get("Range") or "").strip()
        if not header.lower().startswith("bytes=") or size <= 0:
            return None
        spec = header.split("=", 1)[1].strip()
        if "," in spec:
            # Multi-range not supported; fall back to full body.
            return None
        if "-" not in spec:
            return None
        start_s, end_s = spec.split("-", 1)
        try:
            if start_s == "":
                # suffix: bytes=-N
                suffix = int(end_s)
                if suffix <= 0:
                    return None
                start = max(0, size - suffix)
                end = size - 1
            else:
                start = int(start_s)
                end = int(end_s) if end_s else size - 1
        except ValueError:
            return None
        if start < 0 or start >= size:
            return None
        end = min(end, size - 1)
        if end < start:
            return None
        return start, end

    def _send_file(self, path: Path, content_type: str) -> None:
        if not path.exists():
            self.send_error(404, f"Missing {path.name}")
            return
        size = path.stat().st_size
        byte_range = self._parse_byte_range(size)

        try:
            if byte_range is None:
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(size))
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                with path.open("rb") as fh:
                    while True:
                        chunk = fh.read(1024 * 256)
                        if not chunk:
                            break
                        self._safe_write(chunk)
                return

            start, end = byte_range
            length = end - start + 1
            self.send_response(206)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(length))
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            with path.open("rb") as fh:
                fh.seek(start)
                remaining = length
                while remaining > 0:
                    chunk = fh.read(min(1024 * 256, remaining))
                    if not chunk:
                        break
                    self._safe_write(chunk)
                    remaining -= len(chunk)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            return
        except OSError as exc:
            if getattr(exc, "errno", None) in (32, 104):
                return
            raise


def main() -> int:
    parser = argparse.ArgumentParser(description="英聽君（yingtingjun）：sync player with highlight bar")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--outdir", type=Path, default=ROOT / "output")
    parser.add_argument("--workdir", type=Path, default=ROOT / "workdir")
    parser.add_argument("--uploads", type=Path, default=ROOT / "uploads")
    parser.add_argument("--notesdir", type=Path, default=ROOT / "notes")
    parser.add_argument("--audio", type=Path, default=None)
    parser.add_argument("--transcript", type=Path, default=None)
    parser.add_argument("--no-open", action="store_true")
    args = parser.parse_args()

    args.outdir.mkdir(parents=True, exist_ok=True)
    args.workdir.mkdir(parents=True, exist_ok=True)
    args.uploads.mkdir(parents=True, exist_ok=True)
    args.notesdir.mkdir(parents=True, exist_ok=True)

    transcript = args.transcript or find_transcript(args.outdir)
    audio = args.audio or find_audio(ROOT, args.workdir)
    if not PLAYER_DIR.joinpath("index.html").exists():
        print(f"Missing player UI: {PLAYER_DIR / 'index.html'}", file=sys.stderr)
        return 1

    state = AppState(
        audio=audio,
        transcript=transcript,
        outdir=args.outdir,
        workdir=args.workdir,
        uploads=args.uploads,
        notesdir=args.notesdir,
    )
    handler = partial(PlayerHandler, state=state)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler)
    url = f"http://127.0.0.1:{args.port}/"
    print(f"Transcript: {transcript.name if transcript else '(none)'}")
    print(f"Audio:      {audio.name if audio else '(none)'}")
    print(f"Open:       {url}")
    if not args.no_open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
