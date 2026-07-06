"""Integration tests for the mock WebSocket server (Story 0.5, AC8).

Spins up a real ``MockWssServer`` on an ephemeral port and drives it with an
async ``websockets`` client to prove the end-to-end contract:

* ``eth_subscribe ["newHeads"]`` / ``["logs", {...}]`` return a subscription id.
* Notifications arrive in strict JSON-RPC 2.0 ``eth_subscription`` shape (AC3).
* At ``--speed 100x`` a client receives >= 100 messages within 5s (AC8).
* An unknown method yields a ``-32601`` JSON-RPC error (AC3/LLM-mistake guard).
* A ``logs`` address filter only matches the requested pool (AC9).
"""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager

import pytest
import websockets

from tools.mock_wss.replay import load_events, parse_speed, resolve_scenario_file
from tools.mock_wss.server import MockWssServer, ServerState

pytestmark = pytest.mark.asyncio

HOST = "127.0.0.1"


@asynccontextmanager
async def running_server(speed: str, scenario: str = "luna", port: int = 8611):
    """Start a mock server on ``port`` for the duration of the context."""
    events = load_events(resolve_scenario_file(scenario))
    state = ServerState()
    server = MockWssServer(events, parse_speed(speed), state=state)
    task = asyncio.create_task(server.run(HOST, port))
    await asyncio.sleep(0.3)  # let serve() bind before the client connects
    try:
        yield server, state, port
    finally:
        server.request_stop()
        await asyncio.wait_for(task, timeout=5)


async def _recv(ws, timeout=5.0):
    return json.loads(await asyncio.wait_for(ws.recv(), timeout=timeout))


async def test_subscribe_returns_subscription_id():
    async with running_server("asap", port=8611) as (_srv, _state, port):
        async with websockets.connect(f"ws://{HOST}:{port}") as ws:
            await ws.send(json.dumps(
                {"jsonrpc": "2.0", "id": 1, "method": "eth_subscribe", "params": ["newHeads"]}
            ))
            reply = await _recv(ws)
            assert reply["jsonrpc"] == "2.0"
            assert reply["id"] == 1
            assert isinstance(reply["result"], str) and reply["result"].startswith("0x")


async def test_unknown_method_returns_minus_32601():
    async with running_server("asap", port=8612) as (_srv, _state, port):
        async with websockets.connect(f"ws://{HOST}:{port}") as ws:
            # Subscribe first so the replay loop starts; then probe a bad method.
            await ws.send(json.dumps(
                {"jsonrpc": "2.0", "id": 1, "method": "eth_subscribe", "params": ["newHeads"]}
            ))
            await ws.send(json.dumps(
                {"jsonrpc": "2.0", "id": 2, "method": "eth_getBalance", "params": []}
            ))
            err = None
            for _ in range(200):
                msg = await _recv(ws)
                if msg.get("id") == 2:
                    err = msg
                    break
            assert err is not None, "no reply to unknown method"
            assert err["error"]["code"] == -32601


async def test_receives_at_least_100_messages_at_100x():
    async with running_server("100x", port=8613) as (_srv, _state, port):
        async with websockets.connect(f"ws://{HOST}:{port}") as ws:
            await ws.send(json.dumps(
                {"jsonrpc": "2.0", "id": 1, "method": "eth_subscribe", "params": ["newHeads"]}
            ))
            await ws.send(json.dumps(
                {"jsonrpc": "2.0", "id": 2, "method": "eth_subscribe", "params": ["logs", {}]}
            ))
            notifications = 0
            deadline = asyncio.get_event_loop().time() + 5.0
            while notifications < 100 and asyncio.get_event_loop().time() < deadline:
                remaining = deadline - asyncio.get_event_loop().time()
                if remaining <= 0:
                    break
                try:
                    msg = await _recv(ws, timeout=remaining)
                except asyncio.TimeoutError:
                    break
                if msg.get("method") == "eth_subscription":
                    # AC3: strict JSON-RPC 2.0 notification shape.
                    assert msg["jsonrpc"] == "2.0"
                    params = msg["params"]
                    assert params["subscription"].startswith("0x")
                    assert isinstance(params["result"], dict)
                    notifications += 1
            assert notifications >= 100, f"only received {notifications} notifications in 5s"


async def test_replay_survives_malformed_row():
    """A malformed fixture row must be skipped, not kill the replay task (AC5/AC10 review)."""
    good = load_events(resolve_scenario_file("luna"))[:5]
    poison = dict(good[0])
    poison["amount0"] = "not-a-number"  # build_raw_log → ValueError → row skipped
    poison["block_number"] = good[-1]["block_number"] + 1
    poison["log_index"] = 0
    events = good + [poison]

    state = ServerState()
    server = MockWssServer(events, parse_speed("asap"), state=state)
    task = asyncio.create_task(server.run(HOST, 8615))
    await asyncio.sleep(0.3)
    try:
        async with websockets.connect(f"ws://{HOST}:8615") as ws:
            await ws.send(json.dumps(
                {"jsonrpc": "2.0", "id": 1, "method": "eth_subscribe", "params": ["logs", {}]}
            ))
            logs_seen = 0
            try:
                while logs_seen < 3:
                    msg = await _recv(ws, timeout=3.0)
                    if msg.get("method") == "eth_subscription" and "address" in msg["params"]["result"]:
                        logs_seen += 1
            except asyncio.TimeoutError:
                pass
            assert logs_seen > 0, "good rows should still replay past the poison row"
        await asyncio.sleep(0.2)
        # Replay task alive/finished cleanly; health still healthy.
        assert state.snapshot()["status"] == "ok"
    finally:
        server.request_stop()
        await asyncio.wait_for(task, timeout=5)


async def test_logs_address_filter_matches_only_requested_pool():
    events = load_events(resolve_scenario_file("luna"))
    target_addr = next(e["pool_address"] for e in events).lower()
    async with running_server("asap", port=8614) as (_srv, _state, port):
        async with websockets.connect(f"ws://{HOST}:{port}") as ws:
            await ws.send(json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "eth_subscribe",
                    "params": ["logs", {"address": target_addr}],
                }
            ))
            seen = 0
            try:
                while seen < 20:
                    msg = await _recv(ws, timeout=3.0)
                    if msg.get("method") == "eth_subscription":
                        result = msg["params"]["result"]
                        if "address" in result:  # a log, not a head
                            assert result["address"].lower() == target_addr
                            seen += 1
            except asyncio.TimeoutError:
                pass
            assert seen > 0, "address filter matched no logs"
