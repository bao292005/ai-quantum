"""Unit tests for engine.baseline (Story 3R.3 → B0 baseline detector build)."""

from __future__ import annotations

from engine.baseline import borrow_activity, borrow_supply_counts, utilization_ratio


def _ev(event_type: str):
    return {"event_type": event_type, "protocol": "aave_v2"}


def _events(borrow: int, supply: int, other: int = 0):
    return (
        [_ev("borrow")] * borrow
        + [_ev("supply")] * supply
        + [_ev("swap")] * other
    )


def test_borrow_supply_counts():
    assert borrow_supply_counts(_events(3, 5, 7)) == (3, 5)


def test_borrow_activity_counts_only_borrow():
    assert borrow_activity(_events(4, 9, 2)) == 4


def test_borrow_activity_empty():
    assert borrow_activity([]) == 0


def test_utilization_ratio_laplace_smoothed():
    # 6 borrow / (2 supply + 1) = 2.0
    assert utilization_ratio(_events(6, 2)) == 2.0


def test_utilization_ratio_no_supply():
    # 3 borrow / (0 + 1) = 3.0 — no division by zero
    assert utilization_ratio(_events(3, 0)) == 3.0


def test_utilization_ratio_empty_is_zero():
    assert utilization_ratio([]) == 0.0
