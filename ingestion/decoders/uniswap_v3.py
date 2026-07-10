"""Uniswap V3 event decoder (Story 1B.1).

Converts a raw Ethereum ``Swap``/``Mint``/``Burn`` log from a Uniswap V3 pool
into a :class:`TickDataEvent` conforming to ``contracts/tick_data.schema.json``.

Also defines the shared :class:`TickDataEvent` / :class:`PoolMeta` dataclasses
and low-level helpers reused by the Aave decoder (1B.2). ``token0``/``token1``
are NOT in the Uniswap event payload — they come from pool metadata supplied by
the caller (the whitelist, 1B.3 / router, 1B.4). The decoder is stateless.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from datetime import datetime, timezone

from eth_abi import decode as abi_decode

SWAP_TOPIC = "0xc42079f94a6350d7e6235f29174924f928cc2ac818eb64fed8004e115fbcca67"
MINT_TOPIC = "0x7a53080ba414158be7ec69b987b5fb7d07dee101fe85488f0853ae16239d0bde"
BURN_TOPIC = "0x0c396cd989a39f4459b5fa1aed6a9a8dcdbc45908acfd67e028cd568da98982c"

# Non-indexed data layout per event (positional). We only read amount0/amount1.
_SWAP_TYPES = ["int256", "int256", "uint160", "uint128", "int24"]
_MINT_TYPES = ["address", "uint128", "uint256", "uint256"]
_BURN_TYPES = ["uint128", "uint256", "uint256"]


@dataclass
class PoolMeta:
    token0: str  # 0x address
    token1: str  # 0x address


@dataclass
class TickDataEvent:
    block_number: int
    block_timestamp: str  # ISO 8601 UTC, e.g. "2023-10-24T12:00:11Z"
    protocol: str
    event_type: str
    pool_address: str
    token0: str
    token1: str
    amount0: str  # decimal string, may be negative (int256 swaps)
    amount1: str
    tx_hash: str
    log_index: int

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


def _topic_hex(raw) -> str:
    """Normalize a topic to a lowercase ``0x``-prefixed hex string.

    ``HexBytes.hex()``/``bytes.hex()`` return no ``0x`` prefix, so add it — the
    module topic constants are ``0x``-prefixed and comparisons must line up.
    """
    if isinstance(raw, (bytes, bytearray)):
        return "0x" + bytes(raw).hex()
    s = str(raw).lower()
    return s if s.startswith("0x") else "0x" + s


def _addr(raw) -> str:
    """Normalize an address value to a lowercase ``0x``-prefixed string."""
    if isinstance(raw, (bytes, bytearray)):
        return "0x" + bytes(raw).hex()
    s = str(raw).lower()
    return s if s.startswith("0x") else "0x" + s


def _to_data_bytes(data) -> bytes:
    if isinstance(data, (bytes, bytearray)):
        return bytes(data)
    return bytes.fromhex(str(data).removeprefix("0x"))


def _to_int(value) -> int:
    """Coerce a numeric log field to ``int``, accepting both ints (web3-parsed)
    and ``0x``-prefixed hex strings (raw JSON-RPC / the mock server)."""
    if isinstance(value, str) and value.startswith("0x"):
        return int(value, 16)
    return int(value)


def _tx_hash(raw) -> str:
    s = raw.hex() if isinstance(raw, (bytes, bytearray)) else str(raw)
    return s if s.startswith("0x") else "0x" + s


def _ts_to_iso(unix_ts: int) -> str:
    return datetime.fromtimestamp(unix_ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class UniswapV3Decoder:
    """Stateless decoder for Uniswap V3 Swap/Mint/Burn logs."""

    def decode(self, log: dict, pool_meta: PoolMeta, block_timestamp: int) -> TickDataEvent:
        topic0 = _topic_hex(log["topics"][0])
        data = _to_data_bytes(log["data"])

        if topic0 == SWAP_TOPIC:
            decoded = abi_decode(_SWAP_TYPES, data)
            amount0, amount1 = int(decoded[0]), int(decoded[1])  # signed int256
            event_type = "swap"
        elif topic0 == MINT_TOPIC:
            decoded = abi_decode(_MINT_TYPES, data)
            amount0, amount1 = int(decoded[2]), int(decoded[3])
            event_type = "mint"
        elif topic0 == BURN_TOPIC:
            decoded = abi_decode(_BURN_TYPES, data)
            amount0, amount1 = int(decoded[1]), int(decoded[2])
            event_type = "burn"
        else:
            raise ValueError(f"Unknown Uniswap V3 topic: {topic0}")

        return TickDataEvent(
            block_number=_to_int(log["blockNumber"]),
            block_timestamp=_ts_to_iso(block_timestamp),
            protocol="uniswap_v3",
            event_type=event_type,
            pool_address=_addr(log["address"]),
            token0=pool_meta.token0.lower(),
            token1=pool_meta.token1.lower(),
            amount0=str(amount0),
            amount1=str(amount1),
            tx_hash=_tx_hash(log["transactionHash"]),
            log_index=_to_int(log["logIndex"]),
        )
