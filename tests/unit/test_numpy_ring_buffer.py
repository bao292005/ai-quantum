"""Unit tests for NumpyRingBuffer (Story 1C.3)."""

import pytest

from core.ring_buffer import DequeRingBuffer, NumpyRingBuffer, RingBufferProtocol


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
    assert isinstance(NumpyRingBuffer(10), RingBufferProtocol)


def test_capacity():
    assert NumpyRingBuffer(50).capacity == 50


def test_default_capacity():
    assert NumpyRingBuffer().capacity == 1000


def test_pre_allocation_shape():
    buf = NumpyRingBuffer(32)
    assert buf._buf.shape == (32,)


def test_write_and_read():
    buf = NumpyRingBuffer(10)
    e = _event(100)
    buf.write(e)
    assert len(buf) == 1
    assert buf.read_all() == [e]


def test_len_increments_per_write():
    buf = NumpyRingBuffer(10)
    for i in range(4):
        buf.write(_event(i))
        assert len(buf) == i + 1


def test_fifo_order_not_full():
    buf = NumpyRingBuffer(10)
    events = [_event(i) for i in range(5)]
    for e in events:
        buf.write(e)
    assert buf.read_all() == events  # oldest first


def test_eviction_at_capacity():
    capacity = 5
    buf = NumpyRingBuffer(capacity)
    for i in range(capacity + 3):
        buf.write(_event(i))
    assert len(buf) == capacity
    block_numbers = [e["block_number"] for e in buf.read_all()]
    assert block_numbers == [3, 4, 5, 6, 7]


def test_read_all_wraparound():
    # capacity=5, write 7 events -> FIFO [2,3,4,5,6]
    buf = NumpyRingBuffer(5)
    for i in range(7):
        buf.write(_event(i))
    assert [e["block_number"] for e in buf.read_all()] == [2, 3, 4, 5, 6]


def test_read_latest_n_lt_len():
    buf = NumpyRingBuffer(10)
    for i in range(5):
        buf.write(_event(i))
    latest = buf.read_latest(3)
    assert [e["block_number"] for e in latest] == [2, 3, 4]


def test_read_latest_n_eq_len():
    buf = NumpyRingBuffer(10)
    events = [_event(i) for i in range(4)]
    for e in events:
        buf.write(e)
    assert buf.read_latest(4) == events


def test_read_latest_n_gt_len():
    buf = NumpyRingBuffer(10)
    buf.write(_event(1))
    assert buf.read_latest(100) == [_event(1)]


def test_read_latest_zero():
    buf = NumpyRingBuffer(10)
    buf.write(_event(1))
    assert buf.read_latest(0) == []


def test_read_all_empty():
    assert NumpyRingBuffer(10).read_all() == []


def test_invalid_capacity():
    with pytest.raises(ValueError):
        NumpyRingBuffer(0)


def test_behavioral_equivalence():
    """NumpyRingBuffer must produce same results as DequeRingBuffer."""
    capacity = 7
    deque_buf = DequeRingBuffer(capacity)
    numpy_buf = NumpyRingBuffer(capacity)

    events = [{"block_number": i, "log_index": i} for i in range(capacity + 5)]
    for e in events:
        deque_buf.write(e)
        numpy_buf.write(e)

    assert deque_buf.read_all() == numpy_buf.read_all()
    assert deque_buf.read_latest(3) == numpy_buf.read_latest(3)
    assert len(deque_buf) == len(numpy_buf)
