"""Contract address whitelist (Story 1B.3).

Loads the set of contract addresses QuantumRadar cares about (Uniswap V3 pools,
the Aave V3 Pool) plus their protocol + token metadata from YAML, so the
:class:`~ingestion.router.EventRouter` (1B.4) can look up a log's emitting
address and dispatch to the correct decoder. Address matching is
case-insensitive (normalized to lowercase on load and lookup).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from ingestion.decoders.uniswap_v3 import PoolMeta

ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"


@dataclass
class WhitelistEntry:
    protocol: str  # "uniswap_v3" | "aave_v3"
    pool_meta: PoolMeta  # token0/token1 (ZERO_ADDRESS for Aave single-contract pool)


class ContractWhitelist:
    def __init__(self, entries: dict[str, WhitelistEntry]) -> None:
        # keys must already be normalized to lowercase
        self._entries = entries

    @classmethod
    def from_yaml(cls, path: str | Path) -> "ContractWhitelist":
        with open(path) as f:
            raw = yaml.safe_load(f) or {}
        entries: dict[str, WhitelistEntry] = {}
        for addr, meta in raw.items():
            entries[addr.lower()] = WhitelistEntry(
                protocol=meta["protocol"],
                pool_meta=PoolMeta(
                    token0=meta.get("token0", ZERO_ADDRESS),
                    token1=meta.get("token1", ZERO_ADDRESS),
                ),
            )
        return cls(entries)

    def addresses(self) -> list[str]:
        """Lowercase contract addresses (e.g. for a logs subscription filter)."""
        return list(self._entries)

    def get(self, address: str) -> WhitelistEntry | None:
        return self._entries.get(address.lower())

    def __contains__(self, address: str) -> bool:
        return address.lower() in self._entries

    def __len__(self) -> int:
        return len(self._entries)
