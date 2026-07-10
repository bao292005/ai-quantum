"""Ingestion heartbeat + stall metrics (Story 1A.5).

Exposes a Prometheus gauge, ``ingestion_ws_last_message_seconds``, tracking the
number of seconds since the last WebSocket message was received. Consumers call
:func:`record_message` on every block header (Story 1A.4's ``stream_new_heads``);
:func:`start_stall_watchdog` runs a background coroutine that refreshes the gauge
and logs a structured WARNING when the stream stalls past a threshold.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from wsgiref.simple_server import WSGIServer

from prometheus_client import Counter, Gauge, start_http_server

logger = logging.getLogger(__name__)

METRIC_NAME = "ingestion_ws_last_message_seconds"
_DEFAULT_THRESHOLD_S = 15.0
_DEFAULT_INTERVAL_S = 5.0

_GAUGE = Gauge(
    METRIC_NAME,
    "Seconds elapsed since the last WebSocket message was received",
)

# Pipeline throughput counters (Story 1E.1). Incremented by the orchestrator.
EVENTS_INGESTED = Counter(
    "events_ingested_total", "Normalized tick-data events written to the ring buffer"
)
BLOCKS_PROCESSED = Counter(
    "blocks_processed_total", "Block headers processed from the newHeads stream"
)

# Module-global heartbeat timestamp. Seeded at import so the gauge starts from a
# defined point rather than an unbounded "never seen a message" value.
_last_message_time: float = time.time()


def record_message() -> None:
    """Mark that a message just arrived: reset the heartbeat and the gauge to 0."""
    global _last_message_time
    _last_message_time = time.time()
    _GAUGE.set(0.0)


def seconds_since_last_message() -> float:
    """Seconds elapsed since the last :func:`record_message` call."""
    return time.time() - _last_message_time


def _check_stall(threshold_s: float) -> float:
    """Refresh the gauge and log a WARNING if the stream has stalled.

    Returns the elapsed seconds since the last message so callers/tests can
    assert on it without reaching into module globals.
    """
    elapsed = seconds_since_last_message()
    _GAUGE.set(elapsed)
    if elapsed > threshold_s:
        logger.warning(
            json.dumps(
                {
                    "event": "stream_stalled",
                    "seconds_since_last": round(elapsed, 1),
                    "threshold_s": threshold_s,
                }
            )
        )
    return elapsed


async def _watchdog_loop(threshold_s: float, interval_s: float) -> None:
    while True:
        await asyncio.sleep(interval_s)
        _check_stall(threshold_s)


def start_stall_watchdog(
    threshold_s: float = _DEFAULT_THRESHOLD_S,
    interval_s: float = _DEFAULT_INTERVAL_S,
) -> asyncio.Task:
    """Start the background stall watchdog and return its :class:`asyncio.Task`.

    Checks every ``interval_s`` seconds (default 5s) and warns when the stream
    has been silent for more than ``threshold_s`` seconds (default 15s). The
    heartbeat clock is (re)started here so a delay between import and the first
    message cannot trigger a spurious stall warning.

    The caller owns the returned task and must cancel it on shutdown.
    """
    global _last_message_time
    _last_message_time = time.time()
    return asyncio.create_task(_watchdog_loop(threshold_s, interval_s))


def start_metrics_server(
    port: int = 9090, addr: str = "127.0.0.1"
) -> tuple[WSGIServer, threading.Thread]:
    """Serve Prometheus metrics over HTTP at ``/metrics`` on ``port``.

    Binds to loopback by default (AC4: ``localhost:9090``); pass ``addr`` to
    opt into exposing the endpoint on other interfaces. Returns the
    ``(server, thread)`` pair from ``prometheus_client`` so the caller can shut
    the server down (used by tests and, later, the Epic 5 / pipeline lifecycle).
    """
    server, thread = start_http_server(port, addr=addr)
    logger.info(json.dumps({"event": "metrics_server_started", "port": port}))
    return server, thread
