import asyncio
import functools
import json
import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)

_RECONNECT_EXCEPTIONS = (
    ConnectionError,
    ConnectionResetError,
    OSError,
)


def auto_reconnect(
    max_retries: int | None = None,
    base: float = 0.5,
    cap: float = 30.0,
) -> Callable:
    """Decorator that retries an async coroutine with exponential backoff.

    Args:
        max_retries: Maximum number of retries after the first failure.
            None = retry indefinitely.
            0    = no retries; raise immediately on the first failure.
            N>0  = retry up to N times, then raise.
        base: Base delay in seconds for the first retry.
        cap: Maximum delay in seconds (delay is capped at this value).
    """

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            attempt = 0
            while True:
                try:
                    return await fn(*args, **kwargs)
                except _RECONNECT_EXCEPTIONS as exc:
                    if max_retries is not None and attempt >= max_retries:
                        raise
                    delay = min(base * (2**attempt), cap)
                    logger.warning(
                        json.dumps(
                            {
                                "event": "reconnect",
                                "attempt": attempt + 1,
                                "delay_s": delay,
                                "error": str(exc),
                                "function": fn.__qualname__,
                            }
                        )
                    )
                    await asyncio.sleep(delay)
                    attempt += 1

        return wrapper

    return decorator
