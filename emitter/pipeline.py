"""Detector → payload → emit orchestration step (Story 6.1 wiring).

Bridges the v1 B0 detector to the alert emitter: score a window of events, and if
it crosses the YELLOW threshold, format a schema-valid payload and fan it out to
subscribers. This is the per-block hot path the E2E latency benchmark measures
(``tests/bench_e2e.py``) and the seam a realtime orchestrator (Epic 1E.1) plugs
into.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

from emitter.payload import alert_level, format_alert
from emitter.webhook import emit
from engine.baseline import borrow_activity, fragility_score

_DEFAULT_TRIGGERS = ("aave_v3",)


async def evaluate_and_emit(
    events: Iterable[dict[str, Any]],
    subscribers: Sequence[str],
    *,
    trigger_protocols: Sequence[str] = _DEFAULT_TRIGGERS,
    timestamp: str | None = None,
    poster=None,
) -> tuple[float, str | None, dict[str, bool] | None]:
    """Score ``events`` (B0) and emit an alert if it reaches YELLOW/RED.

    Returns ``(fragility_score, alert_level, delivery_results)``. When the score
    is below the YELLOW threshold, no payload is built or sent and
    ``(score, None, None)`` is returned.
    """
    score = fragility_score(borrow_activity(events))
    level = alert_level(score)
    if level is None:
        return score, None, None

    payload = format_alert(
        score, trigger_protocols=list(trigger_protocols), timestamp=timestamp
    )
    results = await emit(payload, subscribers, poster=poster)
    return score, level, results


__all__ = ["evaluate_and_emit"]
