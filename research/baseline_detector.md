# Story 3R.3: Naive Baseline Detector Design `[RESEARCH]` — P1

## Purpose

Design a **simple, non-MPS** fragility detector to serve as the control that
proves whether the MPS entanglement-entropy model (3R.1) actually **earns its
complexity**. Without a baseline, a "RED ≥ 10 min early" result is unfalsifiable —
a trivial detector might do just as well. This doc defines the baseline
algorithm(s), the head-to-head comparison method (lead-time, false-positive), and
confirms each is implementable in **≤ 1 build story**.

Research-only artifact. Feeds Epic 4 calibration (4.1/4.2) and Epic 6 Success
Signal proof. Literature basis: `research/literature_review.md` (L3 — largest
eigenvalue / centrality is the orthodox systemic-risk scalar).

Inputs available (schema 0.1 events / fixtures): `block_number`,
`block_timestamp`, `protocol`, `event_type` (swap|mint|burn|borrow|supply|
withdraw|liquidation), `pool_address`, `token0/1`, `amount0/1`, `tx_hash`,
`log_index`.

---

## 1. Design principle — an ablation ladder

The baselines are chosen so that MPS is the **top rung of a ladder**, each rung
adding one idea. Comparing adjacent rungs isolates *which* idea carries the signal.

| Rung | Detector | Uses graph? | Uses full spectrum? | Isolates |
|---|---|---|---|---|
| **B0** | Aggregate utilization/leverage scalar | ❌ | ❌ | "does the graph help at all?" |
| **B1** | Largest eigenvalue / top-mode share of the coupling matrix | ✅ | ❌ (top only) | "does entropy beat just `σ₁`?" |
| **MPS** | Entanglement entropy `F_raw` (3R.1) | ✅ | ✅ | (the product) |

If MPS ≈ B1 → the entropy adds nothing (ship B1, it's cheaper). If MPS ≈ B0 → the
whole graph adds nothing. MPS is justified only if it **strictly** beats both on
lead-time and/or false-positive rate.

---

## 2. Baseline B0 — Aggregate leverage/utilization (no graph)

The cheapest genuine *leading* indicator (not the label). Per rolling window `Δ`
(e.g. one block, or the last `k` blocks in the ring buffer):

```
borrow_vol  = Σ |amount|  over events with event_type == "borrow"
supply_vol  = Σ |amount|  over events with event_type ∈ {"supply"}
util_raw    = borrow_vol / (supply_vol + ε)            # leverage proxy, ≥ 0
B0_score    = min(util_raw / U_ref, 1.0)               # normalize to [0,1]
```

`U_ref` is a calibration constant (Epic 4). Rationale: rising system-wide leverage
precedes liquidation cascades. **Must NOT use `liquidation`-event counts** — those
are the label we predict; using them leaks ground truth.

Cost: one pass over the buffer, `O(E)`. Trivial.

## 3. Baseline B1 — Spectral top-eigenvalue (graph, no entropy)

Reuses the Epic-2 tensor path. Two variants:

```
# B1a — structure only (cheapest graph detector)
A          = adjacency_tensor(graph)          # (N,N), Story 2B.1
B1a_score  = λ_max(A) / N          # normalized largest eigenvalue ∈ [0,1]-ish

# B1b — SAME input as MPS (fair entropy ablation)
W          = diag(√m) A diag(√m)   # m = X·w, exactly as 3R.1 Step 2
σ          = svdvals(W)
B1b_score  = σ₁² / Σσ²  = p₁       # top-mode Born share ∈ [0,1]
```

B1b shares MPS's exact input `W`; the **only** difference is
`entropy(p)` (MPS) vs `max(p) = p₁` (B1b). This is the sharpest test of "is the
entanglement *entropy* the right summary, or does the dominant mode suffice?"
(Literature L3: `σ₁` is the classic Spectral SRI.)

Cost: same `O(N³)` SVD already computed for MPS. Trivial at `N ≈ 10–15`.

### Motivating evidence (verified on the 3R.1 oracle graphs)

| Graph | MPS `F_raw` | B1a `λ_max(A)` | B1a top-share `p₁(A)` |
|---|---|---|---|
| Oracle A — K3 triangle, `m=(1,1,1)` | **0.789690** | 2.0000 | 0.6667 |
| Oracle B — triangle, `m=(1,1,4)` | **0.741117** | 2.0000 | 0.6667 |
| Path `1–2–3`, `m=(1,1,1)` | 0.630930 | 1.4142 | 0.5000 |

**Key observation:** B1a (bare adjacency) gives **identical** scores for Oracle A
and Oracle B (same `A`), so it **cannot see** the node-mass concentration that
distinguishes them — while MPS separates them (0.7897 vs 0.7411) because it weights
by `m` *and* reads the whole spectrum. This is a concrete example of where the MPS
pipeline could add value that a naive top-eigenvalue-of-`A` detector misses. (B1b,
which uses `W`, would see the difference — hence B1b is the *harder*, fairer
baseline to beat.)

---

## 4. Comparison methodology (the experiment)

Run all detectors through the **same** replay pipeline (`ReplayDriver`, Story
1D.3) on the **same** fixtures, scoring each block.

### 4.1 Fair thresholding
Each detector `d` emits a raw score `s_d(t) ∈ [0,1]` per block. Calibrate a single
RED threshold `θ_d` **per detector** on a shared rule (e.g. `θ_d` = the value that
yields an equal false-positive budget on `normal_2023_03_15`). This prevents an
unfair win from threshold tuning — every detector gets the same FP budget, then we
compare lead-time.

### 4.2 Metrics (per fixture)
- **Lead-time** `LT_d` = minutes between the first block where `s_d(t) ≥ θ_d`
  (sustained ≥ `p` blocks to avoid flicker) and the ground-truth first-liquidation
  timestamp (from `research/ground_truth_labeling.md` / `fixtures/backtest/README.md`).
  Success Signal requires `LT ≥ 10 min`.
- **False-positive rate** `FP_d` = fraction of blocks on `normal_2023_03_15` with
  `s_d(t) ≥ θ_d`. Target `< 5%` (Story 4.1 AC).
- **Discrimination** = `LT` on LUNA/FTX at the FP-matched threshold.

### 4.3 Decision rule — "does MPS add value?"
At an equal FP budget:
```
MPS wins if   LT_MPS ≥ LT_B1 + margin      (longer early warning), OR
              LT_MPS ≈ LT_B1 but FP_MPS < FP_B1 at equal LT (cleaner signal)
Ship the simplest detector within `margin` of the best.
```
`margin` (e.g. 1–2 min) set in Epic 4. If B0/B1 match MPS within `margin`, the
MPS complexity is **not** justified for v1 — a critical, honest gate.

---

## 5. Implementability (≤ 1 build story)

- **B0:** pure event aggregation over the buffer — a single function
  `baseline_utilization(events) -> float`. ~30 LOC + unit test.
- **B1a/B1b:** `torch.linalg.eigvalsh(A)` / reuse `svdvals(W)` from the MPS path —
  a few lines each; B1b is literally `p[0]` from the MPS spectrum.
- **Harness:** the comparison (§4) is a script over `ReplayDriver` reused by Epic
  4/6; not part of this ≤1-story build (the *detectors* are).

All three detectors together comfortably fit one build story
(`engine/baseline.py` + tests). Recommended: build them alongside 3A.1 so the
baseline lands before Epic 4 calibration needs it.

---

## Decision (summary)

- Baseline = an **ablation ladder**: **B0** (aggregate utilization, no graph),
  **B1** (largest-eigenvalue / top-mode share — B1a on `A`, B1b on `W`).
- Comparison at **equal false-positive budget**, metric = **lead-time** (≥10 min
  target) with **FP < 5%** on `normal`; MPS must **strictly** beat B1b to justify
  its complexity.
- Verified toy evidence: bare-adjacency B1a cannot distinguish node-mass
  concentration (Oracle A ≡ B), whereas MPS can — the concrete value hypothesis to
  confirm on real LUNA/FTX data in Epic 4.
- All detectors are ≤1 build story (`engine/baseline.py`), reusing the Epic-2
  tensor path and Story 1D.3 replay. No schema/contract change.
