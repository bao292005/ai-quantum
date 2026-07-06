"""Unit tests for the fragility-alert webhook payload schema (Story 0.3)."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import ValidationError

from core.schemas import load_alert_schema, validate_alert_payload

EXAMPLES_DIR = Path(__file__).resolve().parents[2] / "contracts" / "examples"
YELLOW_PATH = EXAMPLES_DIR / "payload_yellow.json"
RED_PATH = EXAMPLES_DIR / "payload_red.json"


def _load(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# Positive tests (AC5)
# ---------------------------------------------------------------------------

def test_yellow_example_validates() -> None:
    validate_alert_payload(_load(YELLOW_PATH))


def test_red_example_validates() -> None:
    validate_alert_payload(_load(RED_PATH))


def test_load_alert_schema_returns_dict() -> None:
    schema = load_alert_schema()
    assert isinstance(schema, dict)
    assert schema["$id"] == "https://quantumradar.io/schemas/fragility_alert.schema.json"
    assert schema["required"] == [
        "timestamp",
        "fragility_score",
        "alert_level",
        "trigger_protocols",
    ]


# ---------------------------------------------------------------------------
# Negative tests (AC5) — 4 required-field removals + 1 cross-field + 1 minItems
# ---------------------------------------------------------------------------

@pytest.fixture
def yellow() -> dict:
    return copy.deepcopy(_load(YELLOW_PATH))


@pytest.mark.parametrize(
    "field",
    ["timestamp", "fragility_score", "alert_level", "trigger_protocols"],
)
def test_missing_required_field_rejected(yellow: dict, field: str) -> None:
    del yellow[field]
    with pytest.raises(ValidationError):
        validate_alert_payload(yellow)


def test_yellow_level_with_red_score_rejected(yellow: dict) -> None:
    """alert_level=YELLOW but fragility_score=95 must fail (cross-field)."""
    yellow["fragility_score"] = 95.0
    with pytest.raises(ValidationError):
        validate_alert_payload(yellow)


def test_empty_trigger_protocols_rejected(yellow: dict) -> None:
    yellow["trigger_protocols"] = []
    with pytest.raises(ValidationError):
        validate_alert_payload(yellow)


# ---------------------------------------------------------------------------
# Guardrail tests
# ---------------------------------------------------------------------------

def test_red_level_with_low_score_rejected(yellow: dict) -> None:
    yellow["alert_level"] = "RED"
    yellow["fragility_score"] = 80.0
    with pytest.raises(ValidationError):
        validate_alert_payload(yellow)


def test_score_above_100_rejected(yellow: dict) -> None:
    yellow["fragility_score"] = 100.5
    with pytest.raises(ValidationError):
        validate_alert_payload(yellow)


def test_score_more_than_two_decimals_rejected(yellow: dict) -> None:
    yellow["fragility_score"] = 75.123
    with pytest.raises(ValidationError):
        validate_alert_payload(yellow)


def test_lowercase_alert_level_rejected(yellow: dict) -> None:
    yellow["alert_level"] = "yellow"
    with pytest.raises(ValidationError):
        validate_alert_payload(yellow)


def test_green_level_rejected(yellow: dict) -> None:
    yellow["alert_level"] = "GREEN"
    with pytest.raises(ValidationError):
        validate_alert_payload(yellow)


def test_unknown_protocol_rejected(yellow: dict) -> None:
    yellow["trigger_protocols"] = ["compound_v3"]
    with pytest.raises(ValidationError):
        validate_alert_payload(yellow)


def test_duplicate_protocols_rejected(yellow: dict) -> None:
    yellow["trigger_protocols"] = ["uniswap_v3", "uniswap_v3"]
    with pytest.raises(ValidationError):
        validate_alert_payload(yellow)


def test_additional_property_rejected(yellow: dict) -> None:
    yellow["explanation"] = "flash-crash on ETH pool"
    with pytest.raises(ValidationError):
        validate_alert_payload(yellow)


def test_timestamp_without_z_rejected(yellow: dict) -> None:
    yellow["timestamp"] = "2026-07-05T18:15:00"
    with pytest.raises(ValidationError):
        validate_alert_payload(yellow)
