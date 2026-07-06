"""Health HTTP endpoint for the mock WebSocket server (Story 0.5, AC5).

A tiny aiohttp app served on a port separate from the WebSocket so ``GET
/health`` never collides with the WS traffic. Runs on the same asyncio event
loop as the server (no extra thread, no blocking calls).
"""

from __future__ import annotations

import logging

from aiohttp import web

from tools.mock_wss.server import ServerState

logger = logging.getLogger("mock_wss")


def make_health_app(state: ServerState) -> web.Application:
    app = web.Application()

    async def health(_request: web.Request) -> web.Response:
        return web.json_response(state.snapshot())

    app.router.add_get("/health", health)
    return app


async def start_health_server(state: ServerState, host: str, port: int) -> web.AppRunner:
    """Start the health app and return its runner (call ``.cleanup()`` to stop)."""
    runner = web.AppRunner(make_health_app(state))
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    logger.info("mock-wss health endpoint on http://%s:%d/health", host, port)
    return runner
