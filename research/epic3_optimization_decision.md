# Epic 3 Optimization Scope Decision (Tracks 3B / 3C / 3D) `[RESEARCH]`

Date: 2026-08-06 · Refs: `metrics/baseline.md` (baseline-v0), `research/graph_topology.md` (2R.2)

## Context

Epic 3 Tracks 3B (bond-dimension R&D), 3C (SVD truncation), and 3D (kernel
optimization) were scoped **before** the MPS forward pass had been measured. Their
shared purpose is to drive latency toward the `3E.1` budget (`p95 < 30 ms`).

The `baseline-v0` measurement (Story 3A.4) now shows the **naive** full-SVD
forward pass (`engine/mps/naive.py`) already clears that budget by a wide margin:

| Graph size | p95 latency | vs 30 ms gate | fwd-pass peak mem |
|---|---:|---:|---:|
| N = 15 (realtime v1) | ~0.055 ms | **~545× under** | < 0.01 MB |
| N = 50 | ~0.10 ms | **~290× under** | < 0.01 MB |

Per 2R.2, the realtime v1 graph is `N ≈ 10–15` and truncation/sparse formats only
pay off at `N ≥ 128`.

## Decision

**Right-size Epic 3: build only what carries value at v1 scale; defer premature
optimization.**

| Track / Story | Decision | Rationale |
|---|---|---|
| **3C.1 truncated_svd** | **BUILD** (done) | reusable low-rank primitive; needed at N≥128 |
| **3C.2 auto_rank** | **BUILD** (done) | energy-based rank selection; reusable |
| **3C.4 stability guard** | **BUILD** (done) | correctness safety net, cheap |
| **3C.3 recompression pipeline** | **DEFER** | wiring truncation into `fragility_raw` gives no v1 benefit (full spectrum is tiny); revisit at N≥128 |
| **3B.1–3B.3 bond-dim sweep/Pareto/plot** | **DEFER** | optimizes latency that is already 290–545× under budget; no decision to make until latency is a constraint |
| **3D.1–3D.3 opt_einsum / TorchScript / tensor reuse** | **DEFER** | micro-optimizing a ~0.1 ms path is negative ROI at v1 |
| **3E.1 forward-pass gate** | **BUILD** (done) | locks the `p95 < 30 ms` budget so future growth can't silently regress |
| **3E.2 regression suite** | **BUILD** (done) | `metrics/optimized.md` + tag `mps-optimized-v1` |

## Re-activation trigger

Un-defer 3B / 3C.3 / 3D when **either** holds (mirrors the 2R.2 sparse trigger):

1. `N ≥ 128` (evaluate) → `N ≥ 512` (mandate), **or**
2. the `3E.1` gate (`tests/bench_mps.py`) starts failing or drops below ~3× headroom.

Until then, the `3E.1` gate is the guard: if the naive path ever approaches 30 ms,
that failure is the signal to build 3B/3C.3/3D. This keeps the option open at zero
ongoing cost (YAGNI, but with a tripwire).
