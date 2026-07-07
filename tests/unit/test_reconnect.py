import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from ingestion.reconnect import auto_reconnect


async def test_success_no_retry():
    """AC5 — coroutine succeeds immediately: called once, no sleep."""
    mock_fn = AsyncMock(return_value="ok")
    decorated = auto_reconnect()(mock_fn)

    with patch("ingestion.reconnect.asyncio.sleep", AsyncMock()) as mock_sleep:
        result = await decorated()

    assert result == "ok"
    mock_fn.assert_called_once()
    mock_sleep.assert_not_called()


async def test_fail_then_succeed():
    """AC6 — fail 3 times then succeed: called exactly 4 times."""
    call_count = 0

    async def flaky():
        nonlocal call_count
        call_count += 1
        if call_count < 4:
            raise ConnectionError("drop")
        return "recovered"

    decorated = auto_reconnect()(flaky)
    with patch("ingestion.reconnect.asyncio.sleep", AsyncMock()):
        result = await decorated()

    assert result == "recovered"
    assert call_count == 4


async def test_delay_sequence():
    """AC2 — delay sequence: 0.5 → 1.0 → 2.0 for 3 retries."""
    delays = []

    async def always_fail():
        raise ConnectionError("fail")

    async def capture_sleep(delay):
        delays.append(delay)

    decorated = auto_reconnect(max_retries=3, base=0.5, cap=30)(always_fail)
    with patch("ingestion.reconnect.asyncio.sleep", capture_sleep):
        with pytest.raises(ConnectionError):
            await decorated()

    assert delays == [0.5, 1.0, 2.0]


async def test_delay_cap():
    """AC2 — delay caps at 30s."""
    delays = []

    async def always_fail():
        raise ConnectionError("fail")

    async def capture_sleep(delay):
        delays.append(delay)

    # 8 retries to hit cap: 0.5→1→2→4→8→16→30→30
    decorated = auto_reconnect(max_retries=8, base=0.5, cap=30)(always_fail)
    with patch("ingestion.reconnect.asyncio.sleep", capture_sleep):
        with pytest.raises(ConnectionError):
            await decorated()

    assert delays[6] == 30.0  # attempt 6 hits cap
    assert delays[7] == 30.0  # stays capped


async def test_max_retries_raises_after_limit():
    """AC3 — max_retries=2: raise original exception after 2 failures."""
    call_count = 0

    async def always_fail():
        nonlocal call_count
        call_count += 1
        raise ConnectionError("always down")

    decorated = auto_reconnect(max_retries=2)(always_fail)
    with patch("ingestion.reconnect.asyncio.sleep", AsyncMock()):
        with pytest.raises(ConnectionError, match="always down"):
            await decorated()

    assert call_count == 3  # initial + 2 retries


async def test_max_retries_none_retries_indefinitely():
    """AC3 — max_retries=None: retry until success."""
    call_count = 0

    async def eventually_ok():
        nonlocal call_count
        call_count += 1
        if call_count < 10:
            raise ConnectionError("not yet")
        return "done"

    decorated = auto_reconnect(max_retries=None)(eventually_ok)
    with patch("ingestion.reconnect.asyncio.sleep", AsyncMock()):
        result = await decorated()

    assert result == "done"
    assert call_count == 10


async def test_non_reconnect_exception_propagates_immediately():
    """Non-connection exceptions should propagate without retry."""
    call_count = 0

    async def bad_logic():
        nonlocal call_count
        call_count += 1
        raise ValueError("programming error")

    decorated = auto_reconnect()(bad_logic)
    with patch("ingestion.reconnect.asyncio.sleep", AsyncMock()) as mock_sleep:
        with pytest.raises(ValueError):
            await decorated()

    assert call_count == 1
    mock_sleep.assert_not_called()


async def test_log_emitted_on_retry(caplog):
    """AC4 — structured JSON log emitted on each retry."""
    import logging

    call_count = 0

    async def flaky():
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise ConnectionError("boom")

    decorated = auto_reconnect()(flaky)
    with patch("ingestion.reconnect.asyncio.sleep", AsyncMock()):
        with caplog.at_level(logging.WARNING, logger="ingestion.reconnect"):
            await decorated()

    assert any("reconnect" in record.message for record in caplog.records)
