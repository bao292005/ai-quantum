"""Unit tests for emitter.api + emitter.registry (Story 5.1 + 5.4)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from emitter.api import create_app
from emitter.registry import SubscriberRegistry

_KEY = "enterprise-secret"
_HDR = {"X-API-Key": _KEY}
_URL = "http://client.example/hook"


def _client(tmp_path, *, rate_limit=100):
    registry = SubscriberRegistry(tmp_path / "subs.json")
    app = create_app(registry=registry, api_keys={_KEY}, rate_limit=rate_limit)
    return TestClient(app), registry


# ---------------------------------------------------------------------------
# 5.1 — subscribe / unsubscribe
# ---------------------------------------------------------------------------

def test_subscribe_adds_to_registry(tmp_path):
    client, registry = _client(tmp_path)
    r = client.post("/subscribe", json={"url": _URL}, headers=_HDR)
    assert r.status_code == 201
    assert _URL in registry.all()


def test_unsubscribe_removes(tmp_path):
    client, registry = _client(tmp_path)
    client.post("/subscribe", json={"url": _URL}, headers=_HDR)
    r = client.request("DELETE", "/unsubscribe", json={"url": _URL}, headers=_HDR)
    assert r.status_code == 200
    assert _URL not in registry.all()


def test_registry_persists_across_instances(tmp_path):
    path = tmp_path / "subs.json"
    reg1 = SubscriberRegistry(path)
    reg1.add(_URL)
    reg2 = SubscriberRegistry(path)  # reload from disk
    assert _URL in reg2.all()


# ---------------------------------------------------------------------------
# 5.4 — authentication + rate limit
# ---------------------------------------------------------------------------

def test_missing_api_key_is_401(tmp_path):
    client, _ = _client(tmp_path)
    r = client.post("/subscribe", json={"url": _URL})  # no header
    assert r.status_code == 401


def test_wrong_api_key_is_401(tmp_path):
    client, _ = _client(tmp_path)
    r = client.post("/subscribe", json={"url": _URL}, headers={"X-API-Key": "nope"})
    assert r.status_code == 401


def test_rate_limit_returns_429(tmp_path):
    client, _ = _client(tmp_path, rate_limit=3)
    codes = [
        client.post("/subscribe", json={"url": _URL}, headers=_HDR).status_code
        for _ in range(4)
    ]
    assert codes[:3] == [201, 201, 201]
    assert codes[3] == 429
