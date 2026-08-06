# Story 4R.3 — Failure Mode & Recovery Analysis (FMEA) `[RESEARCH]`

Date: 2026-08-06 · Refs: `research/decision_b0_v1_detector.md`, `research/latency_budget.md`

FMEA for the v1 (B0) pipeline: `WS ingest → decode → ring buffer → B0 detector →
payload → webhook`. Each mode lists cause, detection, expected behavior, recovery,
and the story that owns it.

| # | Failure mode | Cause | Detection | Expected behavior | Recovery | Owner |
|---|---|---|---|---|---|---|
| F1 | **WS disconnect** | node/network drop, provider restart | `ingestion.metrics` stall watchdog (`ingestion_ws_last_message_seconds` > 15 s) + connection error | log WARN, stop emitting on stale data | exponential backoff reconnect (0.5→30 s) | 1A.3 reconnector, 1A.5 metrics |
| F2 | **Malformed / undecodable log** | unexpected ABI, non-whitelist contract, bad row | decoder raises / router returns `None` | drop the single event, never crash the loop | continue; bad CSV rows → `csv_errors.log` | 1B.4 router, 1D.1 csv loader |
| F3 | **Ring buffer overflow** | ingest faster than consumer | buffer at `maxlen` (bounded deque) | oldest events evicted (FIFO) — bounded memory (NFR4) | none needed; window is last ~10 blocks by design | 1C.2/1C.4 |
| F4 | **Detector exception** | empty window, missing `event_type` key | try/except around B0 score; `borrow_activity([])→0` | emit no alert for that block (score 0), log WARN | next block re-evaluates | 4.x (B0), Epic 5 orchestrator |
| F5 | **Webhook subscriber timeout / 5xx** | subscriber down/slow | aiohttp timeout on POST | isolate: one slow subscriber must not block others | 1 retry then log ERROR, drop; async fan-out | 5.3 emitter |
| F6 | **Duplicate / out-of-order blocks** | reorg, provider replay | block number non-monotonic check | de-dup by block; warn on out-of-order | idempotent buffer write | 1A.4 streams, 1D.2 |
| F7 | **Alert storm** (B0 fires every block) | sustained elevated-borrow regime (LUNA-class) | RED sustained across many blocks | debounce: fire on threshold *crossing* + periodic re-alert, not every block | Epic 5 payload/emitter dedup policy | 5.2/5.3 |
| F8 | **Missed cascade** (false negative) | off-chain-origin event, low on-chain footprint (FTX-class, `ftx_validation.md`) | none at runtime (silent) | documented v1 scope limit — B0 covers on-chain deleveraging only | out of scope v1; needs off-chain feed | product / Epic 6 |

## Notes

- **F3/F7 supersede Story 4.4 (backpressure/circuit-breaker) for v1.** The queue-drop
  circuit breaker was designed for a slow CPU-bound MPS engine; B0 keeps up trivially,
  so the only real backpressure need is **webhook fan-out isolation (F5)** and
  **alert-storm debounce (F7)**, both owned by Epic 5. Story 4.4 is therefore
  **deferred/re-scoped** — see `decision_b0_v1_detector.md`.
- **F8 is the most important honesty item:** the v1 detector has a known false-negative
  class (off-chain cascades). It must be stated in product docs, not hidden.
