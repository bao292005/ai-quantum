# Story 4R.1 — End-to-End Latency Budget `[RESEARCH]`

Date: 2026-08-06 · Refs: `research/decision_b0_v1_detector.md`, `metrics/baseline.md`

## NFR1

End-to-end latency (new block → webhook sent) **< 50 ms** (p95).

## Budget — v1 (B0 detector)

The v1 detector is **B0** (`engine.baseline.borrow_activity`, event counting), not
the MPS tensor core. This collapses the compute budget: the per-block detector cost
is microseconds, so the NFR1 budget is dominated by I/O, not computation.

| Stage | Budget (ms) | Basis |
|---|---:|---|
| WS receive + parse block/logs | 15 | network + `web3` decode (dominant, I/O-bound) |
| Decode → `TickDataEvent` (Track 1B) | 3 | ABI decode per log, small counts |
| Ring-buffer write (Track 1C) | 1 | in-memory deque/numpy, O(1) |
| **Detector: B0 borrow-rate over window** | **1** | pure Python counting over ~10-block window |
| Payload format (Epic 5) | 2 | dict → JSON, schema-validate |
| Webhook emit (aiohttp, async) | 20 | outbound POST to subscriber (I/O-bound, dominant) |
| **Total** | **42** | **< 50 ms with ~8 ms headroom** |

## Notes

- **The detector is no longer on the critical path.** Under the MPS design this
  stage carried a 30 ms sub-budget (gate 3E.1); with B0 it is ~1 ms. The 30 ms MPS
  gate still exists in `tests/bench_mps.py` but guards the *parked* R&D path, not v1.
- **Dominant costs are I/O** (WS receive, webhook POST), governed by network and the
  subscriber's responsiveness — mitigated by async emission (Story 5.3) and the
  backpressure decision below.
- **NFR3 (engine on a separate process)** was motivated by a CPU-bound MPS core.
  With B0 there is no CPU-bound stage, so cross-process IPC (4R.2) and the
  multiprocessing wrapper (4.3) are **not required for v1** — see
  `research/decision_b0_v1_detector.md`. This removes IPC serialization from the
  budget entirely.

## Gate handoffs

- **6.1 (E2E latency benchmark)** validates this budget end-to-end (mock WSS → mock
  subscriber), target p95 < 50 ms / p99 < 80 ms.
- If v1 ever re-adopts MPS, restore the 30 ms detector sub-budget and the IPC line.
