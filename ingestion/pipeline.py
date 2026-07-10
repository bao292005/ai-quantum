"""Pipeline orchestrator (Story 1E.1).

Wires the ingestion pipeline behind one CLI:

* ``--source=mock``     realtime: EthereumClient WebSocket → newHeads + logs →
  Track 1B ``EventRouter`` → Track 1C ring buffer.
* ``--source=backtest`` historical: CSV fixture → Track 1D ``ReplayDriver`` →
  ring buffer.

Both feed the same ``DequeRingBuffer`` and surface ``events_ingested_total`` /
``blocks_processed_total`` on the Prometheus ``/metrics`` endpoint. SIGTERM/SIGINT
trigger a clean shutdown.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import logging
import signal

from core.ring_buffer import DequeRingBuffer, RingBufferProtocol
from ingestion import metrics
from ingestion.client import EthereumClient
from ingestion.config import IngestionConfig
from ingestion.csv_loader import ReplayDriver
from ingestion.router import EventRouter
from tools.mock_wss.replay import resolve_scenario_file

logger = logging.getLogger(__name__)

_STOP_POLL_S = 0.5  # how often the realtime loop checks the stop event while idle


def _to_int(value) -> int:
    if isinstance(value, str) and value.startswith("0x"):
        return int(value, 16)
    return int(value)


async def run_backtest(
    buffer: RingBufferProtocol, scenario: str, speed: str, *, path=None
) -> int:
    """Replay a fixture into ``buffer`` via the Track 1D ReplayDriver."""
    fixture = path if path is not None else resolve_scenario_file(scenario)
    n = await ReplayDriver(buffer, rate=speed).run(fixture)
    metrics.EVENTS_INGESTED.inc(n)
    logger.info(json.dumps({"event": "backtest_complete", "events": n, "scenario": scenario}))
    return n


async def run_realtime(
    buffer: RingBufferProtocol,
    router: EventRouter,
    wss_url: str,
    stop: asyncio.Event,
) -> None:
    """Consume newHeads + logs from a WebSocket node and fill the ring buffer.

    Single combined loop over ``process_subscriptions()`` (a shared iterator —
    two coroutines cannot both consume it), dispatching by subscription id.
    """
    addresses = router.whitelist.addresses()  # lowercase whitelisted addresses
    async with EthereumClient(IngestionConfig(wss_url=wss_url)) as client:
        w3 = client.w3
        heads_id = await w3.eth.subscribe("newHeads")
        logs_id = await w3.eth.subscribe("logs", {"address": addresses})
        current_ts = 0
        sub_iter = w3.socket.process_subscriptions()
        try:
            while not stop.is_set():
                try:
                    msg = await asyncio.wait_for(sub_iter.__anext__(), timeout=_STOP_POLL_S)
                except asyncio.TimeoutError:
                    continue  # idle — re-check stop
                except StopAsyncIteration:
                    break
                metrics.record_message()
                result = msg["result"]
                if msg["subscription"] == heads_id:
                    current_ts = _to_int(result["timestamp"])
                    metrics.BLOCKS_PROCESSED.inc()
                elif msg["subscription"] == logs_id:
                    if current_ts == 0:
                        # No block time seen yet — don't stamp events with epoch 0.
                        logger.warning(json.dumps({"event": "log_before_first_head_skipped"}))
                        continue
                    try:
                        # One malformed log (missing key, unknown topic, bad
                        # timestamp, schema violation) must not kill ingestion.
                        event = router.route_validated(result, current_ts)
                    except Exception as exc:
                        logger.warning(json.dumps({"event": "log_route_error", "error": str(exc)}))
                        continue
                    if event is not None:
                        buffer.write(event.to_dict())
                        metrics.EVENTS_INGESTED.inc()
        finally:
            # Bound teardown so shutdown stays within the <2s budget even if the
            # socket is unresponsive.
            with contextlib.suppress(Exception):
                await asyncio.wait_for(
                    asyncio.gather(
                        *(w3.eth.unsubscribe(sid) for sid in (heads_id, logs_id)),
                        return_exceptions=True,
                    ),
                    timeout=2.0,
                )


def _parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="ingestion.pipeline", description="QuantumRadar ingestion pipeline")
    p.add_argument("--source", choices=["mock", "backtest"], required=True)
    p.add_argument("--scenario", choices=["luna", "ftx", "normal"], default="luna")
    p.add_argument("--speed", default="100x", help="replay pace, backtest only (ignored for --source=mock)")
    p.add_argument("--capacity", type=int, default=1000)
    p.add_argument("--metrics-port", type=int, default=9090)
    p.add_argument("--whitelist", default="ingestion/whitelist.yaml")
    p.add_argument("--wss-url", default="ws://localhost:8546")
    return p.parse_args(argv)


async def _amain(argv=None) -> RingBufferProtocol:
    args = _parse_args(argv)
    logging.basicConfig(level=logging.INFO)
    buffer = DequeRingBuffer(args.capacity)
    server = thread = None
    with contextlib.suppress(Exception):
        server, thread = metrics.start_metrics_server(args.metrics_port)
    watchdog = metrics.start_stall_watchdog()

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, stop.set)

    try:
        if args.source == "backtest":
            # Run the replay as a task so SIGTERM/SIGINT can interrupt a long
            # backtest promptly instead of waiting for it to finish.
            work = asyncio.create_task(run_backtest(buffer, args.scenario, args.speed))
            waiter = asyncio.create_task(stop.wait())
            _, pending = await asyncio.wait({work, waiter}, return_when=asyncio.FIRST_COMPLETED)
            for t in pending:
                t.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await asyncio.gather(*pending, return_exceptions=True)
        else:
            router = EventRouter.from_yaml(args.whitelist)
            await run_realtime(buffer, router, args.wss_url, stop)
    finally:
        watchdog.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await watchdog
        if server is not None:
            with contextlib.suppress(Exception):
                server.shutdown()
        logger.info(json.dumps({
            "event": "pipeline_shutdown",
            "source": args.source,
            "buffer_len": len(buffer),
        }))
    return buffer


def main(argv=None) -> None:
    asyncio.run(_amain(argv))


if __name__ == "__main__":
    main()
