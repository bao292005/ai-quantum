"""Engine process wrapper + backpressure (Stories 4.3 / 4.4).

Runs a **detector callable in a separate process** (NFR3) so a CPU-bound engine
(e.g. the parked MPS forward pass) cannot block the asyncio ingest loop. Frames
are submitted over a **bounded queue**; when the engine falls behind, the oldest
frame is dropped (circuit breaker) and ``engine_frames_dropped_total`` is
incremented so end-to-end latency stays bounded (Story 4.4).

Detector-agnostic: any picklable top-level callable ``frame -> result`` works —
the v1 B0 detector (`engine.baseline.borrow_activity`) or, if un-parked, the MPS
`engine.mps.naive.fragility_raw_from_graph`. Under the 'spawn' start method
(macOS default) the detector is referenced by import path, so it must be a
module-level function, not a lambda/closure.
"""

from __future__ import annotations

import logging
import multiprocessing as mp
import queue
from typing import Any, Callable

from prometheus_client import Counter

logger = logging.getLogger(__name__)

engine_frames_dropped_total = Counter(
    "engine_frames_dropped_total",
    "Frames dropped by engine backpressure (input queue full).",
)

# Tagged queue messages so any frame payload (dict, list, str, tensor) is
# unambiguous vs the stop signal.
_FRAME = 0
_STOP = 1

Detector = Callable[[Any], Any]


def _worker(detector: Detector, in_q: mp.Queue, out_q: mp.Queue) -> None:
    """Engine loop: pull frames, run the detector, push results. Runs in a child
    process. A single bad frame must never kill the engine (failure mode F4)."""
    while True:
        tag, payload = in_q.get()
        if tag == _STOP:
            break
        try:
            out_q.put(detector(payload))
        except Exception:  # noqa: BLE001 — isolate per-frame failures
            logger.exception("engine detector raised on a frame; skipping")


class EngineProcess:
    """Supervises a detector running in a separate process with backpressure."""

    def __init__(self, detector: Detector, *, max_queue: int = 100) -> None:
        if max_queue < 1:
            raise ValueError(f"max_queue must be >= 1; got {max_queue}")
        self._detector = detector
        self._in: mp.Queue = mp.Queue(maxsize=max_queue)
        self._out: mp.Queue = mp.Queue()
        self._proc: mp.Process | None = None

    def start(self) -> None:
        self._proc = mp.Process(
            target=_worker, args=(self._detector, self._in, self._out), daemon=True
        )
        self._proc.start()

    @property
    def pid(self) -> int | None:
        return self._proc.pid if self._proc else None

    def is_alive(self) -> bool:
        return bool(self._proc and self._proc.is_alive())

    def submit(self, frame: Any) -> None:
        """Non-blocking submit with **drop-oldest** backpressure (Story 4.4).

        Keeps the freshest data: on a full queue, evict the oldest frame, count
        the drop, and enqueue the new one. Never blocks the caller (ingest loop).
        """
        try:
            self._in.put_nowait((_FRAME, frame))
            return
        except queue.Full:
            pass
        # Circuit breaker: make room by dropping the oldest frame.
        try:
            self._in.get_nowait()
        except queue.Empty:
            pass
        engine_frames_dropped_total.inc()
        logger.info("engine backpressure: dropped oldest frame (queue full)")
        try:
            self._in.put_nowait((_FRAME, frame))
        except queue.Full:
            # Worker refilled the slot instantly; drop the new frame too.
            engine_frames_dropped_total.inc()

    def poll_results(self) -> list[Any]:
        """Drain and return all currently available results (non-blocking)."""
        out: list[Any] = []
        while True:
            try:
                out.append(self._out.get_nowait())
            except queue.Empty:
                break
        return out

    def stop(self, timeout: float = 5.0) -> None:
        """Signal the engine to stop and join it cleanly (no zombie)."""
        if not self._proc:
            return
        try:
            self._in.put_nowait((_STOP, None))
        except queue.Full:
            try:
                self._in.get_nowait()
            except queue.Empty:
                pass
            try:
                self._in.put_nowait((_STOP, None))
            except queue.Full:
                pass
        self._proc.join(timeout)
        if self._proc.is_alive():
            self._proc.terminate()
            self._proc.join(timeout)
        self._proc = None


__all__ = ["EngineProcess", "engine_frames_dropped_total"]
