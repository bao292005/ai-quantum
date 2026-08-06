"""Webhook subscriber registry (Story 5.1).

In-memory set of subscriber URLs with optional JSON persistence, so the
subscription list survives an API restart. Single-process (the asyncio app), so
a plain set is sufficient — no locking.
"""

from __future__ import annotations

import json
from pathlib import Path


class SubscriberRegistry:
    def __init__(self, persist_path: str | Path | None = None) -> None:
        self._path = Path(persist_path) if persist_path else None
        self._subs: set[str] = set()
        if self._path and self._path.exists():
            try:
                self._subs = set(json.loads(self._path.read_text()))
            except (json.JSONDecodeError, OSError):
                self._subs = set()

    def add(self, url: str) -> None:
        self._subs.add(url)
        self._save()

    def remove(self, url: str) -> None:
        self._subs.discard(url)
        self._save()

    def all(self) -> list[str]:
        return sorted(self._subs)

    def __contains__(self, url: str) -> bool:
        return url in self._subs

    def __len__(self) -> int:
        return len(self._subs)

    def _save(self) -> None:
        if self._path:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps(sorted(self._subs)))


__all__ = ["SubscriberRegistry"]
