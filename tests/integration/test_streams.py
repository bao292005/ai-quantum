"""Integration tests for ``stream_new_heads`` (Story 1A.4, AC5).

Spins up a real ``MockWssServer`` (Story 0.5) on an ephemeral port and drives it
through the real ``EthereumClient`` + web3.py WebSocket subscription, proving the
end-to-end contract: subscribe → receive >= 5 normalized block headers within
10s at ``speed=asap``, each carrying the AC3 fields.

Each test starts its own server because the mock replays a fixture exactly once
per lifetime (lazy-started on the first subscription). The fixture is trimmed to
the first few blocks: at ``asap`` an unbounded replay would flood web3's internal
subscription queue faster than a 5-header consumer drains it, so a small, bounded
replay keeps subscribe/consume/teardown fast and deterministic.
"""

from __future__ import annotations

import asyncio
import socket
from contextlib import asynccontextmanager

from ingestion.client import EthereumClient
from ingestion.config import IngestionConfig
from ingestion.streams import stream_new_heads
from tools.mock_wss.replay import load_events, parse_speed, resolve_scenario_file
from tools.mock_wss.server import MockWssServer, ServerState

HOST = "127.0.0.1"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind((HOST, 0))
        return s.getsockname()[1]


def _first_n_blocks(events: list[dict], n: int) -> list[dict]:
    """Return the events belonging to the first ``n`` distinct blocks."""
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
async def running_server(
    speed: str = "asap", scenario: str = "luna", port: int = 8621, blocks: int = 10
):
    """Start a mock WSS server replaying the first ``blocks`` blocks of a scenario."""
    events = _first_n_blocks(load_events(resolve_scenario_file(scenario)), blocks)
    server = MockWssServer(events, parse_speed(speed), state=ServerState())
    task = asyncio.create_task(server.run(HOST, port))
    await asyncio.sleep(0.3)  # let serve() bind before the client connects
    try:
        yield port
    finally:
        server.request_stop()
        await asyncio.wait_for(task, timeout=5)


async def _collect_heads(port: int, count: int) -> list[dict]:
    cfg = IngestionConfig(wss_url=f"ws://{HOST}:{port}")
    headers: list[dict] = []
    async with EthereumClient(cfg) as client:
        stream = stream_new_heads(client)
        try:
            async for head in stream:
                headers.append(head)
                if len(headers) >= count:
                    break
        finally:
            # Tear the subscription down before disconnecting so the live
            # socket read loop stops promptly (keeps teardown fast).
            await stream.aclose()
    return headers


async def test_stream_new_heads_receives_blocks():
    # AC5: subscribe → receive >= 5 block headers within 10s at speed=asap.
    async with running_server(speed="asap", port=_free_port()) as port:
        headers = await asyncio.wait_for(_collect_heads(port, 5), timeout=10.0)

    assert len(headers) >= 5
    for h in headers:
        # AC3 field presence + types after normalization.
        assert isinstance(h["number"], int)
        assert isinstance(h["hash"], str) and h["hash"].startswith("0x")
        assert isinstance(h["timestamp"], int)
        assert isinstance(h["parentHash"], str) and h["parentHash"].startswith("0x")


async def test_block_numbers_are_monotonic():
    async with running_server(speed="asap", port=_free_port()) as port:
        headers = await asyncio.wait_for(_collect_heads(port, 5), timeout=10.0)

    numbers = [h["number"] for h in headers]
    assert numbers == sorted(numbers)
