"""Unit tests for AsyncRingBuffer (Story 1C.4)."""

import asyncio

import pytest

from core.ring_buffer import (
    AsyncRingBuffer,
    AsyncRingBufferProtocol,
    DequeRingBuffer,
    NumpyRingBuffer,
    RingBufferProtocol,
)


def _event(i: int) -> dict:
    return {
        "block_number": i,
        "log_index": i,
        "protocol": "uniswap_v3",
        "event_type": "swap",
        "pool_address": "0x" + "aa" * 20,
        "token0": "0x" + "bb" * 20,
        "token1": "0x" + "cc" * 20,
        "amount0": "100",
        "amount1": "-50",
        "tx_hash": "0x" + "dd" * 32,
        "block_timestamp": "2023-10-24T12:00:00Z",
    }


async def test_write_and_read():
    buf = AsyncRingBuffer(DequeRingBuffer(100))
    e = _event(1)
    await buf.write(e)
    result = await buf.read_all()
    assert result == [e]


async def test_concurrent_writes():
    """AC6: 10 coroutines write 100 events each = 1000 total.

    capacity=1000 so len == min(capacity, 1000) == 1000, no lost writes.
    """
    capacity = 1000
    buf = AsyncRingBuffer(DequeRingBuffer(capacity))

    async def writer(start: int):
        for i in range(100):
            await buf.write(_event(start + i))

    await asyncio.gather(*[writer(i * 100) for i in range(10)])
    assert len(buf) == min(capacity, 1000) == 1000


async def test_concurrent_writes_evict_at_capacity():
    """AC6 variant: 1000 concurrent writes into capacity=500 -> len == 500."""
    capacity = 500
    buf = AsyncRingBuffer(DequeRingBuffer(capacity))

    async def writer(start: int):
        for i in range(100):
            await buf.write(_event(start + i))

    await asyncio.gather(*[writer(i * 100) for i in range(10)])
    assert len(buf) == min(capacity, 1000) == 500


async def test_eviction_concurrent():
    """100 events into capacity=50 -> exactly 50 remain."""
    buf = AsyncRingBuffer(DequeRingBuffer(50))
    await asyncio.gather(*[buf.write(_event(i)) for i in range(100)])
    assert len(buf) == 50


async def test_read_latest():
    buf = AsyncRingBuffer(DequeRingBuffer(100))
    for i in range(10):
        await buf.write(_event(i))
    latest = await buf.read_latest(3)
    assert len(latest) == 3
    assert latest[-1]["block_number"] == 9  # newest


async def test_snapshot_context_manager():
    buf = AsyncRingBuffer(DequeRingBuffer(10))
    for i in range(5):
        await buf.write(_event(i))
    async with buf.snapshot() as events:
        assert len(events) == 5
        assert events[0]["block_number"] == 0


async def test_capacity_passthrough():
    buf = AsyncRingBuffer(NumpyRingBuffer(42))
    assert buf.capacity == 42


async def test_len_passthrough():
    buf = AsyncRingBuffer(DequeRingBuffer(100))
    await buf.write(_event(1))
    assert len(buf) == 1


async def test_works_with_numpy_backend():
    buf = AsyncRingBuffer(NumpyRingBuffer(100))
    for i in range(20):
        await buf.write(_event(i))
    result = await buf.read_all()
    assert len(result) == 20
    assert result[0]["block_number"] == 0  # FIFO order preserved


async def test_backend_is_protocol():
    # The wrapped backend satisfies the sync RingBufferProtocol. Note:
    # AsyncRingBuffer's own methods are async, so despite structurally sharing
    # the same attribute names, callers must await them — do not treat an
    # AsyncRingBuffer as a drop-in sync RingBufferProtocol.
    buf = AsyncRingBuffer(DequeRingBuffer(10))
    assert isinstance(buf._backend, RingBufferProtocol)


async def test_satisfies_async_protocol():
    # AsyncRingBuffer is the canonical AsyncRingBufferProtocol implementation.
    buf = AsyncRingBuffer(DequeRingBuffer(10))
    assert isinstance(buf, AsyncRingBufferProtocol)


async def test_rejects_async_backend():
    # Wrapping an async buffer would silently drop writes (un-awaited coroutine),
    # so the constructor rejects it.
    inner = AsyncRingBuffer(DequeRingBuffer(10))
    with pytest.raises(TypeError):
        AsyncRingBuffer(inner)


async def test_lock_serializes_write_and_snapshot():
    """A held snapshot lock must block a concurrent write until released.

    Verifies mutual exclusion: while inside snapshot(), a write scheduled
    concurrently cannot land until the snapshot context exits.
    """
    buf = AsyncRingBuffer(DequeRingBuffer(10))
    await buf.write(_event(0))

    order: list[str] = []

    async def writer():
        # Give the snapshot a chance to acquire the lock first.
        await asyncio.sleep(0.01)
        await buf.write(_event(99))
        order.append("write-done")

    async def reader():
        async with buf.snapshot() as events:
            order.append("snapshot-enter")
            # Hold the lock while the writer is blocked on it.
            await asyncio.sleep(0.05)
            # Write must NOT have landed while we hold the lock.
            assert len(events) == 1
            order.append("snapshot-exit")

    await asyncio.gather(reader(), writer())
    # snapshot fully completed before the blocked write finished.
    assert order == ["snapshot-enter", "snapshot-exit", "write-done"]
    assert len(buf) == 2
