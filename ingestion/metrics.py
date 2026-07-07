from __future__ import annotations

import asyncio
import json
import logging
import time

from prometheus_client import Gauge, REGISTRY, start_http_server

logger = logging.getLogger(__name__)

METRIC_NAME = "ingestion_ws_last_message_seconds"
_WATCHDOG_INTERVAL_S = 5.0


def _build_gauge() -> Gauge:
    try:
        return Gauge(
            METRIC_NAME,
            "Seconds elapsed since the last WebSocket message was received",
        )
    except ValueError:
        existing = getattr(REGISTRY, "_names_to_collectors", {}).get(METRIC_NAME)
        if existing is not None:
            return existing
        raise


_GAUGE = _build_gauge()
_last_message_time: float = time.time()


def record_message() -> None:
    global _last_message_time

    _last_message_time = time.time()
    _GAUGE.set(0.0)


def start_stall_watchdog(threshold_s: float = 15) -> asyncio.Task:
    return asyncio.create_task(_watchdog_loop(float(threshold_s)))


def start_metrics_server(port: int = 9090) -> None:
    start_http_server(port)
    logger.info(json.dumps({"event": "metrics_server_started", "port": port}))


async def _watchdog_loop(threshold_s: float) -> None:
    while True:
        await asyncio.sleep(_WATCHDOG_INTERVAL_S)
        elapsed = max(0.0, time.time() - _last_message_time)
        _GAUGE.set(elapsed)
        if elapsed > threshold_s:
            logger.warning(
                json.dumps(
                    {
                        "event": "stream_stalled",
                        "seconds_since_last": elapsed,
                        "threshold_s": threshold_s,
                    }
                )
            )
