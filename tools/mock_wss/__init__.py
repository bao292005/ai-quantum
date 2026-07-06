"""Mock Ethereum WebSocket server (Story 0.5).

Replays tick-data fixture CSVs over ``ws://localhost:8546`` speaking a
JSON-RPC 2.0 ``eth_subscribe`` protocol compatible with Web3.py, so that the
Epic 1 data-ingestion tracks can develop and test without a real RPC provider.
"""

from tools.mock_wss.replay import (
    SCENARIO_FILES,
    build_block_header,
    build_raw_log,
    iter_block_groups,
    load_events,
    parse_speed,
    resolve_scenario_file,
    sleep_seconds,
)
from tools.mock_wss.server import MockWssServer, ServerState

__all__ = [
    "SCENARIO_FILES",
    "MockWssServer",
    "ServerState",
    "build_block_header",
    "build_raw_log",
    "iter_block_groups",
    "load_events",
    "parse_speed",
    "resolve_scenario_file",
    "sleep_seconds",
]
