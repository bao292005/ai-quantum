"""Event router / normalizer (Story 1B.4).

Takes a raw Ethereum log, looks its emitting address up in the
:class:`~ingestion.whitelist.ContractWhitelist`, and dispatches to the matching
decoder (Uniswap V3 or Aave V3). Logs from unknown contracts are silently
dropped (``None``); a known contract emitting an unrecognized ``topic0`` lets the
decoder's ``ValueError`` propagate. This is the single normalized entry point the
Track 1C ring buffer and Epic 2 graph builder consume.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import jsonschema

from ingestion.decoders.aave_v3 import AaveV3Decoder
from ingestion.decoders.uniswap_v3 import TickDataEvent, UniswapV3Decoder
from ingestion.whitelist import ContractWhitelist

logger = logging.getLogger(__name__)

_SCHEMA_PATH = Path(__file__).resolve().parent.parent / "contracts" / "tick_data.schema.json"
_validator: jsonschema.protocols.Validator | None = None


def _get_validator() -> jsonschema.protocols.Validator:
    """Compile the tick-data validator once and reuse it (avoids per-call recompile)."""
    global _validator
    if _validator is None:
        schema = json.loads(_SCHEMA_PATH.read_text())
        cls = jsonschema.validators.validator_for(schema)
        cls.check_schema(schema)
        _validator = cls(schema)
    return _validator


def _log_address(log: dict) -> str:
    addr = log["address"]
    if isinstance(addr, (bytes, bytearray)):
        return "0x" + bytes(addr).hex()
    return addr.lower()


class EventRouter:
    def __init__(self, whitelist: ContractWhitelist) -> None:
        self._whitelist = whitelist
        self._uniswap = UniswapV3Decoder()
        self._aave = AaveV3Decoder()

    @property
    def whitelist(self) -> ContractWhitelist:
        return self._whitelist

    @classmethod
    def from_yaml(cls, path: str | Path) -> "EventRouter":
        return cls(ContractWhitelist.from_yaml(path))

    def route(self, log: dict, block_timestamp: int) -> TickDataEvent | None:
        """Dispatch a raw log to the right decoder.

        Returns a ``TickDataEvent`` for a whitelisted contract, ``None`` for an
        unknown one. Propagates ``ValueError`` if the contract is known but the
        event ``topic0`` is unrecognized.
        """
        entry = self._whitelist.get(_log_address(log))
        if entry is None:
            return None  # unknown contract — silent drop
        if entry.protocol == "uniswap_v3":
            return self._uniswap.decode(log, entry.pool_meta, block_timestamp)
        if entry.protocol == "aave_v3":
            return self._aave.decode(log, entry.pool_meta, block_timestamp)
        logger.warning(json.dumps({"event": "unknown_protocol", "protocol": entry.protocol}))
        return None

    def route_validated(self, log: dict, block_timestamp: int) -> TickDataEvent | None:
        """Like :meth:`route`, but validates output against tick_data.schema.json."""
        event = self.route(log, block_timestamp)
        if event is not None:
            _get_validator().validate(event.to_dict())
        return event
