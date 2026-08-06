"""Async webhook emitter (Story 5.3).

Fans a fragility-alert payload out to all subscriber URLs **in parallel**
(`asyncio.gather`) so one slow/unhealthy subscriber never blocks the others.
Each delivery is retried once on failure/timeout; a final failure is logged at
ERROR. Transport is aiohttp by default; a ``poster`` coroutine can be injected
(tests, alternate transports).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Sequence
from typing import Any

logger = logging.getLogger(__name__)

# poster(url) -> truthy on success; raises or returns falsy on failure.
Poster = Callable[[str], Awaitable[Any]]

_DEFAULT_TIMEOUT_S = 5.0


async def _deliver(url: str, poster: Poster, retries: int) -> bool:
    attempts = retries + 1
    for _ in range(attempts):
        try:
            if await poster(url):
                return True
        except Exception as exc:  # noqa: BLE001 — timeout / connection / etc.
            logger.debug("webhook attempt failed url=%s: %r", url, exc)
    logger.error("webhook delivery failed url=%s after %d attempt(s)", url, attempts)
    return False


async def emit(
    payload: dict,
    subscribers: Sequence[str],
    *,
    timeout: float = _DEFAULT_TIMEOUT_S,
    retries: int = 1,
    poster: Poster | None = None,
) -> dict[str, bool]:
    """Deliver ``payload`` to every subscriber URL concurrently.

    Args:
        payload: schema-valid FragilityAlert dict (from ``emitter.payload``).
        subscribers: subscriber webhook URLs.
        timeout: per-request timeout for the default aiohttp transport.
        retries: extra attempts after the first (1 → up to 2 attempts total).
        poster: optional injected delivery coroutine ``(url) -> truthy``; when
            omitted, an aiohttp POST of ``payload`` is used.

    Returns:
        ``{url: delivered_ok}`` for every subscriber.
    """
    if not subscribers:
        return {}

    if poster is None:
        import aiohttp

        session = aiohttp.ClientSession()

        async def poster(url: str) -> bool:  # type: ignore[misc]
            client_timeout = aiohttp.ClientTimeout(total=timeout)
            async with session.post(url, json=payload, timeout=client_timeout) as resp:
                return 200 <= resp.status < 300

        try:
            outcomes = await asyncio.gather(
                *(_deliver(u, poster, retries) for u in subscribers)
            )
        finally:
            await session.close()
    else:
        outcomes = await asyncio.gather(
            *(_deliver(u, poster, retries) for u in subscribers)
        )

    return dict(zip(subscribers, outcomes))


__all__ = ["emit"]
