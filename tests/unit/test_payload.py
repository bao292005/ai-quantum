"""Unit tests for emitter.payload + engine.baseline.fragility_score (Story 5.2)."""

from __future__ import annotations

import pytest

from core.schemas import validate_alert_payload
from emitter.payload import alert_level, format_alert
from engine.baseline import fragility_score


# ---------------------------------------------------------------------------
# B0 score mapping (calibration/luna_calibration.md — resolves code-review M2)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("rate", "expected"),
    [(16, 0.0), (24, 50.0), (28, 75.0), (32, 100.0), (8, 0.0), (40, 100.0)],
)
def test_fragility_score_mapping(rate, expected):
    assert fragility_score(rate) == expected


# ---------------------------------------------------------------------------
# alert_level thresholds (schema: YELLOW [70,90), RED [90,100])
# ---------------------------------------------------------------------------

def test_alert_level_boundaries():
    assert alert_level(69.99) is None
    assert alert_level(70.0) == "YELLOW"
    assert alert_level(89.99) == "YELLOW"
    assert alert_level(90.0) == "RED"
    assert alert_level(100.0) == "RED"


# ---------------------------------------------------------------------------
# format_alert (AC: score 92 -> RED payload, ISO-8601 Z, schema-valid)
# ---------------------------------------------------------------------------

def test_red_payload_matches_schema():
    p = format_alert(92.0, trigger_protocols=["aave_v3"])
    assert p["alert_level"] == "RED"
    assert p["fragility_score"] == 92.0
    assert p["timestamp"].endswith("Z")
    validate_alert_payload(p)  # raises if invalid


def test_yellow_payload_matches_schema():
    p = format_alert(75.42, trigger_protocols=["uniswap_v3", "aave_v3"])
    assert p["alert_level"] == "YELLOW"
    validate_alert_payload(p)


def test_score_rounded_to_two_decimals():
    p = format_alert(94.109, trigger_protocols=["aave_v3"])
    assert p["fragility_score"] == 94.11
    validate_alert_payload(p)


def test_explicit_timestamp_passthrough():
    p = format_alert(91.0, trigger_protocols=["aave_v3"], timestamp="2022-05-07T21:04:48Z")
    assert p["timestamp"] == "2022-05-07T21:04:48Z"


def test_below_yellow_threshold_raises():
    with pytest.raises(ValueError):
        format_alert(50.0, trigger_protocols=["aave_v3"])


def test_invalid_trigger_protocol_rejected():
    # aave_v2 is not in the payload enum (realtime scope is v3) -> schema rejects.
    with pytest.raises(Exception):
        format_alert(92.0, trigger_protocols=["aave_v2"])


def test_empty_trigger_protocols_rejected():
    with pytest.raises(Exception):
        format_alert(92.0, trigger_protocols=[])
