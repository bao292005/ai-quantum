import asyncio
import logging
import socket
import urllib.request

import pytest
from prometheus_client import REGISTRY

from ingestion import metrics


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _Clock:
    """A controllable stand-in for ``time.time`` used to make elapsed-time
    assertions deterministic without real sleeping."""

    def __init__(self, t: float) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t


@pytest.fixture
def clock(monkeypatch):
    c = _Clock(1_000.0)
    monkeypatch.setattr(metrics.time, "time", c)
    return c


def _gauge_value() -> float:
    return REGISTRY.get_sample_value(metrics.METRIC_NAME)


class TestRecordMessage:
    def test_updates_timestamp_and_zeroes_gauge(self, clock):
        clock.t = 1_234.5
        metrics.record_message()

        assert metrics._last_message_time == 1_234.5
        assert _gauge_value() == 0.0

    def test_seconds_since_last_message_tracks_elapsed(self, clock):
        clock.t = 1_000.0
        metrics.record_message()
        clock.t = 1_007.0

        assert metrics.seconds_since_last_message() == 7.0


class TestStallDetection:
    def test_warns_when_stalled_past_threshold(self, clock, caplog):
        clock.t = 2_000.0
        metrics.record_message()
        clock.t = 2_020.0  # 20s of silence, threshold 15s

        with caplog.at_level(logging.WARNING, logger=metrics.logger.name):
            elapsed = metrics._check_stall(15.0)

        assert elapsed == 20.0
        assert _gauge_value() == 20.0
        stalls = [r for r in caplog.records if "stream_stalled" in r.getMessage()]
        assert len(stalls) == 1
        assert '"seconds_since_last": 20.0' in stalls[0].getMessage()

    def test_no_warning_when_fresh(self, clock, caplog):
        clock.t = 3_000.0
        metrics.record_message()
        clock.t = 3_005.0  # only 5s, under threshold

        with caplog.at_level(logging.WARNING, logger=metrics.logger.name):
            elapsed = metrics._check_stall(15.0)

        assert elapsed == 5.0
        assert _gauge_value() == 5.0
        assert not any("stream_stalled" in r.getMessage() for r in caplog.records)


class TestMetricName:
    def test_metric_name_is_exact(self):
        assert metrics.METRIC_NAME == "ingestion_ws_last_message_seconds"
        # Gauge is registered under that exact name in the default registry.
        assert _gauge_value() is not None


class TestWatchdogTask:
    async def test_watchdog_detects_stall(self, clock, caplog):
        clock.t = 4_000.0  # start_stall_watchdog anchors the heartbeat clock here

        with caplog.at_level(logging.WARNING, logger=metrics.logger.name):
            task = metrics.start_stall_watchdog(threshold_s=15.0, interval_s=0.01)
            clock.t = 4_030.0  # 30s of silence since the watchdog started
            await asyncio.sleep(0.05)  # allow a few watchdog iterations
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

        assert any("stream_stalled" in r.getMessage() for r in caplog.records)

    async def test_watchdog_reset_prevents_startup_false_stall(self, clock, caplog):
        # Regression for the import-time seed: a long-idle _last_message_time must
        # NOT trip a stall on the first check because the clock is reset at start.
        metrics._last_message_time = 0.0  # simulate a very stale import-time seed
        clock.t = 5_000.0

        with caplog.at_level(logging.WARNING, logger=metrics.logger.name):
            task = metrics.start_stall_watchdog(threshold_s=15.0, interval_s=0.01)
            await asyncio.sleep(0.03)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

        assert not any("stream_stalled" in r.getMessage() for r in caplog.records)

    async def test_watchdog_returns_task(self, clock):
        task = metrics.start_stall_watchdog(threshold_s=15.0, interval_s=0.01)
        assert isinstance(task, asyncio.Task)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task


class TestMetricsServer:
    def test_metrics_endpoint_serves_gauge(self):
        # AC4: GET /metrics exposes the gauge in Prometheus text format.
        port = _free_port()
        server, thread = metrics.start_metrics_server(port=port, addr="127.0.0.1")
        try:
            metrics.record_message()
            body = urllib.request.urlopen(
                f"http://127.0.0.1:{port}/metrics", timeout=3
            ).read().decode()
        finally:
            server.shutdown()
            thread.join(timeout=3)

        assert "ingestion_ws_last_message_seconds" in body
        assert not thread.is_alive()
