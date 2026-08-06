# Optimized Metrics — `mps-optimized-v1` (Story 3E.2)

Locks the post-Track-3 state of the MPS forward pass and its comparison to
`baseline-v0` (Story 3A.4), so future PRs cannot regress it. Ref machine and
methodology: see `metrics/baseline.md`.

## Baseline vs optimized

Per `research/epic3_optimization_decision.md`, the naive baseline already clears
the `3E.1` gate (`p95 < 30 ms`) by ~290–545× at v1 scale, so the latency-oriented
optimization tracks (3B bond-dim, 3C.3 recompression, 3D kernel) were **deferred**.
There is therefore **no latency delta** to report: `mps-optimized-v1` == the naive
path measured in `baseline-v0`.

| Metric | baseline-v0 | optimized-v1 | Δ |
|---|---:|---:|---:|
| p95 latency, N=15 (ms) | ~0.055 | ~0.055 | none (deferred) |
| p95 latency, N=50 (ms) | ~0.10 | ~0.10 | none (deferred) |
| fwd-pass peak mem (MB) | < 0.01 | < 0.01 | none |
| output range | [0, 1] | [0, 1] | unchanged |
| accuracy (oracle A/B) | 0.789690 / 0.741117 | 0.789690 / 0.741117 | identical |

**What Track 3 *did* add:** reusable SVD-truncation primitives
(`engine/mps/truncation.py`: `truncated_svd`, `auto_rank`, rank-deficiency guard)
ready for the `N ≥ 128` regime, and the `3E.1` latency gate wired into
`tests/bench_mps.py`.

## Regression gates (active)

| Gate | Where | Rule |
|---|---|---|
| 3E.1 forward-pass budget | `tests/bench_mps.py` | `p95 < 30 ms` (hard) |
| 3A.2 regression | `tests/bench_mps.py` | `p95 ≤ baseline × 1.10` |

Run: `pytest tests/bench_mps.py --benchmark-only`.

## Git tag

`mps-optimized-v1` marks the commit introducing `engine/mps/truncation.py` + the
3E.1 gate. Because no optimization was applied, this tag is functionally
equivalent to `baseline-v0` in performance; it exists to anchor the regression
suite and record that Track 3 optimization was **consciously deferred**, not
skipped.
