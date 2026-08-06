"""Unit tests for engine.runner (Story 4.3 multiprocessing + 4.4 backpressure).

Detectors are module-level functions so they are picklable across the 'spawn'
start method used on macOS.
"""

from __future__ import annotations

import os
import time

from engine.runner import EngineProcess, engine_frames_dropped_total


# --- picklable top-level detectors ---
def _double(x):
    return x * 2


def _slow_double(x):
    time.sleep(0.05)  # 50 ms — makes the engine the bottleneck
    return x * 2


def _wait_for_result(engine, timeout=8.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        results = engine.poll_results()
        if results:
            return results
        time.sleep(0.01)
    raise AssertionError("engine produced no result within timeout")


# ---------------------------------------------------------------------------
# 4.3 — process isolation
# ---------------------------------------------------------------------------

def test_engine_runs_in_separate_process():
    engine = EngineProcess(_double)
    engine.start()
    try:
        assert engine.pid is not None
        assert engine.pid != os.getpid()  # different PID than main
        engine.submit(21)
        assert 42 in _wait_for_result(engine)
    finally:
        engine.stop()


def test_clean_shutdown_no_zombie():
    engine = EngineProcess(_double)
    engine.start()
    assert engine.is_alive()
    engine.stop()
    assert not engine.is_alive()  # joined cleanly, no zombie


def test_bad_frame_does_not_kill_engine():
    # _double("x"*...) works, but a None * 2 -> TypeError; engine must survive it.
    engine = EngineProcess(_double)
    engine.start()
    try:
        engine.submit(None)   # None * 2 raises inside worker -> swallowed
        engine.submit(5)      # engine still alive, processes this
        assert 10 in _wait_for_result(engine)
        assert engine.is_alive()
    finally:
        engine.stop()


# ---------------------------------------------------------------------------
# 4.4 — backpressure / circuit breaker
# ---------------------------------------------------------------------------

def test_backpressure_drops_frames_when_engine_slow():
    before = engine_frames_dropped_total._value.get()
    engine = EngineProcess(_slow_double, max_queue=2)
    engine.start()
    try:
        for i in range(60):        # flood far faster than 50ms/frame worker
            engine.submit(i)
        after = engine_frames_dropped_total._value.get()
        assert after > before      # circuit breaker dropped overflow frames
    finally:
        engine.stop()


def test_submit_is_nonblocking_while_engine_busy():
    engine = EngineProcess(_slow_double, max_queue=5)
    engine.start()
    try:
        start = time.perf_counter()
        for i in range(200):       # 200 submits; worker can only do ~20/s
            engine.submit(i)
        elapsed_ms = (time.perf_counter() - start) * 1000
        # Non-blocking submit: 200 puts must not wait on the slow engine.
        assert elapsed_ms < 500, f"submit blocked: {elapsed_ms:.1f}ms for 200 frames"
    finally:
        engine.stop()


def test_invalid_max_queue_raises():
    import pytest

    with pytest.raises(ValueError):
        EngineProcess(_double, max_queue=0)
