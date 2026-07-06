"""CLI entrypoint for the mock WebSocket server (Story 0.5).

    python -m tools.mock_wss --file fixtures/backtest/luna_2022_05_09.csv --speed 1x
    python -m tools.mock_wss --scenario luna --speed 100x

Flags: --host, --port (8546), --health-port (8547), --file OR --scenario
(exactly one required), --speed (1x|100x|asap).
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import sys
from pathlib import Path

from tools.mock_wss.health import start_health_server
from tools.mock_wss.replay import load_events, parse_speed, resolve_scenario_file
from tools.mock_wss.server import MockWssServer, ServerState

logger = logging.getLogger("mock_wss")

DEFAULT_WS_PORT = 8546
DEFAULT_HEALTH_PORT = 8547


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tools.mock_wss",
        description="Replay tick-data fixtures over a mock Ethereum eth_subscribe WebSocket.",
    )
    parser.add_argument("--host", default="0.0.0.0", help="bind host (default 0.0.0.0)")
    parser.add_argument("--port", type=int, default=DEFAULT_WS_PORT, help="WebSocket port (default 8546)")
    parser.add_argument(
        "--health-port", type=int, default=DEFAULT_HEALTH_PORT, help="health HTTP port (default 8547)"
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--file", help="path to a fixture .csv/.csv.gz")
    source.add_argument(
        "--scenario", choices=["luna", "ftx", "normal"], help="shortcut to a Story 0.4 fixture"
    )
    parser.add_argument("--speed", default="1x", help="replay speed: 1x, 100x, or asap")
    return parser


def _resolve_file(args: argparse.Namespace) -> Path:
    if args.scenario:
        return resolve_scenario_file(args.scenario)
    path = Path(args.file)
    if not path.is_file():
        raise FileNotFoundError(f"fixture not found: {path}")
    return path


async def _serve(args: argparse.Namespace) -> int:
    fixture = _resolve_file(args)
    speed = parse_speed(args.speed)
    events = load_events(fixture)
    logger.info("loaded %d events from %s (speed=%s)", len(events), fixture.name, args.speed)

    state = ServerState()
    server = MockWssServer(events, speed, state=state)

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, server.request_stop)
        except NotImplementedError:  # pragma: no cover - Windows
            signal.signal(sig, lambda *_: server.request_stop())

    health_runner = await start_health_server(state, args.host, args.health_port)
    try:
        await server.run(args.host, args.port)
    finally:
        await health_runner.cleanup()
    return 0


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    args = build_parser().parse_args(argv)
    try:
        return asyncio.run(_serve(args))
    except (OSError, ValueError) as exc:
        # OSError covers FileNotFoundError and gzip.BadGzipFile (a mislabeled
        # .gz/.csv), so a bad fixture is a clean exit-2, not a raw traceback.
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
