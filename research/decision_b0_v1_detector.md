# Decision: B0 borrow-rate baseline is the v1 detector (MPS → R&D)

Date: 2026-08-06 · Status: **Accepted** · Refs: `research/4.1_calibration_findings.md`,
`research/baseline_detector.md`, `research/literature_review.md`

## Context

The de-risk spike for Story 4.1 showed:
- The MPS graph/entropy fragility (Epics 2–3) does **not** discriminate crisis from
  calm on the LUNA/FTX/normal fixtures (signal was inverted).
- A trivial **B0 borrow-rate detector** (`engine/baseline.py`) meets the Success
  Signal easily: threshold = calm-control max → **FP = 0%**, LUNA lead ~29 h, FTX
  lead ~47 h (regression-tested).

Per the project's own falsifiability gate (3R.3, literature L3), MPS must beat the
baseline to justify its complexity. It does not (yet).

## Decision

**Adopt B0 (`borrow_activity` over a rolling window) as the QuantumRadar v1
detector.** The MPS tensor-network model is reclassified as **future R&D**, parked
behind the working baseline (its primitives — `engine/mps/`, `engine/tensor/`,
`engine/graph/` — remain in-tree, tested, and reusable if a future feature set
makes it beat B0).

## Consequences

1. **Massive simplification of Epic 4.**
   - **NFR3 (PyTorch core in a separate process)** was motivated by the CPU-bound
     MPS forward pass. B0 is `O(events)` counting — no heavy engine. → Story 4.3
     (multiprocessing wrapper) is likely **unnecessary for v1**; re-scope or defer.
   - **Latency (4R.1 / NFR1 < 50 ms)** becomes trivial — B0 is microseconds. The
     30 ms MPS gate (3E.1) no longer sits on the critical path.
2. **Epic 5 (alert/API) proceeds on B0's scalar** — the payload formatter maps the
   B0 signal / threshold crossing to YELLOW/RED (`fragility_alert.schema.json`).
   `fragility_score` is derived from the B0 signal (e.g. normalized borrow-rate),
   not from MPS entropy.
3. **Calibration (4.1/4.2)** = choosing the B0 threshold and window; already shown
   to generalize LUNA→FTX with no re-tune (same threshold fires both). 4.2 becomes
   a formalization/report, not new modeling.
4. **Honesty debt to close before shipping:**
   - FP confidence rests on a **single** calm fixture — widen the normal-control
     set before claiming a general FP rate.
   - B0's ~29 h lead means it flags a *stressed regime*, not an imminent cascade;
     document this as the v1 product semantics ("elevated-risk regime alert").

## Revisit trigger (un-park MPS)

Re-open the MPS path only if a future node-feature set (e.g. utilization as a node
feature, richer topology, or price/vol from in-scope volatile pools) makes
`fragility_raw` **beat B0** on lead-time and FP across a wider fixture set.
