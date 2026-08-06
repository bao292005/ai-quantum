# Baseline Metrics — `baseline-v0` (Story 3A.4) `[RESEARCH]`

Frozen reference numbers for the **naive** MPS forward pass
(`engine.mps.naive.fragility_raw`, Story 3A.1) before any optimization
(Track 3B bond dimension, 3C SVD truncation, 3D kernel). Every later optimization
is measured against these numbers; the `3E.1` gate (`p95 < 30 ms`) and the `3A.2`
regression gate (`p95` must not grow > 10%) both reference this baseline.

Source data: `bench_report/latency.json` (Story 3A.2) and `bench_report/memory.md`
(Story 3A.3), produced by `tests/bench_mps.py` and `tests/bench_memory.py`.

## Reference machine & environment (assumptions)

| Item | Value |
|---|---|
| CPU | Apple M1 (8 cores, 8 physical) |
| Accelerator | none — CPU-only (NFR5) |
| PyTorch | 2.13.0 (CPU build) |
| `torch.get_num_threads()` | 4 |
| NumPy | 1.26.3 |
| Python | 3.12.4 (`/opt/anaconda3/bin/python3`) |
| OS | macOS (darwin) |
| Date | 2026-08-06 |

> Numbers are machine-specific. Re-baseline (`baseline-v1`) if the reference
> machine, thread count, or PyTorch major version changes. Latency is wall-clock
> from `pytest-benchmark` (auto-calibrated rounds); memory is `tracemalloc`
> steady-state (post warm-up, one-time PyTorch allocations excluded).

---

## Table 1 — Latency (ms)

`fragility_raw` forward pass, times in **milliseconds**.

| Graph size | p50 | p95 | p99 | mean | rounds |
|---|---:|---:|---:|---:|---:|
| N = 15 (realtime v1, 2R.2) | 0.0516 | 0.0547 | 0.0635 | 0.0522 | 2256 |
| N = 50 (3A.1 AC size) | 0.0963 | 0.1029 | 0.1181 | 0.0981 | 7727 |

**Headroom vs 3E.1 gate (`p95 < 30 ms`):** ~**290×** at N=15, ~**290×** at N=50.
The naive full-SVD path already clears the MPS-forward budget by a wide margin at
v1 scale — bond-dimension / truncation optimization (3B/3C) is **not** latency-
critical until `N` grows well past the 2R.2 dense/sparse threshold (`N ≥ 128`).

## Table 2 — Memory

`tracemalloc` traced peak of the forward pass (steady-state, post warm-up).

| Graph size | traced current (MB) | traced peak (MB) | gate (< 500 MB) |
|---|---:|---:|:--:|
| N = 15 | 0.0023 | 0.0029 | PASS |
| N = 50 | 0.0001 | 0.0007 | PASS |
| N = 128 | 0.0002 | 0.0009 | PASS |

Process peak RSS (informational, includes the PyTorch runtime base): **238.2 MB**.

**Note:** the 500 MB PoC gate is checked against the **traced forward-pass peak**
(the isolatable metric), not whole-process RSS — the PyTorch base RSS is large and
constant, so gating on it would be flaky. Forward-pass allocations are KB-scale
(~5 orders of magnitude under the limit); top sites are `naive.py:76` (`svdvals`)
and `naive.py:75` (W construction).

## Table 3 — Output range & correctness oracle

`fragility_raw` returns a scalar in **[0, 1]** (raw, uncalibrated; Epic 4 maps to
the 0–100 alert score). Deterministic — repeated calls are bit-identical.

| Graph (3R.1 §7 oracle) | F_raw | meaning |
|---|---:|---|
| K3 triangle, `m=(1,1,1)` | 0.789690 | fully-coupled → high fragility |
| triangle, `m=(1,1,4)` | 0.741117 | concentrated mass → lower |
| path `1–2–3`, `m=(1,1,1)` | 0.630930 | chain → lowest |
| `N ≤ 1` / no edges / zero mass | 0.000000 | degenerate guard |

Oracle values are the locked correctness reference (tolerance `± 1e-5`,
`tests/unit/test_naive_fragility.py`).

---

## Optimization targets (handoff)

| Track | Goal vs this baseline |
|---|---|
| 3B (bond dim) | accuracy vs `F_raw` at reduced `χ`; latency/memory sweep |
| 3C (SVD truncation) | `p95` ↓ ≥ 40% *when it matters* (large N); accuracy loss < 5% |
| 3E.1 (gate) | keep `p95 < 30 ms` on this machine (currently ~0.10 ms) |
| 3A.2 (regression) | reject any commit with `p95 > baseline × 1.10` |

**Git tag:** this document is tagged `baseline-v0` on the commit that introduces
the baseline code (`engine/mps/naive.py` + benchmark harnesses). See Change Log /
sprint notes for the exact commit.
