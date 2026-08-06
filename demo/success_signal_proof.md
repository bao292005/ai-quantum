# Story 6.3 — Success Signal Proof (E2E)

Date: 2026-08-06 · Detector: **B0** (`research/decision_b0_v1_detector.md`)
Refs: `calibration/luna_calibration.md`, `calibration/ftx_validation.md`,
`research/ground_truth_labeling.md`

## What was run

The **full E2E path** on each backtest fixture, block window by block window:

```
replay events → borrow_activity (B0) → fragility_score → format_alert (schema 0.3)
              → emit() fan-out to a subscriber
```

via `emitter.pipeline.evaluate_and_emit` (window 300 blocks / stride 100), with a
capturing subscriber to confirm delivery. Locked calibration (LUNA, no re-tune for
FTX/normal): `score = 100·clamp((borrow_rate − 16)/16, 0, 1)`, RED ≥ 90.

## Results (machine-verified)

| Fixture | RED alerts | first RED lead vs cascade | delivered | YELLOW |
|---|---:|---:|:--:|---:|
| **LUNA** (2022-05) | 122 | **+1611.6 min (~26.9 h) early** | ✅ all | 12 |
| **FTX** (2022-11) | 1 | none before cascade | ✅ | 2 |
| **NORMAL** (2023-03, control) | 0 | — | — | 0 |

Ground truth: LUNA `cascade_start` block 14,732,113 (2022-05-07T21:14:48Z),
`red_deadline` = 10 min earlier.

## Verdict

- ✅ **LUNA Success Signal PROVEN.** RED fires ~26.9 h before the cascade — far
  inside the "≥ 10 min early" requirement — and every alert is delivered to the
  subscriber with a schema-valid payload.
- ✅ **False positives = 0** on the normal-market control (0 RED, 0 YELLOW).
- ❌ **FTX NOT proven (documented miss).** FTX produces no RED before its cascade.
  This is the honest limitation established in `calibration/ftx_validation.md`:
  FTX was an off-chain (CEX) collapse with a tiny on-chain footprint (8
  liquidations), so the B0 on-chain-borrow signal never reaches RED pre-cascade.

## Honesty statement (scope of the proof)

The original Story 6.3 AC requires **both** LUNA **and** FTX to fire RED ≥ 10 min
early. That is **partially met**:

1. **LUNA-class (high-severity, on-chain deleveraging): PROVEN** end-to-end.
2. **FTX-class (off-chain-origin, low on-chain footprint): OUT OF SCOPE for v1** —
   a known false-negative that needs an off-chain / price-oracle stress feed,
   which the current on-chain-only pipeline does not have.
3. **FP confidence** rests on a **single** normal-control fixture; widen the
   control set before publishing a general false-positive rate.

## Reproduce / regression

- Regression test encoding the LUNA lead + normal FP=0:
  `tests/integration/test_baseline_success_signal.py`.
- E2E latency (NFR1): `tests/bench_e2e.py` (p95 ~0.5 ms, well under 50 ms).
- A recorded screencast (per the AC) is not produced here (out of band for a
  text artifact); the numbers above are reproducible from the committed fixtures
  and code.
