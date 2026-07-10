"""Unit tests for DequeRingBuffer (Story 1C.2)."""

import pytest

from core.ring_buffer import DequeRingBuffer, RingBufferProtocol


def _event(block: int, idx: int = 0) -> dict:
    """Minimal tick_data event dict for testing."""
    return {
        "block_number": block,
        "block_timestamp": "2023-10-24T12:00:00Z",
        "protocol": "uniswap_v3",
        "event_type": "swap",
        "pool_address": "0x" + "aa" * 20,
        "token0": "0x" + "bb" * 20,
        "token1": "0x" + "cc" * 20,
        "amount0": "1000",
        "amount1": "-500",
        "tx_hash": "0x" + "dd" * 32,
        "log_index": idx,
    }


def test_isinstance_protocol():
    assert isinstance(DequeRingBuffer(10), RingBufferProtocol)


def test_capacity():
    buf = DequeRingBuffer(50)
    assert buf.capacity == 50


def test_default_capacity():
    assert DequeRingBuffer().capacity == 1000


def test_write_and_read():
    buf = DequeRingBuffer(10)
    e = _event(100)
    buf.write(e)
    assert len(buf) == 1
    assert buf.read_all() == [e]


def test_len_increments_per_write():
    buf = DequeRingBuffer(10)
    for i in range(4):
        buf.write(_event(i))
        assert len(buf) == i + 1


def test_fifo_order():
    buf = DequeRingBuffer(10)
    events = [_event(i) for i in range(5)]
    for e in events:
        buf.write(e)
    result = buf.read_all()
    assert result == events  # oldest first


def test_eviction_at_capacity():
    capacity = 5
    buf = DequeRingBuffer(capacity)
    for i in range(capacity + 5):  # AC7: write capacity + 5 events
        buf.write(_event(i))
    assert len(buf) == capacity
    # Oldest events (0..4) should be evicted; newest capacity remain.
    block_numbers = [e["block_number"] for e in buf.read_all()]
    assert block_numbers == [5, 6, 7, 8, 9]


def test_read_latest_n_lt_len():
    buf = DequeRingBuffer(10)
    for i in range(5):
        buf.write(_event(i))
    latest = buf.read_latest(3)
    assert len(latest) == 3
    assert [e["block_number"] for e in latest] == [2, 3, 4]  # newest 3


def test_read_latest_n_eq_len():
    buf = DequeRingBuffer(10)
    events = [_event(i) for i in range(4)]
    for e in events:
        buf.write(e)
    assert buf.read_latest(4) == events


def test_read_latest_n_gt_len():
    buf = DequeRingBuffer(10)
    buf.write(_event(1))
    assert buf.read_latest(100) == [_event(1)]


def test_read_latest_zero():
    buf = DequeRingBuffer(10)
    buf.write(_event(1))
    assert buf.read_latest(0) == []


def test_invalid_capacity():
    with pytest.raises(ValueError):
        DequeRingBuffer(0)
