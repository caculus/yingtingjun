#!/usr/bin/env python3
"""Newline progress helpers (TTY tqdm + web player line reader both work)."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Callable


def log_line(msg: str, *, print_fn: Callable[..., None] = print) -> None:
    print_fn(f"       {msg}", flush=True)


@contextmanager
def heartbeat(
    start_msg: str,
    *,
    interval_sec: float = 15.0,
    print_fn: Callable[..., None] = print,
) -> Iterator[None]:
    """Print start_msg, then a waiting line every interval until the block exits."""
    log_line(start_msg, print_fn=print_fn)
    stop = threading.Event()

    def _beat() -> None:
        waited = 0
        step = max(1, int(interval_sec))
        while not stop.wait(interval_sec):
            waited += step
            log_line(f"…仍在進行（已等待 {waited}s）", print_fn=print_fn)

    thread = threading.Thread(target=_beat, name="ytj-heartbeat", daemon=True)
    thread.start()
    try:
        yield
    finally:
        stop.set()
        thread.join(timeout=0.2)


def asr_progress_pct(end_sec: float, duration_sec: float) -> int:
    if duration_sec <= 0:
        return 0
    return min(100, max(0, int(100.0 * float(end_sec) / float(duration_sec))))


def should_emit_progress(last_pct: int, pct: int, *, step: int = 5) -> bool:
    """Emit on first tick, every ``step`` percent, and at 100%."""
    if pct <= last_pct:
        return False
    if last_pct < 0:
        return True
    if pct >= 100:
        return True
    return pct // step > last_pct // step
