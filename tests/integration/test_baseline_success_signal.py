"""Integration test: B0 baseline meets the Success Signal on real fixtures.

Encodes the `research/4.1_calibration_findings.md` result as a regression test:
with a RED threshold set at the calm-control's maximum windowed borrow activity,
the LUNA fixture fires RED *before* the cascade block (>= 10 min early) while the
normal-market control never fires (0% false positives).
"""

from __future__ import annotations

import bisect
import tempfile

import pytest

from engine.baseline import borrow_activity
from ingestion.csv_loader import iter_csv_events

# Ground truth (research/ground_truth_labeling.md).
LUNA_PATH = "fixtures/backtest/luna_2022_05_09.csv.gz"
NORMAL_PATH = "fixtures/backtest/normal_2023_03_15.csv.gz"
LUNA_CASCADE_BLOCK = 14_732_113
LUNA_RED_DEADLINE_BLOCK = 14_732_063  # cascade - ~10 min

_WINDOW = 300
_STRIDE = 100


def _load(path):
    errlog = tempfile.NamedTemporaryFile(suffix=".log", delete=False).name
    events = list(iter_csv_events(path, error_log=errlog, validate=False))
    events.sort(key=lambda e: e["block_number"])
    return events


def _windowed_borrow(events):
    blocks = [e["block_number"] for e in events]
    lo, hi = blocks[0], blocks[-1]
    out = []
    b = lo + _WINDOW
    while b <= hi:
        li = bisect.bisect_left(blocks, b - _WINDOW)
        ri = bisect.bisect_right(blocks, b)
        out.append((b, borrow_activity(events[li:ri])))
        b += _STRIDE
    return out


@pytest.fixture(scope="module")
def luna_windows():
    return _windowed_borrow(_load(LUNA_PATH))


@pytest.fixture(scope="module")
def normal_windows():
    return _windowed_borrow(_load(NORMAL_PATH))


def test_normal_control_sets_threshold(normal_windows):
    # The calm control has low borrow activity — this is the FP=0 threshold.
    assert max(v for _, v in normal_windows) <= 20


def test_luna_fires_red_before_cascade_with_zero_false_positives(
    luna_windows, normal_windows
):
    threshold = max(v for _, v in normal_windows)  # calm-control max → FP = 0%

    # False positives on the normal control must be zero at this threshold.
    fp = sum(1 for _, v in normal_windows if v > threshold)
    assert fp == 0

    # LUNA must fire (exceed threshold) in a window strictly before the cascade.
    fired_before = [blk for blk, v in luna_windows if v > threshold and blk < LUNA_CASCADE_BLOCK]
    assert fired_before, "B0 never fired before the LUNA cascade"

    # Lead time must clear the 10-minute (~50 block) Success-Signal deadline.
    first_fire_block = min(fired_before)
    assert first_fire_block <= LUNA_RED_DEADLINE_BLOCK
