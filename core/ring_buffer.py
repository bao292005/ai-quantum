"""Ring buffer interface for the ingestion hot path (Story 1C.1).

`RingBufferProtocol` is the structural contract every ring-buffer implementation
must satisfy so downstream consumers (Epic 2 GraphBuilder, Story 1E.1 pipeline)
depend on the interface, not a concrete class.

Implementations (later stories):
- ``DequeRingBuffer``  (1C.2): ``collections.deque`` — simple, GIL-protected.
- ``NumpyRingBuffer``  (1C.3): pre-allocated numpy array — O(1) circular write.
- ``AsyncRingBuffer``  (1C.4): ``asyncio.Lock`` wrapper around any implementation.

Each ``event`` is a ``dict`` conforming to ``tick_data.schema.json``
(``TickDataEvent.to_dict()`` output from Track 1B).
"""

from __future__ import annotations

import asyncio
from collections import deque
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Protocol, runtime_checkable

# pyrefly: ignore [missing-import]
import numpy as np 


# numpy is imported lazily inside NumpyRingBuffer.__init__ so that this module
# can be imported in environments where numpy is not installed (e.g. lightweight
# workers that only need RingBufferProtocol or DequeRingBuffer).


@runtime_checkable
class RingBufferProtocol(Protocol):
    """Structural interface for a fixed-capacity FIFO ring buffer of events."""

    @property
    def capacity(self) -> int:
        """Maximum number of events the buffer can hold."""
        ...

    def write(self, event: dict) -> None:
        """Insert ``event``. If the buffer is full, silently evict the oldest."""
        ...

    def read_all(self) -> list[dict]:
        """Return all events in FIFO order (oldest first, newest last)."""
        ...

    def read_latest(self, n: int) -> list[dict]:
        """Return the ``n`` most recent events (newest last).

        If ``n`` exceeds the current size, return all events.
        """
        ...

    def __len__(self) -> int:
        """Current number of events in the buffer."""
        ...


@runtime_checkable
class AsyncRingBufferProtocol(Protocol):
    """Async structural contract for lock-protected ring buffers (Story 1C.4).

    This is the canonical interface for the async pipeline; type async consumers
    against it rather than ``RingBufferProtocol``.

    CAVEAT: ``@runtime_checkable`` verifies only attribute *names*, not that
    ``write``/``read_all``/``read_latest`` are coroutines. A synchronous
    ``RingBufferProtocol`` implementation therefore also structurally satisfies
    this protocol at runtime (and ``AsyncRingBuffer`` structurally satisfies the
    sync protocol too). Do NOT rely on ``isinstance`` to distinguish sync vs
    async buffers — use these protocols for static typing only.
    """

    @property
    def capacity(self) -> int:
        """Maximum number of events the buffer can hold."""
        ...

    async def write(self, event: dict) -> None:
        """Insert ``event``. If the buffer is full, silently evict the oldest."""
        ...

    async def read_all(self) -> list[dict]:
        """Return all events in FIFO order (oldest first, newest last)."""
        ...

    async def read_latest(self, n: int) -> list[dict]:
        """Return the ``n`` most recent events (newest last)."""
        ...

    def __len__(self) -> int:
        """Current number of events in the buffer."""
        ...


class DequeRingBuffer:
    """Ring buffer backed by ``collections.deque`` (Story 1C.2).

    GIL-protected for the single-threaded asyncio pipeline. Auto-evicts the
    oldest event in O(1) when ``capacity`` is reached, via ``deque(maxlen=...)``.

    Events are stored **by reference**: callers must treat stored events as
    immutable. Mutating a ``dict`` after passing it to ``write()`` (or mutating
    a dict returned by ``read_all``/``read_latest``) aliases the buffer's
    contents.
    """

    def __init__(self, capacity: int = 1000) -> None:
        if capacity <= 0:
            raise ValueError(f"capacity must be > 0, got {capacity}")
        self._buf: deque[dict] = deque(maxlen=capacity)

    @property
    def capacity(self) -> int:
        """Maximum number of events the buffer can hold."""
        return self._buf.maxlen  # type: ignore[return-value]

    def write(self, event: dict) -> None:
        """O(1) insert. Oldest event evicted automatically when full."""
        self._buf.append(event)

    def read_all(self) -> list[dict]:
        """Return all events in FIFO order (oldest first, newest last)."""
        return list(self._buf)

    def read_latest(self, n: int) -> list[dict]:
        """Return the ``n`` most recent events (newest last).

        Returns all events if ``n`` exceeds the current size, and an empty
        list if ``n <= 0``.
        """
        if n <= 0:
            return []
        return list(self._buf)[-n:]

    def __len__(self) -> int:
        return len(self._buf)


class NumpyRingBuffer:
    """Ring buffer backed by a pre-allocated numpy object array (Story 1C.3).

    Uses a circular write head — O(1) write with fixed memory allocated at
    construction (no GC pressure from dynamic resizing). Behavioral equivalent
    to ``DequeRingBuffer``; useful for benchmarking.

    Events are stored **by reference** (same contract as ``DequeRingBuffer``):
    callers must treat stored events as immutable.
    """

    def __init__(self, capacity: int = 1000) -> None:
        if capacity <= 0:
            raise ValueError(f"capacity must be > 0, got {capacity}")
        self._capacity = capacity
        self._buf = np.empty(capacity, dtype=object)
        self._head: int = 0  # next write position (absolute, wraps modulo capacity)
        self._size: int = 0  # current number of valid events

    @property
    def capacity(self) -> int:
        """Maximum number of events the buffer can hold."""
        return self._capacity

    def write(self, event: dict) -> None:
        """O(1) circular write. Overwrites the oldest slot when full."""
        self._buf[self._head % self._capacity] = event
        self._head += 1
        if self._size < self._capacity:
            self._size += 1

    def read_all(self) -> list[dict]:
        """Return all events in FIFO order (oldest first, newest last)."""
        if self._size == 0:
            return []
        if self._size < self._capacity:
            # Not yet wrapped — slots 0.._size-1 are already in order.
            return list(self._buf[: self._size])
        # Full buffer — oldest slot is at _head % capacity, walk forward wrapping.
        start = self._head % self._capacity
        return [self._buf[(start + i) % self._capacity] for i in range(self._capacity)]

    def read_latest(self, n: int) -> list[dict]:
        """Return the ``n`` most recent events (newest last).

        Returns all events if ``n`` exceeds the current size, and an empty
        list if ``n <= 0``.
        """
        if n <= 0:
            return []
        all_events = self.read_all()
        return all_events[-n:] if n < len(all_events) else all_events

    def __len__(self) -> int:
        return self._size


class AsyncRingBuffer:
    """``asyncio.Lock``-protected wrapper around any ``RingBufferProtocol``.

    Implements ``AsyncRingBufferProtocol`` (the canonical async contract). Single
    lock per instance; writers and readers contend. For the QuantumRadar pipeline
    (single asyncio event loop, ~100 events/sec) contention is negligible.
    ``capacity`` and ``len()`` are atomic int reads and skip the lock.

    The ``backend`` must be a *synchronous* ``RingBufferProtocol`` (e.g.
    ``DequeRingBuffer``, ``NumpyRingBuffer``). Passing an async buffer such as
    another ``AsyncRingBuffer`` is rejected — its ``write`` returns an un-awaited
    coroutine, which would silently drop events.
    """

    def __init__(self, backend: RingBufferProtocol) -> None:
        write_fn = getattr(backend, "write", None)
        if write_fn is None:
            raise TypeError(
                f"{type(backend).__name__!r} has no 'write' attribute; "
                "backend must be a synchronous RingBufferProtocol."
            )
        if asyncio.iscoroutinefunction(write_fn):
            raise TypeError(
                "backend must be a synchronous RingBufferProtocol; got an async "
                f"buffer ({type(backend).__name__}). Wrapping an async backend "
                "would drop writes (un-awaited coroutine)."
            )
        self._backend = backend
        self._lock = asyncio.Lock()

    @property
    def capacity(self) -> int:
        """Backend capacity (atomic int read — no lock needed)."""
        return self._backend.capacity

    async def write(self, event: dict) -> None:
        """Acquire the lock and write to the backend."""
        async with self._lock:
            self._backend.write(event)

    async def read_all(self) -> list[dict]:
        """Acquire the lock and return all events in FIFO order."""
        async with self._lock:
            return self._backend.read_all()

    async def read_latest(self, n: int) -> list[dict]:
        """Acquire the lock and return the ``n`` most recent events."""
        async with self._lock:
            return self._backend.read_latest(n)

    def __len__(self) -> int:
        return len(self._backend)  # atomic int read — no lock needed

    @asynccontextmanager
    async def snapshot(self) -> AsyncGenerator[list[dict], None]:
        """Hold the lock for the entire read, yielding a consistent snapshot.

        Prevents writes from interleaving while the caller processes events::

            async with buf.snapshot() as events:
                result = graph_builder.build(events)
        """
        async with self._lock:
            yield self._backend.read_all()
