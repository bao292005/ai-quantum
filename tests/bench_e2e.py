"""End-to-end latency benchmark (Story 6.1 — NFR1).

Measures the per-block hot path **new block → webhook dispatched**:
``borrow_activity → fragility_score → format_alert → emit`` (with a no-op poster,
so the measured time is the pipeline compute + fan-out orchestration that
QuantumRadar controls; real subscriber network round-trip is excluded and is
subscriber-dependent).

Run explicitly (``bench_*`` name → not collected by the default suite):

    pytest tests/bench_e2e.py -q

Gate: p95 < 50 ms (NFR1), p99 < 80 ms.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

import numpy as np

from emitter.pipeline import evaluate_and_emit

REPORT_DIR = Path(__file__).resolve().parent.parent / "benchmarks"
GATE_P95_MS = 50.0
GATE_P99_MS = 80.0
_ROUNDS = 500
_SUBSCRIBERS = ["http://sub1/hook", "http://sub2/hook", "http://sub3/hook"]


async def _noop_poster(url):  # simulate an instantly-responding subscriber
    return True


def _block_events(n_borrow: int = 40):
    # A RED-level window (score 100) so the full format+emit path runs each block.
    return [{"event_type": "borrow"}] * n_borrow


def test_e2e_latency_meets_nfr1():
    events = _block_events()
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(  # warm-up (exclude one-time import/JIT costs)
            evaluate_and_emit(events, _SUBSCRIBERS, poster=_noop_poster)
        )
        latencies = []
        for _ in range(_ROUNDS):
            start = time.perf_counter()
            loop.run_until_complete(
                evaluate_and_emit(events, _SUBSCRIBERS, poster=_noop_poster)
            )
            latencies.append((time.perf_counter() - start) * 1000.0)
    finally:
        loop.close()

    arr = np.asarray(latencies)
    p50, p95, p99 = (float(np.percentile(arr, q)) for q in (50, 95, 99))

    REPORT_DIR.mkdir(exist_ok=True)
    (REPORT_DIR / "e2e_latency.md").write_text(
        "# E2E Latency Benchmark (Story 6.1 — NFR1)\n\n"
        "Path: new block -> `borrow_activity` -> `fragility_score` -> "
        "`format_alert` -> `emit` (no-op poster; excludes subscriber network RTT).\n\n"
        f"Rounds: {_ROUNDS}, subscribers: {len(_SUBSCRIBERS)}.\n\n"
        "| metric | ms | gate |\n|---|---:|---:|\n"
        f"| p50 | {p50:.4f} | — |\n"
        f"| p95 | {p95:.4f} | < {GATE_P95_MS} |\n"
        f"| p99 | {p99:.4f} | < {GATE_P99_MS} |\n\n"
        "The B0 detector makes the compute path microseconds; NFR1 headroom is "
        "dominated by (excluded) I/O — WS receive and the webhook POST.\n"
    )

    assert p95 < GATE_P95_MS, f"E2E p95 {p95:.3f}ms exceeds NFR1 gate {GATE_P95_MS}ms"
    assert p99 < GATE_P99_MS, f"E2E p99 {p99:.3f}ms exceeds {GATE_P99_MS}ms"
