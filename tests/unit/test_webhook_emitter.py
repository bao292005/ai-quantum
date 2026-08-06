"""Unit tests for emitter.webhook (Story 5.3).

The delivery orchestration (parallel fan-out + 1 retry + ERROR log) is tested with
an injected ``poster`` coroutine so no network/extra deps are needed; aiohttp is
the default transport.
"""

from __future__ import annotations

import asyncio

from emitter.webhook import emit

_PAYLOAD = {"timestamp": "2022-05-07T21:04:48Z", "fragility_score": 92.0,
            "alert_level": "RED", "trigger_protocols": ["aave_v3"]}


async def test_healthy_and_timeout_mixed():
    healthy = [f"http://h{i}" for i in range(5)]
    bad = [f"http://b{i}" for i in range(5)]
    calls: dict[str, int] = {}

    async def poster(url):
        calls[url] = calls.get(url, 0) + 1
        if url.startswith("http://b"):
            raise asyncio.TimeoutError()
        return True

    results = await emit(_PAYLOAD, healthy + bad, poster=poster, retries=1)

    assert all(results[u] for u in healthy)          # healthy delivered
    assert not any(results[u] for u in bad)          # timeouts failed
    assert all(calls[u] == 1 for u in healthy)       # no retry for healthy
    assert all(calls[u] == 2 for u in bad)           # 1 retry => 2 attempts


async def test_one_slow_subscriber_does_not_block_others():
    async def poster(url):
        if url == "http://slow":
            await asyncio.sleep(0.2)
            raise asyncio.TimeoutError()
        return True

    start = asyncio.get_event_loop().time()
    results = await emit(_PAYLOAD, ["http://fast", "http://slow"], poster=poster, retries=0)
    elapsed = asyncio.get_event_loop().time() - start

    assert results["http://fast"] is True
    assert results["http://slow"] is False
    # fan-out is parallel: total time ~ the slow one, not the sum.
    assert elapsed < 0.5


async def test_non_2xx_status_counts_as_failure():
    async def poster(url):
        return False  # e.g. HTTP 500

    results = await emit(_PAYLOAD, ["http://x"], poster=poster, retries=1)
    assert results["http://x"] is False


async def test_empty_subscribers_returns_empty():
    async def poster(url):
        return True

    assert await emit(_PAYLOAD, [], poster=poster) == {}
