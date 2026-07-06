"""Async mock Ethereum WebSocket server (Story 0.5).

Speaks a JSON-RPC 2.0 ``eth_subscribe`` subset compatible with Web3.py's
``AsyncWeb3(WebSocketProvider(...))``:

* ``eth_subscribe ["newHeads"]``           → per-block BlockHeader notifications
* ``eth_subscribe ["logs", {address,...}]`` → per-log notifications (address
  filter only in v1 — AC9; ``topics`` is parsed but ignored with a WARNING)
* ``eth_unsubscribe [id]``                  → drop a subscription
* any other method                          → JSON-RPC ``-32601`` error

A single replay loop walks the fixture in block order and fans notifications
out to each client's bounded outgoing queue. Slow clients get their oldest
queued message dropped rather than stalling the replay loop (AC10).
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field

import websockets
from websockets.asyncio.server import ServerConnection, serve

from tools.mock_wss.replay import (
    build_block_header,
    build_raw_log,
    iter_block_groups,
    sleep_seconds,
)

logger = logging.getLogger("mock_wss")

MAX_QUEUE_PER_CLIENT = 10_000  # AC10 backpressure ceiling
DRAIN_TIMEOUT_SEC = 2.0  # AC6 graceful-shutdown drain budget


@dataclass
class ServerState:
    """Shared, read-mostly metrics surfaced by the health endpoint (AC5)."""

    start_time: float = field(default_factory=time.time)
    current_block: int = 0
    events_sent: int = 0
    dropped_total: int = 0

    def snapshot(self) -> dict:
        return {
            "status": "ok",
            "current_block": self.current_block,
            "events_sent": self.events_sent,
            "dropped_total": self.dropped_total,
            "uptime_seconds": round(time.time() - self.start_time, 3),
        }


@dataclass
class _Subscription:
    sub_id: str
    kind: str  # "newHeads" | "logs"
    addresses: frozenset[str] | None  # None → match every address


class _Client:
    """One connected websocket + its bounded outgoing queue and subscriptions."""

    def __init__(self, ws: ServerConnection) -> None:
        self.ws = ws
        self.id = uuid.uuid4().hex
        self.queue: asyncio.Queue[str] = asyncio.Queue(maxsize=MAX_QUEUE_PER_CLIENT)
        self.subs: dict[str, _Subscription] = {}
        self.dropped = 0

    def enqueue(self, message: str) -> bool:
        """Non-blocking enqueue that always places ``message`` (AC10).

        On a full queue the *oldest* queued message is evicted to make room, so
        the newest message (including control-plane replies) is never the one
        dropped. Returns ``True`` iff an eviction occurred, so the caller can
        bump the global ``mock_wss_dropped_total`` metric. Never blocks — the
        replay loop must keep throughput.
        """
        dropped = False
        if self.queue.full():
            try:
                self.queue.get_nowait()  # evict oldest to guarantee room
            except asyncio.QueueEmpty:  # pragma: no cover - single-threaded, unreachable
                pass
            else:
                dropped = True
                self.dropped += 1
                if self.dropped % 1000 == 0:
                    logger.warning(
                        "client %s slow: %d dropped (mock_wss_dropped_total)",
                        self.id,
                        self.dropped,
                    )
        self.queue.put_nowait(message)  # guaranteed: room was made above
        return dropped


class MockWssServer:
    def __init__(self, events: list[dict], speed: float | None, state: ServerState | None = None) -> None:
        self.events = events
        self.speed = speed
        self.state = state or ServerState()
        self._clients: set[_Client] = set()
        self._stop = asyncio.Event()
        self._first_sub = asyncio.Event()

    # -- lifecycle ---------------------------------------------------------

    def request_stop(self) -> None:
        self._stop.set()

    async def run(self, host: str, port: int) -> None:
        """Serve until :meth:`request_stop`, then drain + close gracefully (AC6)."""
        async with serve(self._handle_client, host, port):
            logger.info("mock-wss listening on ws://%s:%d", host, port)
            replay_task = asyncio.create_task(self._replay_loop())
            await self._stop.wait()
            replay_task.cancel()
            await asyncio.gather(replay_task, return_exceptions=True)
            await self._drain_and_close()

    async def _await_first_subscription(self) -> bool:
        """Block until the first client subscribes or a stop is requested.

        Returns ``True`` if a subscriber arrived, ``False`` if the server was
        asked to stop first. Replaying only once a subscriber exists means late
        connections (the common case in tests and CI) still see the full replay
        from the beginning — the server keeps no per-client offset.
        """
        stop_wait = asyncio.ensure_future(self._stop.wait())
        sub_wait = asyncio.ensure_future(self._first_sub.wait())
        try:
            done, _ = await asyncio.wait(
                {stop_wait, sub_wait}, return_when=asyncio.FIRST_COMPLETED
            )
        finally:
            stop_wait.cancel()
            sub_wait.cancel()
        return self._first_sub.is_set()

    async def _drain_and_close(self) -> None:
        deadline = time.time() + DRAIN_TIMEOUT_SEC
        for client in list(self._clients):
            while not client.queue.empty() and time.time() < deadline:
                await asyncio.sleep(0.02)
        await asyncio.gather(
            *(c.ws.close() for c in list(self._clients)), return_exceptions=True
        )
        logger.info("mock-wss drained and closed %d client(s)", len(self._clients))

    # -- per-client handling ----------------------------------------------

    async def _handle_client(self, ws: ServerConnection) -> None:
        client = _Client(ws)
        self._clients.add(client)
        writer = asyncio.create_task(self._writer(client))
        try:
            async for raw in ws:
                await self._on_message(client, raw)
        except websockets.ConnectionClosed:
            pass
        finally:
            writer.cancel()
            await asyncio.gather(writer, return_exceptions=True)
            self._clients.discard(client)

    async def _writer(self, client: _Client) -> None:
        try:
            while True:
                message = await client.queue.get()
                await client.ws.send(message)
        except (asyncio.CancelledError, websockets.ConnectionClosed):
            pass

    async def _on_message(self, client: _Client, raw: str | bytes) -> None:
        try:
            req = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return  # ignore non-JSON frames
        req_id = req.get("id")
        method = req.get("method")
        params = req.get("params") or []

        if method == "eth_subscribe":
            result = self._subscribe(client, params)
            await self._reply(client, req_id, result=result)
        elif method == "eth_unsubscribe":
            sub_id = params[0] if isinstance(params, list) and params else None
            removed = client.subs.pop(sub_id, None) is not None
            await self._reply(client, req_id, result=removed)
        else:
            await self._reply(
                client,
                req_id,
                error={"code": -32601, "message": f"Method not found: {method}"},
            )

    def _subscribe(self, client: _Client, params: list) -> str:
        if not isinstance(params, list):
            params = []
        kind = params[0] if params else "newHeads"
        addresses: frozenset[str] | None = None
        if kind == "logs":
            filt = params[1] if len(params) > 1 and isinstance(params[1], dict) else {}
            addr = filt.get("address")
            if isinstance(addr, str):
                addresses = frozenset({addr.lower()})
            elif isinstance(addr, list):
                # AC9: address-only match; ignore non-string elements defensively.
                cleaned = {a.lower() for a in addr if isinstance(a, str)}
                addresses = frozenset(cleaned) if cleaned else None
            if filt.get("topics"):
                logger.warning(
                    "client %s sent a 'topics' filter — IGNORED in v1 "
                    "(address-only matching, AC9)",
                    client.id,
                )
        sub = _Subscription(sub_id="0x" + uuid.uuid4().hex, kind=kind, addresses=addresses)
        client.subs[sub.sub_id] = sub
        self._first_sub.set()  # release the replay loop (lazy start, AC7)
        return sub.sub_id

    async def _reply(self, client: _Client, req_id, *, result=None, error=None) -> None:
        msg: dict = {"jsonrpc": "2.0", "id": req_id}
        if error is not None:
            msg["error"] = error
        else:
            msg["result"] = result
        # enqueue guarantees placement (drops the OLDEST on a full queue), so a
        # control-plane reply — e.g. the subscription id the client awaits — is
        # never the message evicted under backpressure.
        client.enqueue(json.dumps(msg))

    # -- fan-out + replay --------------------------------------------------

    @staticmethod
    def _notification(sub_id: str, result: dict) -> str:
        return json.dumps(
            {
                "jsonrpc": "2.0",
                "method": "eth_subscription",
                "params": {"subscription": sub_id, "result": result},
            }
        )

    def _fanout_head(self, header: dict) -> None:
        # Snapshot before iterating: clients/subs may mutate from the read path.
        for client in list(self._clients):
            for sub in list(client.subs.values()):
                if sub.kind == "newHeads":
                    if client.enqueue(self._notification(sub.sub_id, header)):
                        self.state.dropped_total += 1

    def _fanout_log(self, log: dict) -> None:
        address = str(log.get("address", "")).lower()
        # Snapshot before iterating: clients/subs may mutate from the read path.
        for client in list(self._clients):
            for sub in list(client.subs.values()):
                if sub.kind != "logs":
                    continue
                if sub.addresses is not None and address not in sub.addresses:
                    continue
                if client.enqueue(self._notification(sub.sub_id, log)):
                    self.state.dropped_total += 1

    async def _replay_loop(self) -> None:
        if not await self._await_first_subscription():
            return  # stop requested before any subscriber connected
        prev_ts: str | None = None
        for block_number, block_ts, rows in iter_block_groups(self.events):
            if self._stop.is_set():
                return
            if prev_ts is not None:
                try:
                    delay = sleep_seconds(prev_ts, block_ts, self.speed)
                except (ValueError, TypeError) as exc:
                    logger.warning(
                        "block %s: bad timestamp %r, replaying with no delay: %s",
                        block_number, block_ts, exc,
                    )
                    delay = 0.0
                if delay > 0:
                    await asyncio.sleep(delay)
            prev_ts = block_ts

            # A single malformed fixture row must NOT kill the replay task (and
            # leave /health falsely reporting "ok"): guard per-block/per-row and
            # skip what cannot be rendered.
            try:
                header = build_block_header(block_number, block_ts)
            except (ValueError, TypeError, KeyError) as exc:
                logger.warning("block %s: cannot build header, skipping: %s", block_number, exc)
                continue
            self.state.current_block = block_number
            self._fanout_head(header)
            self.state.events_sent += 1
            for row in rows:
                try:
                    log = build_raw_log(row)
                except (ValueError, TypeError, KeyError) as exc:
                    logger.warning(
                        "block %s: skipping malformed row (log_index=%s): %s",
                        block_number, row.get("log_index"), exc,
                    )
                    continue
                self._fanout_log(log)
                self.state.events_sent += 1
        logger.info("mock-wss replay finished (%d events)", self.state.events_sent)
