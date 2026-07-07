from __future__ import annotations

import logging

import pytest

from ingestion import metrics


class _StopWatchdog(Exception):
    pass


def test_metric_name_is_exact():
    assert metrics._GAUGE._name == "ingestion_ws_last_message_seconds"


def test_record_message_updates_timestamp_and_resets_gauge(monkeypatch):
    monkeypatch.setattr(metrics.time, "time", lambda: 123.0)
    metrics._GAUGE.set(42.0)

    metrics.record_message()

    assert metrics._last_message_time == 123.0
    assert metrics._GAUGE._value.get() == 0.0


async def test_watchdog_warns_when_threshold_exceeded(monkeypatch, caplog):
    calls = 0

    async def fake_sleep(_seconds):
        nonlocal calls
        calls += 1
        if calls > 1:
            raise _StopWatchdog

    monkeypatch.setattr(metrics.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(metrics.time, "time", lambda: 120.0)
    monkeypatch.setattr(metrics, "_last_message_time", 100.0)

    with caplog.at_level(logging.WARNING, logger="ingestion.metrics"):
        task = metrics.start_stall_watchdog(threshold_s=15)
        with pytest.raises(_StopWatchdog):
            await task

    assert metrics._GAUGE._value.get() == 20.0
    assert any("stream_stalled" in record.message for record in caplog.records)
    assert any("seconds_since_last" in record.message for record in caplog.records)
    assert any("threshold_s" in record.message for record in caplog.records)


async def test_watchdog_does_not_warn_before_threshold(monkeypatch, caplog):
    calls = 0

    async def fake_sleep(_seconds):
        nonlocal calls
        calls += 1
        if calls > 1:
            raise _StopWatchdog

    monkeypatch.setattr(metrics.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(metrics.time, "time", lambda: 110.0)
    monkeypatch.setattr(metrics, "_last_message_time", 100.0)

    with caplog.at_level(logging.WARNING, logger="ingestion.metrics"):
        task = metrics.start_stall_watchdog(threshold_s=15)
        with pytest.raises(_StopWatchdog):
            await task

    assert metrics._GAUGE._value.get() == 10.0
    assert "stream_stalled" not in caplog.text


def test_start_metrics_server_calls_prometheus(monkeypatch, caplog):
    called = {}

    def fake_start_http_server(port):
        called["port"] = port

    monkeypatch.setattr(metrics, "start_http_server", fake_start_http_server)

    with caplog.at_level(logging.INFO, logger="ingestion.metrics"):
        metrics.start_metrics_server(port=9191)

    assert called["port"] == 9191
    assert "metrics_server_started" in caplog.text
