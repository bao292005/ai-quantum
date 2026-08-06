"""Unit tests for emitter.pipeline.evaluate_and_emit (Story 6.1 orchestration)."""

from __future__ import annotations

from emitter.pipeline import evaluate_and_emit


async def test_red_window_formats_and_delivers():
    events = [{"event_type": "borrow"}] * 40  # score 100 -> RED
    seen: dict[str, bool] = {}

    async def poster(url):
        seen[url] = True
        return True

    score, level, results = await evaluate_and_emit(
        events, ["http://a", "http://b"], poster=poster
    )
    assert score == 100.0
    assert level == "RED"
    assert results == {"http://a": True, "http://b": True}
    assert seen == {"http://a": True, "http://b": True}


async def test_below_threshold_does_not_emit():
    events = [{"event_type": "borrow"}] * 10  # score 0 -> no alert
    called: list[str] = []

    async def poster(url):
        called.append(url)
        return True

    score, level, results = await evaluate_and_emit(
        events, ["http://a"], poster=poster
    )
    assert level is None
    assert results is None
    assert called == []  # emit never attempted below YELLOW


async def test_yellow_window_emits_yellow():
    events = [{"event_type": "borrow"}] * 28  # score 75 -> YELLOW
    async def poster(url):
        return True

    score, level, _ = await evaluate_and_emit(events, ["http://a"], poster=poster)
    assert level == "YELLOW"
