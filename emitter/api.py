"""FastAPI subscription API (Story 5.1) + enterprise-key auth (Story 5.4).

`create_app` is a factory so the registry, the set of valid API keys, and the
per-key rate limit can be injected (tests, different deployments). Endpoints:

- ``POST /subscribe {"url": ...}``   → 201, add subscriber
- ``DELETE /unsubscribe {"url": ...}`` → 200, remove subscriber
- ``GET /subscribers``               → list current subscribers

Every endpoint requires a valid ``X-API-Key`` header (401 otherwise) and is
rate-limited per key (429 when exceeded).
"""

from __future__ import annotations

import time
from collections.abc import Set

from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel

from emitter.registry import SubscriberRegistry


class SubscribeRequest(BaseModel):
    url: str


def create_app(
    *,
    registry: SubscriberRegistry,
    api_keys: Set[str],
    rate_limit: int = 100,
) -> FastAPI:
    app = FastAPI(title="QuantumRadar Alert API")
    # key -> [minute_bucket, count_in_bucket]
    _rate: dict[str, list[int]] = {}

    def require_api_key(request: Request) -> str:
        key = request.headers.get("X-API-Key")
        if not key or key not in api_keys:
            raise HTTPException(status_code=401, detail="invalid or missing API key")
        minute = int(time.time() // 60)
        window = _rate.get(key)
        if window is None or window[0] != minute:
            window = [minute, 0]
            _rate[key] = window
        window[1] += 1
        if window[1] > rate_limit:
            raise HTTPException(status_code=429, detail="rate limit exceeded")
        return key

    @app.post("/subscribe", status_code=201)
    def subscribe(body: SubscribeRequest, _key: str = Depends(require_api_key)):
        registry.add(body.url)
        return {"subscribed": body.url}

    @app.delete("/unsubscribe")
    def unsubscribe(body: SubscribeRequest, _key: str = Depends(require_api_key)):
        registry.remove(body.url)
        return {"unsubscribed": body.url}

    @app.get("/subscribers")
    def subscribers(_key: str = Depends(require_api_key)):
        return {"subscribers": registry.all()}

    return app


__all__ = ["create_app", "SubscribeRequest"]
