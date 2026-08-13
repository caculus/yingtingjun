"""Newline progress helpers used by ASR / player logs."""

import time

from progress_log import (
    asr_progress_pct,
    heartbeat,
    should_emit_progress,
)


def test_asr_progress_pct_bounds():
    assert asr_progress_pct(0, 100) == 0
    assert asr_progress_pct(50, 100) == 50
    assert asr_progress_pct(100, 100) == 100
    assert asr_progress_pct(120, 100) == 100
    assert asr_progress_pct(1, 0) == 0


def test_should_emit_progress_steps():
    assert should_emit_progress(-1, 0)
    assert should_emit_progress(0, 5)
    assert not should_emit_progress(5, 7)
    assert should_emit_progress(5, 10)
    assert should_emit_progress(95, 100)
    assert not should_emit_progress(100, 100)


def test_heartbeat_emits_waiting_lines():
    lines: list[str] = []

    def capture(*args, **kwargs):
        lines.append(str(args[0]) if args else "")

    with heartbeat("start", interval_sec=0.05, print_fn=capture):
        time.sleep(0.12)
    assert any("start" in ln for ln in lines)
    assert any("仍在進行" in ln for ln in lines)
