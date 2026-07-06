"""Unit tests for the tick-data JSON Schema (Story 0.1)."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import ValidationError

from core.schemas import load_tick_schema, validate_tick

EXAMPLES_DIR = Path(__file__).resolve().parents[2] / "contracts" / "examples"


def _load_example(name: str) -> dict:
    with (EXAMPLES_DIR / name).open("r", encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# Positive tests — 3 example files must validate.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "filename",
    [
        "tick_uniswap_swap.json",
        "tick_aave_borrow.json",
        "tick_aave_liquidation.json",
    ],
)
def test_example_validates(filename: str) -> None:
    event = _load_example(filename)
    validate_tick(event)  # must not raise


def test_load_tick_schema_returns_dict() -> None:
    schema = load_tick_schema()
    assert isinstance(schema, dict)
    assert schema["$id"] == "https://quantumradar.io/schemas/tick_data.schema.json"


# ---------------------------------------------------------------------------
# Negative tests — required by AC5.
# ---------------------------------------------------------------------------

def _valid_uniswap() -> dict:
    return _load_example("tick_uniswap_swap.json")


def test_missing_block_number() -> None:
    event = _valid_uniswap()
    del event["block_number"]
    with pytest.raises(ValidationError):
        validate_tick(event)


def test_wrong_protocol_event_combo() -> None:
    """protocol=uniswap_v3 with event_type=borrow must fail (AC3 cross-field)."""
    event = _valid_uniswap()
    event["event_type"] = "borrow"
    with pytest.raises(ValidationError):
        validate_tick(event)


def test_pool_address_not_hex() -> None:
    event = _valid_uniswap()
    event["pool_address"] = "not-an-address"
    with pytest.raises(ValidationError):
        validate_tick(event)


# ---------------------------------------------------------------------------
# Additional guardrail tests to keep the contract strict.
# ---------------------------------------------------------------------------

def test_additional_property_rejected() -> None:
    event = _valid_uniswap()
    event["extra_field"] = "surprise"
    with pytest.raises(ValidationError):
        validate_tick(event)


def test_amount_as_number_rejected() -> None:
    event = _valid_uniswap()
    event["amount0"] = 1234  # must be string to preserve precision
    with pytest.raises(ValidationError):
        validate_tick(event)


def test_timestamp_without_z_rejected() -> None:
    event = _valid_uniswap()
    event["block_timestamp"] = "2023-10-24T12:00:11"
    with pytest.raises(ValidationError):
        validate_tick(event)


def test_aave_liquidation_valid() -> None:
    event = _load_example("tick_aave_liquidation.json")
    validate_tick(event)


def test_aave_with_swap_event_rejected() -> None:
    """protocol=aave_v3 + event_type=swap must fail (AC3 reverse direction)."""
    event = _load_example("tick_aave_borrow.json")
    event["event_type"] = "swap"
    with pytest.raises(ValidationError):
        validate_tick(event)


def test_validator_is_cached_between_calls() -> None:
    """Two consecutive validations must reuse the same schema object (perf)."""
    ev1 = _valid_uniswap()
    ev2 = copy.deepcopy(ev1)
    validate_tick(ev1)
    validate_tick(ev2)
    assert load_tick_schema() is load_tick_schema()
