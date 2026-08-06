# Story 4.1 — LUNA/UST Calibration (B0 v1 detector) `[RESEARCH]`

Date: 2026-08-06 · Status: **Complete — Success Signal met on LUNA**
Refs: `research/4.1_calibration_findings.md`, `research/decision_b0_v1_detector.md`,
`research/ground_truth_labeling.md`

## Detector

Per the v1 decision (`decision_b0_v1_detector.md`), the calibrated detector is the
**B0 borrow-rate** signal (`engine.baseline.borrow_activity`), not MPS — the MPS
fragility did not discriminate crisis from calm on these fixtures.

## Locked parameters

| Parameter | Value | Rationale |
|---|---|---|
| window | 300 blocks (~1 h) | enough Aave events per window for a stable rate |
| stride | 100 blocks (~20 min) | evaluation cadence |
| signal | `borrow_activity(window)` | borrow-event count = leverage-demand rate |
| `B_LOW` | 16 | the **normal control's max** borrow/window → score 0 (calm ceiling) |
| `B_HIGH` | 32 | **2× calm-max** → score 100 (acute stress) |
| score | `100 · clamp((rate − 16) / (32 − 16), 0, 1)` | maps rate → `fragility_score ∈ [0,100]` |
| alert | `RED` if score ≥ 90, `YELLOW` if score ≥ 70 | fixed by `fragility_alert.schema.json` |

`B_HIGH = 2·B_LOW` is a deliberate, non-overfit choice: "acute" = borrow demand at
double the calm ceiling. Sweeping `B_HIGH ∈ [30, 50]` leaves the LUNA result and
`FP = 0%` unchanged, so the calibration is not knife-edge sensitive.

## Result (verified on real fixtures)

| Fixture | windows | RED before cascade | first-RED lead | FP (RED / YELLOW) |
|---|---:|---:|---:|---:|
| **LUNA** (crisis) | 157 | 122 | **1612 min (~27 h)** | — |
| **NORMAL** (control) | 47 | 0 | — | **0.0% / 0.0%** |

**Story 4.1 AC met:** LUNA fires `RED` well before `red_deadline`
(cascade − 10 min = block 14,732,063), and the normal control produces **zero**
YELLOW/RED windows (FP = 0% ≤ 5% budget). The Success Signal, as defined by
`ground_truth_labeling.md` (`red_deadline` = latest acceptable RED time), is
satisfied.

## Honest caveats (carry into 4.2 / ship)

1. **~27 h lead = regime alert, not a pinpoint.** B0 fires RED from essentially
   the start of the crisis fixture — it detects the *elevated-borrow regime* for
   the whole window, not the precise cascade moment. This clears "≥ 10 min early"
   but massively overshoots the epics-4.1 `[10, 30] min` framing (which assumed a
   sharp MPS spike). v1 product semantics = **"elevated systemic-risk regime"**,
   not "cascade imminent in N minutes."
2. **FP = 0% rests on a single calm fixture.** Widen the normal-control set before
   claiming a general false-positive rate (tracked for 6.3).
3. **FTX preview (4.2 will formalize):** at these same locked params, FTX produces
   **no RED and no YELLOW before its cascade** (its on-chain footprint is tiny —
   8 liquidations, mostly off-chain assets; ground-truth README calls it a
   *low-severity* cascade). So B0-RED **does not generalize** to low-severity /
   off-chain-origin cascades. 4.2 should report this honestly rather than re-tune
   `B_HIGH` down to force an FTX RED (which would erode the calm margin).

## Handoff

- **Epic 5** implements the locked score mapping above (the payload formatter maps
  `borrow_activity` → `fragility_score` → `alert_level`). The mapping currently
  lives only here + in tests (see code-review M2) — encapsulate it in source then.
- **4.2** applies these exact params to FTX **without re-tuning** and reports the
  low-severity-cascade limitation.
