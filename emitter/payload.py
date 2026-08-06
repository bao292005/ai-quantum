"""Fragility-alert payload formatter (Story 5.2).

Turns a ``fragility_score`` (0–100, produced by the calibrated B0 mapping
``engine.baseline.fragility_score``) into a webhook payload conforming to
``contracts/fragility_alert.schema.json`` (Story 0.3). Every payload is validated
against the schema before it is returned, so the emitter (5.3) can never send a
malformed body.

Alert bands (from the schema): ``YELLOW`` for ``70 ≤ score < 90``, ``RED`` for
``90 ≤ score ≤ 100``. Below 70 there is no payload (GREEN is intentionally not
emitted).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone

from core.schemas import validate_alert_payload

_YELLOW_MIN = 70.0
_RED_MIN = 90.0


def alert_level(score: float) -> str | None:
    """Return ``"RED"``, ``"YELLOW"``, or ``None`` (below the YELLOW threshold)."""
    if score >= _RED_MIN:
        return "RED"
    if score >= _YELLOW_MIN:
        return "YELLOW"
    return None


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def format_alert(
    score: float,
    *,
    trigger_protocols: Sequence[str],
    timestamp: str | None = None,
) -> dict:
    """Build a schema-valid ``FragilityAlert`` payload from a fragility score.

    Args:
        score: fragility score in ``[0, 100]`` (values are rounded to 2 decimals
            to satisfy the schema's ``multipleOf 0.01``).
        trigger_protocols: non-empty list of protocols
            (``uniswap_v3`` / ``aave_v3``) that triggered the alert.
        timestamp: ISO-8601 UTC string ending in ``Z``; defaults to now.

    Returns:
        The validated payload dict.

    Raises:
        ValueError: if ``score`` is below the YELLOW threshold (no alert emitted).
        jsonschema.ValidationError: if the resulting payload violates the schema
            (e.g. an out-of-enum protocol or an empty ``trigger_protocols``).
    """
    # Round first, then classify — so a score like 89.999 that rounds to 90.00
    # is labelled RED, keeping the level and the band-checked score consistent.
    rounded = round(float(score), 2)
    level = alert_level(rounded)
    if level is None:
        raise ValueError(
            f"score {rounded} is below the YELLOW threshold ({_YELLOW_MIN}); "
            "no payload is emitted"
        )

    payload = {
        "timestamp": timestamp or _now_iso(),
        "fragility_score": rounded,
        "alert_level": level,
        "trigger_protocols": list(trigger_protocols),
    }
    validate_alert_payload(payload)
    return payload


__all__ = ["alert_level", "format_alert"]
