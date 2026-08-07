# E2E Latency Benchmark (Story 6.1 — NFR1)

Path: new block -> `borrow_activity` -> `fragility_score` -> `format_alert` -> `emit` (no-op poster; excludes subscriber network RTT).

Rounds: 500, subscribers: 3.

| metric | ms | gate |
|---|---:|---:|
| p50 | 0.3265 | — |
| p95 | 0.4652 | < 50.0 |
| p99 | 3.0031 | < 80.0 |

The B0 detector makes the compute path microseconds; NFR1 headroom is dominated by (excluded) I/O — WS receive and the webhook POST.
