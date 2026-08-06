# Story 4.2 — FTX Cross-Validation (B0 v1 detector) `[RESEARCH]`

Date: 2026-08-06 · Status: **Complete — cross-validation reveals a real limitation**
Refs: `calibration/luna_calibration.md`, `research/ground_truth_labeling.md`,
`research/decision_b0_v1_detector.md`

## Goal

Apply the **LUNA-calibrated B0 parameters with NO re-tuning** to the FTX fixture
and check whether the Success Signal generalizes (guards against overfitting to
LUNA). Ground truth: FTX `cascade_start` = block 15,914,506 (2022-11-07T00:17:11Z),
`red_deadline` = 10 min earlier.

## Locked parameters (unchanged from 4.1)

`window = 300`, `stride = 100`, `score = 100·clamp((borrow_rate − 16)/(32 − 16), 0, 1)`,
`RED ≥ 90`, `YELLOW ≥ 70`.

## Result

| Fixture | pre-cascade borrow max | pre-cascade max score | first RED before cascade | first YELLOW before cascade |
|---|---:|---:|---:|---:|
| LUNA (4.1) | 84 | 100 | ~1612 min early | ~1612 min early |
| **FTX** | **24** | **50** | **none** | **none** |

At the LUNA-calibrated thresholds, FTX's pre-cascade borrow activity peaks at a
score of **50** — below the YELLOW bar (70) and the RED bar (90). **FTX produces no
YELLOW and no RED before its cascade.** (A score of 100 is only reached *after* the
cascade, borrow max 36.)

## Interpretation — honest negative result

**B0 calibrated on LUNA does NOT generalize to FTX.** This is not a tuning bug; it
is a property of the event:

- FTX was an **off-chain (CEX) collapse**. Its on-chain Aave footprint is tiny — the
  ground-truth README documents only **8 liquidations** (vs LUNA's 266) and a
  *low-severity* on-chain cascade. Pre-cascade borrow activity (mean 11.1, max 24)
  sits just above the calm baseline (normal mean 7.66) but far below the LUNA regime
  (mean 88.8).
- So the leading signal B0 relies on (a surge in on-chain leverage demand) is simply
  **not present** for an off-chain-origin cascade.

**Do NOT lower `B_HIGH` to force an FTX RED.** FTX pre-cascade max (24) is close to
the normal control's activity band; dropping the RED threshold to catch it would
erode the calm margin and risk false positives on busy-but-healthy markets (and the
FP estimate already rests on a single normal fixture).

## v1 scope statement (product honesty)

The v1 B0 detector reliably flags **high-severity, on-chain deleveraging cascades**
(LUNA-class: RED ~27 h early, FP 0% on the control). It **does not** detect
**off-chain-origin / low-on-chain-footprint** events (FTX-class) — those leave too
little on-chain borrow signal. This limitation must be stated in the product
README / alert docs (Epic 5) and re-examined in Epic 6 (6.3 Success-Signal proof).

## Consequence for the roadmap

- The original Success Signal ("RED ≥ 10 min before LUNA **or** FTX") is met for
  LUNA; FTX is a documented miss. Whether v1 ships requires a product call: LUNA-class
  coverage may be sufficient for a first release, with FTX-class detection as a known
  gap (would need an off-chain / price-oracle stress feed, out of the current
  on-chain-only scope).
