"""Background import job manager (single active job)."""

from __future__ import annotations

import queue
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from yt_decoder.constants import DEFAULT_MAX_DURATION_SEC
from yt_decoder.errors import ProbeError
from yt_decoder.import_video import run_import
from yt_decoder.io_util import set_log_hook
from yt_decoder.types import ImportOptions
from yt_decoder.util import UrlError, normalize_youtube_url


@dataclass
class JobState:
    id: str
    status: str = "queued"  # queued | running | done | error
    url: str = ""
    events: queue.Queue = field(default_factory=queue.Queue)
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None


class JobManager:
    """At most one import job at a time."""

    def __init__(self, *, outdir: Path, yingtingjun_root: Path | None = None) -> None:
        self.outdir = outdir
        self.yingtingjun_root = yingtingjun_root
        self._lock = threading.Lock()
        self._current: JobState | None = None

    def busy(self) -> bool:
        with self._lock:
            return self._current is not None and self._current.status in {"queued", "running"}

    def get(self, job_id: str) -> JobState | None:
        with self._lock:
            if self._current and self._current.id == job_id:
                return self._current
            return None

    def start(
        self,
        url: str,
        *,
        mode: str = "auto",
        skip_translate: bool = False,
        max_duration_sec: int = DEFAULT_MAX_DURATION_SEC,
    ) -> JobState:
        with self._lock:
            if self._current is not None and self._current.status in {"queued", "running"}:
                raise RuntimeError("busy")
            try:
                normalized = normalize_youtube_url(url)
            except UrlError as exc:
                raise ValueError(str(exc)) from exc

            job = JobState(id=uuid.uuid4().hex[:12], url=normalized, status="queued")
            self._current = job

        thread = threading.Thread(
            target=self._run_job,
            args=(job, mode, skip_translate, max_duration_sec),
            daemon=True,
        )
        thread.start()
        return job

    def _emit(self, job: JobState, event: dict[str, Any]) -> None:
        job.events.put(event)

    def _run_job(
        self,
        job: JobState,
        mode: str,
        skip_translate: bool,
        max_duration_sec: int,
    ) -> None:
        job.status = "running"
        self._emit(job, {"type": "status", "status": "running", "url": job.url})

        def hook(stage: str, message: str) -> None:
            self._emit(job, {"type": "log", "stage": stage, "message": message})

        set_log_hook(hook)
        try:
            options = ImportOptions.from_data_root(
                self.outdir,
                mode=mode,
                skip_translate=skip_translate,
                max_duration_sec=max_duration_sec,
                yingtingjun_root=self.yingtingjun_root,
            )
            result = run_import(job.url, options)
            payload = {
                "stem": result.stem,
                "json_path": str(result.json_path),
                "audio_path": str(result.audio_path),
                "audio_name": result.audio_path.name,
                "caption_kind": result.caption_kind,
                "turns_count": result.turns_count,
                "hint": (
                    f"若英聽君已開啟，請先重新整理頁面（Cmd+R），"
                    f"再從下拉選單選擇：{result.audio_path.name}"
                ),
            }
            job.result = payload
            job.status = "done"
            self._emit(job, {"type": "done", **payload})
        except ProbeError as exc:
            job.error = {"code": exc.code, "message": str(exc)}
            job.status = "error"
            self._emit(job, {"type": "error", "code": exc.code, "message": str(exc)})
        except Exception as exc:  # noqa: BLE001
            job.error = {"code": "error", "message": str(exc)}
            job.status = "error"
            self._emit(job, {"type": "error", "code": "error", "message": str(exc)})
        finally:
            set_log_hook(None)
            self._emit(job, {"type": "end"})
