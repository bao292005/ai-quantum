"""Unit tests for the mock WebSocket server (Story 0.5, AC8).

Fast, network-free coverage of the pure helpers and the CLI parser:

* ``parse_speed`` / ``sleep_seconds`` — speed-control math (AC2).
* ``build_parser`` — CLI argument parsing (AC1/AC4).
* ``build_block_header`` / ``build_raw_log`` — JSON-RPC payload shapes (AC3).
* ``resolve_scenario_file`` — ``--scenario`` mapping (AC4).

The live client/server round-trip lives in
``tests/integration/test_mock_wss_client.py``.
"""

from __future__ import annotations

import pytest

from tools.mock_wss import server as server_mod
from tools.mock_wss.__main__ import build_parser
from tools.mock_wss.replay import (
    build_block_header,
    build_raw_log,
    iter_block_groups,
    parse_speed,
    resolve_scenario_file,
    sleep_seconds,
)
from tools.mock_wss.server import ServerState, _Client


# --- AC2: speed control -----------------------------------------------------

@pytest.mark.parametrize(
    ("value", "expected"),
    [("1x", 1.0), ("100x", 100.0), ("2.5x", 2.5), ("100", 100.0), ("asap", None)],
)
def test_parse_speed_valid(value, expected):
    assert parse_speed(value) == expected


@pytest.mark.parametrize("value", ["0x", "-1x", "fast", "", "x"])
def test_parse_speed_invalid(value):
    with pytest.raises(ValueError):
        parse_speed(value)


def test_sleep_seconds_scales_with_speed():
    prev, cur = "2022-05-09T00:00:00Z", "2022-05-09T00:01:40Z"  # 100s gap
    assert sleep_seconds(prev, cur, 1.0) == pytest.approx(100.0)
    assert sleep_seconds(prev, cur, 100.0) == pytest.approx(1.0)


def test_sleep_seconds_asap_is_zero():
    assert sleep_seconds("2022-05-09T00:00:00Z", "2022-05-09T00:01:40Z", None) == 0.0


def test_sleep_seconds_never_negative():
    # Out-of-order timestamps must never yield a negative sleep.
    assert sleep_seconds("2022-05-09T00:01:40Z", "2022-05-09T00:00:00Z", 1.0) == 0.0


# --- AC1/AC4: CLI parsing ---------------------------------------------------

def test_cli_parses_file_and_speed():
    args = build_parser().parse_args(["--file", "x.csv", "--speed", "100x"])
    assert args.file == "x.csv"
    assert args.speed == "100x"
    assert args.port == 8546
    assert args.health_port == 8547


def test_cli_parses_scenario():
    args = build_parser().parse_args(["--scenario", "luna"])
    assert args.scenario == "luna"
    assert args.file is None


def test_cli_requires_a_source():
    # --file and --scenario are a required mutually-exclusive group.
    with pytest.raises(SystemExit):
        build_parser().parse_args(["--speed", "1x"])


def test_cli_file_and_scenario_are_mutually_exclusive():
    with pytest.raises(SystemExit):
        build_parser().parse_args(["--file", "x.csv", "--scenario", "luna"])


# --- AC4: scenario resolution -----------------------------------------------

def test_resolve_scenario_unknown_raises():
    with pytest.raises(ValueError):
        resolve_scenario_file("does-not-exist")


def test_resolve_scenario_luna_points_at_a_real_fixture():
    path = resolve_scenario_file("luna")
    assert path.is_file()
    assert path.name.startswith("luna_2022_05_09.csv")


# --- AC3: JSON-RPC payload shapes -------------------------------------------

def test_build_block_header_shape():
    header = build_block_header(14_740_000, "2022-05-09T00:00:00Z")
    assert set(header) == {"number", "hash", "parentHash", "timestamp"}
    assert header["number"] == hex(14_740_000)
    assert header["hash"].startswith("0x")
    assert header["parentHash"] == build_block_header(14_739_999, "2022-05-09T00:00:00Z")["hash"]


def test_build_raw_log_shape():
    row = {
        "block_number": 14_740_000,
        "block_timestamp": "2022-05-09T00:00:00Z",
        "event_type": "swap",
        "pool_address": "0xAbC0000000000000000000000000000000000001",
        "amount0": "123",
        "amount1": "-456",
        "tx_hash": "0xdead",
        "log_index": 7,
    }
    log = build_raw_log(row)
    assert log["address"] == row["pool_address"]
    assert log["topics"] and log["topics"][0].startswith("0x")
    assert log["data"].startswith("0x") and len(log["data"]) == 2 + 128  # two 32-byte words
    assert log["blockNumber"] == hex(14_740_000)
    assert log["logIndex"] == hex(7)
    assert log["removed"] is False


# --- AC10: backpressure enqueue semantics (review patch) --------------------

def test_enqueue_drops_oldest_and_reports(monkeypatch):
    # Shrink the ceiling so we can force a full queue deterministically.
    monkeypatch.setattr(server_mod, "MAX_QUEUE_PER_CLIENT", 2)
    c = _Client(ws=None)
    assert c.enqueue("a") is False
    assert c.enqueue("b") is False
    assert c.enqueue("c") is True  # full → evict oldest ("a"), keep newest ("c")
    drained = [c.queue.get_nowait() for _ in range(c.queue.qsize())]
    assert drained == ["b", "c"]
    assert c.dropped == 1


def test_snapshot_includes_dropped_total():
    # AC10 observability: the health snapshot must surface the drop counter.
    state = ServerState()
    state.dropped_total = 7
    snap = state.snapshot()
    assert snap["dropped_total"] == 7
    assert set(snap) == {"status", "current_block", "events_sent", "dropped_total", "uptime_seconds"}


def test_build_raw_log_raises_on_non_numeric_amount():
    # The replay loop relies on this raising (not silently mangling) so its
    # per-row guard can skip the bad row instead of dying.
    row = {
        "block_number": 1, "block_timestamp": "t", "event_type": "swap",
        "pool_address": "0xabc", "amount0": "not-a-number", "amount1": "0",
        "tx_hash": "0x0", "log_index": 0,
    }
    with pytest.raises(ValueError):
        build_raw_log(row)


def test_iter_block_groups_orders_by_block():
    events = [
        {"block_number": 2, "block_timestamp": "t2", "log_index": 0},
        {"block_number": 1, "block_timestamp": "t1", "log_index": 0},
        {"block_number": 2, "block_timestamp": "t2", "log_index": 1},
    ]
    events.sort(key=lambda r: (r["block_number"], r["log_index"]))
    groups = list(iter_block_groups(events))
    assert [g[0] for g in groups] == [1, 2]
    assert len(groups[1][2]) == 2  # block 2 has two rows
