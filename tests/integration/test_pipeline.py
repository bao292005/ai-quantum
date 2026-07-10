"""Integration test for the realtime pipeline orchestrator (Story 1E.1).

Self-hosts a ``MockWssServer`` (Story 0.5, emitting real ABI logs after Story
0.6) on an ephemeral port and drives ``run_realtime`` end-to-end: WebSocket
newHeads + logs → EventRouter (1B) → DequeRingBuffer (1C). Asserts the ring
buffer fills, counters advance, and shutdown is clean.
"""

from __future__ import annotations

import asyncio
import socket
from contextlib import asynccontextmanager

from core.ring_buffer import DequeRingBuffer
from ingestion import metrics
from ingestion.pipeline import run_realtime
from ingestion.router import EventRouter
from tools.mock_wss.replay import load_events, parse_speed, resolve_scenario_file
from tools.mock_wss.server import MockWssServer, ServerState

HOST = "127.0.0.1"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind((HOST, 0))
        return s.getsockname()[1]


def _first_n_blocks(events: list[dict], n: int) -> list[dict]:
    out: list[dict] = []
    seen: set[int] = set()
    for e in events:
        block = e["block_number"]
        if block not in seen:
            if len(seen) >= n:
                break
            seen.add(block)
        out.append(e)
    return out


@asynccontextmanager
async def running_server(port: int, scenario: str = "luna", blocks: int = 8, speed: str = "100x"):
    # A finite speed (not "asap") is required: at asap the mock replays to
    # completion synchronously on the first (newHeads) subscription, before the
    # logs subscription registers — so no logs would be delivered. A per-block
    # sleep lets the logs subscription attach and receive blocks 2..N.
    events = _first_n_blocks(load_events(resolve_scenario_file(scenario)), blocks)
    server = MockWssServer(events, parse_speed(speed), state=ServerState())
    task = asyncio.create_task(server.run(HOST, port))
    await asyncio.sleep(0.3)  # let serve() bind
    try:
        yield
    finally:
        server.request_stop()
        await asyncio.wait_for(task, timeout=5)


async def test_realtime_ingests_from_mock():
    port = _free_port()
    buffer = DequeRingBuffer(1000)
    router = EventRouter.from_yaml("ingestion/whitelist.yaml")
    stop = asyncio.Event()

    ev_before = metrics.EVENTS_INGESTED._value.get()
    blk_before = metrics.BLOCKS_PROCESSED._value.get()

    async with running_server(port):
        wss = f"ws://{HOST}:{port}"
        consumer = asyncio.create_task(run_realtime(buffer, router, wss, stop))
        await asyncio.sleep(2.5)  # let the mock replay a few blocks at 100x
        stop.set()
        await asyncio.wait_for(consumer, timeout=3.0)  # clean shutdown < 2s budget

    assert len(buffer) > 0, "ring buffer should have received decoded events"
    assert metrics.EVENTS_INGESTED._value.get() - ev_before > 0
    assert metrics.BLOCKS_PROCESSED._value.get() - blk_before > 0

    # Every buffered item is a schema-shaped normalized dict.
    sample = buffer.read_latest(1)[0]
    assert set(sample) >= {"protocol", "event_type", "amount0", "amount1", "pool_address"}
    assert sample["protocol"] in {"uniswap_v3", "aave_v3"}
