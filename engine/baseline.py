"""Naive non-MPS baseline detector — B0 (Story 3R.3 build).

B0 is the control the MPS fragility model (Epic 3) must beat to justify its
complexity (`research/baseline_detector.md`, `research/literature_review.md` L3).
It reads Aave lending-stress directly from schema-0.1 event flows — no graph, no
tensor.

Empirical result (`research/4.1_calibration_findings.md`): windowed borrow
activity separates crisis from calm by ~11× (LUNA mean 88.8 vs normal 7.66) and
is elevated *before* the cascade — a threshold set at the calm-control maximum
fires RED on LUNA/FTX with **0% false positives** on the normal control.

These are pure event-count reducers over a window of events (the caller decides
the window, e.g. the ring buffer or a replay slice).
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

Event = dict[str, Any]


def borrow_supply_counts(events: Iterable[Event]) -> tuple[int, int]:
    """Return ``(borrow_count, supply_count)`` over ``events``."""
    borrow = supply = 0
    for e in events:
        et = e["event_type"]
        if et == "borrow":
            borrow += 1
        elif et == "supply":
            supply += 1
    return borrow, supply


def borrow_activity(events: Iterable[Event]) -> int:
    """B0 primary signal: number of ``borrow`` events (leverage-demand rate).

    This is the strongest crisis/calm discriminator found in the backtest
    fixtures and leads the cascade (elevated throughout the pre-cascade runway).
    """
    return sum(1 for e in events if e["event_type"] == "borrow")


def utilization_ratio(events: Iterable[Event]) -> float:
    """B0 alternative: ``borrow / (supply + 1)`` flow-leverage proxy.

    Laplace-smoothed (``+1``) so an all-borrow / no-supply window is finite and
    a division by zero never occurs. Returns ``0.0`` for an empty window.
    """
    borrow, supply = borrow_supply_counts(events)
    return borrow / (supply + 1)


# --- Calibrated score mapping (Story 4.1 → 5.2) -----------------------------
# Locked in calibration/luna_calibration.md: score ramps 0→100 as the windowed
# borrow rate goes from the calm-control max (B0_SCORE_LOW) to 2× that
# (B0_SCORE_HIGH). Verified: LUNA RED (score ≥ 90) ~27 h early, FP = 0% on the
# normal control. (Resolves code-review M2 — the mapping now lives in source.)
B0_SCORE_LOW = 16
B0_SCORE_HIGH = 32


def fragility_score(
    borrow_rate: float,
    *,
    low: float = B0_SCORE_LOW,
    high: float = B0_SCORE_HIGH,
) -> float:
    """Map a windowed borrow rate to a ``fragility_score`` in ``[0, 100]``.

    ``score = 100 · clamp((rate − low) / (high − low), 0, 1)``.
    """
    if high <= low:
        raise ValueError(f"high ({high}) must exceed low ({low})")
    x = (borrow_rate - low) / (high - low)
    return max(0.0, min(1.0, x)) * 100.0


__all__ = [
    "borrow_supply_counts",
    "borrow_activity",
    "utilization_ratio",
    "fragility_score",
    "B0_SCORE_LOW",
    "B0_SCORE_HIGH",
]
