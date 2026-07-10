import inspect
import pytest

from typing import Protocol

from core.ring_buffer import AsyncRingBuffer, AsyncRingBufferProtocol, DequeRingBuffer, RingBufferProtocol


class _ConformingBuffer:
    """A minimal structural implementation of the protocol (no explicit
    inheritance) — used to prove duck-typing works (AC3)."""

    def __init__(self, capacity: int = 10) -> None:
        self._cap = capacity
        self._data: list[dict] = []

    @property
    def capacity(self) -> int:
        return self._cap

    def write(self, event: dict) -> None:
        self._data.append(event)

    def read_all(self) -> list[dict]:
        return list(self._data)

    def read_latest(self, n: int) -> list[dict]:
        return self._data[-n:] if n > 0 else []

    def __len__(self) -> int:
        return len(self._data)


class _MissingMethods:
    """Implements only some of the protocol — must NOT satisfy isinstance."""

    def write(self, event: dict) -> None:
        pass


def test_protocol_is_runtime_checkable():
    # @runtime_checkable sets this flag; without it isinstance() would raise.
    assert getattr(RingBufferProtocol, "_is_runtime_protocol", False) is True


def test_conforming_class_is_instance_via_duck_typing():
    # AC3: structural typing — no explicit inheritance required.
    assert isinstance(_ConformingBuffer(10), RingBufferProtocol)


def test_non_conforming_class_is_not_instance():
    assert not isinstance(_MissingMethods(), RingBufferProtocol)


def test_protocol_declares_all_required_members():
    for name in ("capacity", "write", "read_all", "read_latest", "__len__"):
        assert name in RingBufferProtocol.__protocol_attrs__, name


def test_method_signatures_are_correct():
    assert list(inspect.signature(RingBufferProtocol.write).parameters) == ["self", "event"]
    assert list(inspect.signature(RingBufferProtocol.read_all).parameters) == ["self"]
    assert list(inspect.signature(RingBufferProtocol.read_latest).parameters) == ["self", "n"]
    assert list(inspect.signature(RingBufferProtocol.__len__).parameters) == ["self"]
    # capacity is a read-only property → inspect its getter.
    assert isinstance(RingBufferProtocol.capacity, property)
    assert list(inspect.signature(RingBufferProtocol.capacity.fget).parameters) == ["self"]


def test_is_a_typing_protocol():
    assert issubclass(RingBufferProtocol, Protocol)


# ---------------------------------------------------------------------------
# AC4 (BH-05): real DequeRingBuffer must satisfy the protocol (1C.2 is done).
# ---------------------------------------------------------------------------

def test_deque_ring_buffer_is_protocol_instance():
    """AC4: isinstance(DequeRingBuffer(10), RingBufferProtocol) → True."""
    assert isinstance(DequeRingBuffer(10), RingBufferProtocol)


# ---------------------------------------------------------------------------
# BH-07: AsyncRingBufferProtocol runtime-checkable + AsyncRingBuffer isinstance.
# ---------------------------------------------------------------------------

def test_async_ring_buffer_protocol_is_runtime_checkable():
    assert getattr(AsyncRingBufferProtocol, "_is_runtime_protocol", False) is True


def test_async_ring_buffer_is_async_protocol_instance():
    """AsyncRingBuffer must satisfy AsyncRingBufferProtocol (all attrs present)."""
    buf = AsyncRingBuffer(DequeRingBuffer(10))
    assert isinstance(buf, AsyncRingBufferProtocol)


# ---------------------------------------------------------------------------
# BH-09: AsyncRingBuffer rejects backends with no .write attribute.
# ---------------------------------------------------------------------------

def test_async_ring_buffer_rejects_backend_without_write():
    """Passing a completely wrong type should raise TypeError, not AttributeError."""

    class _BadBackend:
        capacity = 10

        def read_all(self):
            return []

        def read_latest(self, n):
            return []

        def __len__(self):
            return 0

    with pytest.raises(TypeError, match="write"):
        AsyncRingBuffer(_BadBackend())  # type: ignore[arg-type]
